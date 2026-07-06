import { Component, computed, DestroyRef, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { IngestionService } from '../../core/services/ingestion.service';
import { TrackingService } from '../../core/services/tracking.service';
import { ApplicationsService } from '../../core/services/applications.service';
import { Router } from '@angular/router';
import { JobFilters } from './models/job-filters.model';
import { NormalizedJob } from './models/normalized-job.model';
import { PortalEntry } from './models/portal-entry.model';
import { ScanPortalsRequest } from './models/scan-portals-request.model';
import { ScanError } from './models/scan-result.model';
import { PaginationComponent } from './components/pagination/pagination.component';
import { scoreClass } from '../../core/utils/score-class';
import { JobFiltersComponent } from './components/job-filters/job-filters.component';
import { JobDetailPanelComponent } from './components/job-detail-panel/job-detail-panel.component';
import { DatePipe } from '@angular/common';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { of, Subject, timer } from 'rxjs';
import { catchError, debounceTime, map, switchMap, take } from 'rxjs/operators';
import { environment } from '../../../environments/environment';
import { FeedbackControlsComponent } from './components/feedback-controls/feedback-controls.component';
import { PreferenceTuningComponent } from './components/preference-tuning/preference-tuning.component';
import { FeedbackKind } from './models/feedback-kind.model';
import { SortableHeaderDirective } from '../../core/components/sortable-header';
import { CompanyLinkComponent } from '../../core/components/company-link';
import { createSortState } from '../../core/utils/sort-state';

@Component({
  selector: 'app-ingestion',
  standalone: true,
  imports: [
    PaginationComponent,
    JobFiltersComponent,
    JobDetailPanelComponent,
    DatePipe,
    FeedbackControlsComponent,
    PreferenceTuningComponent,
    SortableHeaderDirective,
    CompanyLinkComponent,
  ],
  templateUrl: './ingestion.component.html',
  styleUrl: './ingestion.component.scss',
})
export class IngestionComponent implements OnInit {
  private ingestionService = inject(IngestionService);
  private trackingService = inject(TrackingService);
  private applicationsService = inject(ApplicationsService);
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  private destroyRef = inject(DestroyRef);

  trackedJobIds = computed(() => this.ingestionService.trackedJobIds());

  // Tab state
  activeTab = signal<'boards' | 'portals'>('boards');

  // Jobs + pagination
  jobs = signal<NormalizedJob[]>([]);
  total = signal(0);
  page = signal(1);
  pageSize = signal(20);
  totalPages = signal(0);

  // Filters
  filters = signal<JobFilters>({});
  boardSources = signal<string[]>([
    'remotive',
    'remoteok',
    'jobicy',
    'himalayas',
    'hn_hiring',
    'weworkremotely',
    'getonboard',
    'linkedin',
  ]);
  portalSources = signal<string[]>([]);

  // Loading
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
  error = signal('');

  // Per-job tracking feedback: the id of the job currently being tracked, so
  // its "Track" button can show progress while the request is in flight.
  trackingJobId = signal<string | null>(null);

  // Portal scan state
  portals = signal<PortalEntry[]>([]);
  availableCategories = signal<string[]>([]);
  selectedCategories = signal<string[]>([]);
  selectedCompanies = signal<string[]>([]);
  scanKeyword = signal('');
  scanning = signal(false);
  scanSummary = signal('');
  scanErrors = signal<ScanError[]>([]);
  showScanFilters = signal(false);

  // Detail panel
  selectedJob = signal<NormalizedJob | null>(null);

  // Jobs the user marked "not interested" this session — dimmed locally until
  // the next refetch (no backend "hidden" persistence; see plan/spec).
  dimmedJobIds = signal<Set<string>>(new Set<string>());

  // Coalesces rapid feedback into one re-rank refetch.
  private feedbackRefetch$ = new Subject<void>();

  // Every job-list request is funneled through this subject and run via
  // switchMap so a newer request CANCELS the in-flight one (#race). Without it,
  // the initial empty-filter load in ngOnInit and the localStorage-restored
  // location filter emitted by <app-job-filters> raced — two uncancelled
  // requests whose last-to-resolve won, so the same page rendered differently
  // on navigation vs refresh. The payload is the `rescore` flag for that call.
  private loadJobs$ = new Subject<boolean>();

  // Sort — clickable column headers, default Match descending.
  sort = createSortState<'match' | 'title' | 'company' | 'location' | 'source' | 'posted'>(
    'match',
    'desc',
    ['title', 'company', 'location', 'source'],
  );

  // LinkedIn connections map (job.id → count), populated from paginated response.
  connectionsByJob = signal<Record<string, number>>({});

  // Show closed jobs toggle
  includeClosed = signal(false);
  // Show low-quality / spam jobs toggle (hidden by default).
  includeLowQuality = signal(false);

  ngOnInit(): void {
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
              catchError((err) => of({ ok: false as const, err })),
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
    this.applyKeywordFromQueryParam();
    this.loadJobs();
    this.openDetailFromQueryParam();
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

  switchTab(tab: 'boards' | 'portals'): void {
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
    this.ingestionService
      .fetchJobs()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.fetching.set(false);
          this.loadJobs();
        },
        error: (err) => {
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
          timer(15000, 15000)
            .pipe(take(8), takeUntilDestroyed(this.destroyRef))
            .subscribe({
              next: () => this.loadJobs(false),
              complete: () => this.revalidateNotice.set(''),
            });
        },
        error: (err) => {
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
        error: (err) => {
          this.scanSummary.set(err.error?.detail || 'Scan failed.');
          this.scanning.set(false);
        },
      });
  }

  onFiltersChange(newFilters: JobFilters): void {
    this.filters.set(newFilters);
    this.page.set(1);
    this.loadJobs();
  }

  onPageChange(newPage: number): void {
    this.page.set(newPage);
    this.loadJobs(false); // pagination — scores unchanged, defer LLM rescore
  }

  onPageSizeChange(newSize: number): void {
    this.pageSize.set(newSize);
    this.page.set(1);
    this.loadJobs(false); // pagination — scores unchanged, defer LLM rescore
  }

  openDetail(job: NormalizedJob): void {
    this.selectedJob.set(job);
  }

  closeDetail(): void {
    this.selectedJob.set(null);
  }

  toggleScanFilters(): void {
    this.showScanFilters.update((v) => !v);
  }

  onCategoryChange(event: Event): void {
    const select = event.target as HTMLSelectElement;
    this.selectedCategories.set(Array.from(select.selectedOptions).map((o) => o.value));
  }

  onCompanyChange(event: Event): void {
    const select = event.target as HTMLSelectElement;
    this.selectedCompanies.set(Array.from(select.selectedOptions).map((o) => o.value));
  }

  onScanKeywordInput(event: Event): void {
    this.scanKeyword.set((event.target as HTMLInputElement).value);
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
        error: (err) => {
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

  onIncludeClosedChange(event: Event): void {
    this.includeClosed.set((event.target as HTMLInputElement).checked);
    this.page.set(1);
    this.loadJobs();
  }

  onIncludeLowQualityChange(event: Event): void {
    this.includeLowQuality.set((event.target as HTMLInputElement).checked);
    this.page.set(1);
    this.loadJobs();
  }

  onSorted(): void {
    this.page.set(1);
    this.loadJobs(false); // reorder only — scores unchanged, defer LLM rescore
  }

  onFeedback(jobId: string, kind: FeedbackKind): void {
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

  scoreBadgeClass(score: number): string {
    return scoreClass(score);
  }

  connectionsCount(jobId: string): number | undefined {
    return this.connectionsByJob()[jobId];
  }
}
