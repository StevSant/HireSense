import { DestroyRef, Injectable, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { HttpErrorResponse } from '@angular/common/http';
import { ActivatedRoute, Router } from '@angular/router';
import { Subject, of, timer } from 'rxjs';
import { catchError, debounceTime, filter, map, switchMap, take } from 'rxjs/operators';
import { ApplicationsService } from '@core/services/applications.service';
import { IngestionService } from '@core/services/ingestion.service';
import { createSortState } from '@core/utils/sort-state';
import { FeedbackKind } from '@core/contracts/feedback-kind.model';
import { JobFilters } from '@core/contracts/job-filters.model';
import { NormalizedJob } from '@core/contracts/normalized-job.model';
import { PortalEntry } from '@core/contracts/portal-entry.model';
import { ScanPortalsRequest } from '@core/contracts/scan-portals-request.model';
import { ScanError } from '@core/contracts/scan-result.model';
import { SourceHealth, SourceInfo } from '@core/contracts/source-capability.model';
import { environment } from '@env/environment';
import { ATS_PORTAL_SOURCES } from './lib/ats-portal-sources';

export type IngestionTab = 'boards' | 'portals';

export type JobSortField = 'match' | 'title' | 'company' | 'location' | 'source' | 'posted';

/**
 * State and orchestration for the Ingestion page.
 *
 * Provided by IngestionComponent rather than the route, so the whole page
 * shares one instance that is discarded on leave — a later visit starts from a
 * clean list instead of resurrecting stale jobs, notices and scan results.
 *
 * Five concerns live here, in this order below: the job list (fetch,
 * pagination, closure revalidation), the query shape (tab, filters, sort,
 * visibility toggles, source catalog), portal scanning, preference feedback,
 * and per-job detail/tracking. They share one store because they share one
 * request — every one of them ultimately re-runs `loadJobs()` with the
 * others' state folded in.
 */
@Injectable()
export class IngestionStore {
  private ingestionService = inject(IngestionService);
  private applicationsService = inject(ApplicationsService);
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  private destroyRef = inject(DestroyRef);

  // ---------------------------------------------------------------------
  // Job list + pagination
  // ---------------------------------------------------------------------

  jobs = signal<NormalizedJob[]>([]);
  total = signal(0);
  page = signal(1);
  pageSize = signal(20);
  totalPages = signal(0);

  loading = signal(false);
  // Distinct from `loading`: true only while pulling *new* jobs from external
  // sources via "Fetch Jobs". A plain page load reads already-stored jobs and
  // must not imply we're hitting the job boards.
  fetching = signal(false);
  // True only while the "Check closed" trigger request is in flight (the sweep
  // itself then runs in the background on the server).
  revalidating = signal(false);
  // Info banner shown while a background closure sweep is running.
  revalidateNotice = signal('');
  // Explains why the visible ranked page may look unchanged after a fetch.
  fetchNotice = signal('');
  error = signal('');

  // LinkedIn connections map (job.id → count), populated from paginated response.
  connectionsByJob = signal<Record<string, number>>({});

  // Every job-list request is funneled through this subject and run via
  // switchMap so a newer request CANCELS the in-flight one (e.g. a filter
  // change while a load is still in flight). The payload is the `rescore`
  // flag for that call.
  //
  // The FIRST load is intentionally not fired from init(). Instead
  // <app-job-filters> always emits its (possibly empty) initial filter state
  // exactly once, synchronously, from its own ngOnInit — see the comment on
  // JobFiltersComponent.ngOnInit — and that emission's applyFilters() handler
  // below is what issues the first loadJobs() call. This guarantees exactly
  // one initial request whether or not a location preference is stored,
  // instead of two racing requests where switchMap silently cancels one.
  private loadJobs$ = new Subject<boolean>();

  // ---------------------------------------------------------------------
  // Query shape — tab, filters, sort, visibility toggles, source catalog
  // ---------------------------------------------------------------------

  activeTab = signal<IngestionTab>('boards');
  filters = signal<JobFilters>({});

  // Sort — clickable column headers, default Match descending.
  sort = createSortState<JobSortField>('match', 'desc', ['title', 'company', 'location', 'source']);

  // Show closed jobs toggle
  includeClosed = signal(false);
  // Show low-quality / spam jobs toggle (hidden by default).
  includeLowQuality = signal(false);

  // Populated from GET /ingestion/sources — the backend registry is the only
  // source of truth. A hand-maintained fallback list used to live here and had
  // already drifted seven sources behind that registry.
  boardSources = signal<string[]>([]);
  portalSources = signal<string[]>([]);
  sourceCatalog = signal<SourceInfo[]>([]);
  sourceHealth = signal<SourceHealth[]>([]);
  sourceWarnings = computed(() => {
    const failing = this.sourceHealth().filter(
      (h) => h.status === 'failing' || h.status === 'degraded',
    );
    const unavailable = this.sourceCatalog().filter(
      (s) =>
        s.enabled &&
        !s.wired &&
        (s.capabilities.requires_credentials || s.capabilities.integration === 'import_fallback'),
    );
    return { failing, unavailable };
  });

  // ---------------------------------------------------------------------
  // Portal scanning
  // ---------------------------------------------------------------------

  portals = signal<PortalEntry[]>([]);
  availableCategories = signal<string[]>([]);
  selectedCategories = signal<string[]>([]);
  selectedCompanies = signal<string[]>([]);
  scanKeyword = signal('');
  scanning = signal(false);
  scanSummary = signal('');
  scanErrors = signal<ScanError[]>([]);
  showScanFilters = signal(false);

  // ---------------------------------------------------------------------
  // Preference feedback
  // ---------------------------------------------------------------------

  // Jobs the user marked "not interested" this session — dimmed locally until
  // the next refetch (no backend "hidden" persistence; see plan/spec).
  dimmedJobIds = signal<Set<string>>(new Set<string>());

  // Coalesces rapid feedback into one re-rank refetch.
  private feedbackRefetch$ = new Subject<void>();

  // ---------------------------------------------------------------------
  // Per-job detail + tracking
  // ---------------------------------------------------------------------

  selectedJob = signal<NormalizedJob | null>(null);

  // Per-job tracking feedback: the id of the job currently being tracked, so
  // its "Track" button can show progress while the request is in flight.
  trackingJobId = signal<string | null>(null);

  trackedJobIds = computed(() => this.ingestionService.trackedJobIds());

  private initialized = false;

  /**
   * Wires the long-lived streams and issues the page's bootstrap requests.
   *
   * Driven from the component's ngOnInit rather than the constructor so the
   * order relative to the child filter component's first emission — which is
   * what triggers the initial job load — stays exactly as it was.
   */
  init(): void {
    if (this.initialized) return;
    this.initialized = true;

    // switchMap: a newer request unsubscribes (aborts) the previous in-flight
    // one, so only the latest filter/sort/page state is ever applied to the
    // signals below. catchError keeps the outer stream alive across failures.
    this.loadJobs$
      .pipe(
        switchMap((rescore) => {
          const filtersWithSort = {
            ...this.filters(),
            sort: this.sort.token() as JobFilters['sort'],
          };
          return this.ingestionService
            .queryJobs(
              this.activeTab(),
              this.page(),
              this.pageSize(),
              filtersWithSort,
              this.includeClosed(),
              rescore,
              this.includeLowQuality(),
            )
            .pipe(
              map((res) => ({ ok: true as const, res })),
              catchError((err: HttpErrorResponse) => of({ ok: false as const, err })),
            );
        }),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((outcome) => {
        this.loading.set(false);
        if (outcome.ok) {
          this.dimmedJobIds.set(new Set<string>());
          this.jobs.set(outcome.res.jobs);
          this.total.set(outcome.res.total);
          this.totalPages.set(outcome.res.total_pages);
          this.connectionsByJob.set(outcome.res.connections_by_job ?? {});
        } else {
          this.error.set(outcome.err.error?.detail || 'Failed to load jobs');
        }
      });

    this.feedbackRefetch$
      .pipe(
        debounceTime(environment.feedbackRefetchDebounceMs),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe(() => this.loadJobs());
    this.loadPortals();
    this.loadSourceCatalog();
    this.applyKeywordFromQueryParam();
    // No loadJobs() here — <app-job-filters>'s guaranteed initial emission
    // (see the loadJobs$ comment above) drives applyFilters(), which issues
    // the first load.
    this.openDetailFromQueryParam();
  }

  loadSourceCatalog(): void {
    this.ingestionService
      .listSources()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.sourceCatalog.set(res.sources);
          this.boardSources.set(
            res.sources
              .filter((s) => s.enabled || s.wired)
              .map((s) => s.capabilities.source)
              .filter((name) => !ATS_PORTAL_SOURCES.includes(name)),
          );
        },
        error: () => {
          // Leave the source dropdown empty rather than guessing at the
          // registry: every other filter still works, and the job list itself
          // is loaded by a separate request.
          this.boardSources.set([]);
        },
      });
    this.ingestionService
      .sourcesHealth()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => this.sourceHealth.set(res.sources),
        error: () => this.sourceHealth.set([]),
      });
  }

  private applyKeywordFromQueryParam(): void {
    const keyword = this.route.snapshot.queryParamMap.get('keyword');
    if (keyword) this.filters.set({ ...this.filters(), keyword });
  }

  private openDetailFromQueryParam(): void {
    const jobId = this.route.snapshot.queryParamMap.get('job_id');
    if (!jobId) return;
    this.ingestionService
      .getJob(jobId)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (job) => this.selectedJob.set(job),
        error: () => {},
      });
  }

  switchTab(tab: IngestionTab): void {
    this.activeTab.set(tab);
    this.page.set(1);
    this.filters.set({});
    this.loadJobs();
  }

  // `rescore` defaults to true (full scoring pipeline). Pure reorder/pagination
  // callers pass false so the server defers the blocking LLM call and reuses
  // cached scores, while the set/order-determining steps still run (#76).
  loadJobs(rescore = true): void {
    this.loading.set(true);
    this.error.set('');
    this.loadJobs$.next(rescore);
  }

  fetchJobs(): void {
    this.loading.set(true);
    this.fetching.set(true);
    this.error.set('');
    this.fetchNotice.set('');
    this.ingestionService
      .fetchJobs()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.fetching.set(false);
          this.fetchNotice.set(
            `Fetch complete: ${res.count} new job(s) ingested. The saved list was refreshed; closed-listing checks continue in the background.`,
          );
          // The fetch already completed its expensive work. Reuse cached scores
          // for the immediate refresh so the new rows are visible promptly.
          this.loadJobs(false);
        },
        error: (err: HttpErrorResponse) => {
          this.error.set(err.error?.detail || 'Failed to fetch jobs');
          this.fetching.set(false);
          this.loading.set(false);
        },
      });
  }

  // Manual closure check: probe the jobs currently on screen synchronously (so
  // a listing you're looking at is closed right away), while the server also
  // sweeps the rest of the corpus in the background. We reload on the immediate
  // result, then poll for a couple of minutes to surface background closures.
  revalidate(): void {
    if (this.revalidating()) return;
    this.revalidating.set(true);
    this.error.set('');
    this.revalidateNotice.set('');
    const visibleIds = this.jobs().map((j) => j.id);
    this.ingestionService
      .revalidate(visibleIds)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.revalidating.set(false);
          this.loadJobs(false); // reflect the immediate (visible-page) closures
          this.revalidateNotice.set(
            `Closed ${res.closed} job(s) on this page. Still scanning the rest of your jobs for closed listings in the background — more may drop off shortly.`,
          );
          timer(environment.closureRevalidatePollMs, environment.closureRevalidatePollMs)
            .pipe(
              // Skip ticks while the tab is backgrounded — no point burning a
              // request (and the user's attention budget) on a poll they
              // can't see; it resumes polling on the next visible tick.
              filter(() => document.visibilityState === 'visible'),
              take(environment.closureRevalidatePollTicks),
              takeUntilDestroyed(this.destroyRef),
            )
            .subscribe({
              next: () => this.loadJobs(false),
              complete: () => this.revalidateNotice.set(''),
            });
        },
        error: (err: HttpErrorResponse) => {
          this.revalidating.set(false);
          this.error.set(err.error?.detail || 'Failed to check for closed jobs');
        },
      });
  }

  loadPortals(): void {
    this.ingestionService
      .loadPortals()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (portals) => {
          this.portals.set(portals);
          const allCategories = portals.flatMap((p) => p.categories);
          this.availableCategories.set([...new Set(allCategories)].sort());
          this.portalSources.set(portals.map((p) => p.name));
        },
        error: () => {},
      });
  }

  scanPortals(): void {
    this.scanning.set(true);
    this.scanSummary.set('');
    this.scanErrors.set([]);

    const body: ScanPortalsRequest = {};
    if (this.selectedCategories().length > 0) body.categories = this.selectedCategories();
    if (this.selectedCompanies().length > 0) body.companies = this.selectedCompanies();
    const kw = this.scanKeyword().trim();
    if (kw) body.keyword = kw;

    this.ingestionService
      .scanPortals(body)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.scanSummary.set(
            `Scan complete: ${res.total_fetched} fetched, ${res.new} new, ${res.duplicates} duplicates.`,
          );
          this.scanErrors.set(res.errors);
          this.scanning.set(false);
          this.loadJobs();
        },
        error: (err: HttpErrorResponse) => {
          this.scanSummary.set(err.error?.detail || 'Scan failed.');
          this.scanning.set(false);
        },
      });
  }

  applyFilters(newFilters: JobFilters): void {
    this.filters.set(newFilters);
    this.page.set(1);
    this.loadJobs();
  }

  goToPage(newPage: number): void {
    this.page.set(newPage);
    this.loadJobs(false); // pagination — scores unchanged, defer LLM rescore
  }

  setPageSize(newSize: number): void {
    this.pageSize.set(newSize);
    this.page.set(1);
    this.loadJobs(false); // pagination — scores unchanged, defer LLM rescore
  }

  setIncludeClosed(include: boolean): void {
    this.includeClosed.set(include);
    this.page.set(1);
    this.loadJobs();
  }

  setIncludeLowQuality(include: boolean): void {
    this.includeLowQuality.set(include);
    this.page.set(1);
    this.loadJobs();
  }

  applySort(): void {
    this.page.set(1);
    this.loadJobs(false); // reorder only — scores unchanged, defer LLM rescore
  }

  setSelectedCategories(categories: string[]): void {
    this.selectedCategories.set(categories);
  }

  setSelectedCompanies(companies: string[]): void {
    this.selectedCompanies.set(companies);
  }

  setScanKeyword(keyword: string): void {
    this.scanKeyword.set(keyword);
  }

  toggleScanFilters(): void {
    this.showScanFilters.update((v) => !v);
  }

  openDetail(job: NormalizedJob): void {
    this.selectedJob.set(job);
  }

  closeDetail(): void {
    this.selectedJob.set(null);
  }

  trackJob(jobId: string): void {
    // Avoid double-submits while a track request is already in flight.
    if (this.trackingJobId() !== null) return;
    this.trackingJobId.set(jobId);
    this.error.set('');
    this.applicationsService
      .createFromJob(jobId)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (agg) => {
          this.ingestionService.markTracked(jobId);
          this.trackingJobId.set(null);
          this.router.navigate(['/dashboard/applications', agg.id]);
        },
        error: (err: HttpErrorResponse) => {
          this.trackingJobId.set(null);
          if (err.status === 409) {
            // Already tracked — mark it and fall back to the applications list
            // so the user can find the existing application.
            this.ingestionService.markTracked(jobId);
            this.router.navigate(['/dashboard/applications']);
            return;
          }
          this.error.set(err.error?.detail || 'Failed to track this job. Please try again.');
        },
      });
  }

  isTracking(jobId: string): boolean {
    return this.trackingJobId() === jobId;
  }

  isTracked(jobId: string): boolean {
    return this.trackedJobIds().has(jobId);
  }

  recordFeedback(jobId: string, kind: FeedbackKind): void {
    if (kind === 'not_interested') {
      const next = new Set(this.dimmedJobIds());
      next.add(jobId);
      this.dimmedJobIds.set(next);
    }
    this.feedbackRefetch$.next();
  }

  isDimmed(jobId: string): boolean {
    return this.dimmedJobIds().has(jobId);
  }

  connectionsCount(jobId: string): number | undefined {
    return this.connectionsByJob()[jobId];
  }
}
