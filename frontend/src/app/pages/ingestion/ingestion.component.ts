import { Component, computed, DestroyRef, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { IngestionService } from '../../core/services/ingestion.service';
import { TrackingService } from '../../core/services/tracking.service';
import { ApplicationsService } from '../../core/services/applications.service';
import { Router } from '@angular/router';
import { CreateApplicationRequest } from '../../core/models/create-application-request.model';
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
import { Subject } from 'rxjs';
import { debounceTime } from 'rxjs/operators';
import { environment } from '../../../environments/environment';
import { FeedbackControlsComponent } from './components/feedback-controls/feedback-controls.component';
import { PreferenceTuningComponent } from './components/preference-tuning/preference-tuning.component';
import { FeedbackKind } from './models/feedback-kind.model';

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
    'remotive', 'remoteok', 'jobicy', 'himalayas',
    'hn_hiring', 'weworkremotely', 'getonboard', 'linkedin',
  ]);
  portalSources = signal<string[]>([]);

  // Loading
  loading = signal(false);
  // Distinct from `loading`: true only while pulling *new* jobs from external
  // sources via "Fetch Jobs". A plain page load reads already-stored jobs and
  // must not imply we're hitting the job boards.
  fetching = signal(false);
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

  // Sort
  sortMode = signal<'' | 'match_desc' | 'date_desc'>('');

  // Show closed jobs toggle
  includeClosed = signal(false);

  ngOnInit(): void {
    this.feedbackRefetch$
      .pipe(debounceTime(environment.feedbackRefetchDebounceMs), takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.loadJobs());
    this.loadPortals();
    this.loadJobs();
    this.openDetailFromQueryParam();
  }

  private openDetailFromQueryParam(): void {
    const jobId = this.route.snapshot.queryParamMap.get('job_id');
    if (!jobId) return;
    this.ingestionService.getJob(jobId).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
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

  loadJobs(): void {
    this.loading.set(true);
    this.error.set('');
    const filtersWithSort = { ...this.filters(), sort: this.sortMode() || undefined };
    this.ingestionService
      .queryJobs(this.activeTab(), this.page(), this.pageSize(), filtersWithSort, this.includeClosed())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.dimmedJobIds.set(new Set<string>());
          this.jobs.set(res.jobs);
          this.total.set(res.total);
          this.totalPages.set(res.total_pages);
          this.loading.set(false);
        },
        error: (err) => {
          this.error.set(err.error?.detail || 'Failed to load jobs');
          this.loading.set(false);
        },
      });
  }

  fetchJobs(): void {
    this.loading.set(true);
    this.fetching.set(true);
    this.error.set('');
    this.ingestionService.fetchJobs().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
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

  loadPortals(): void {
    this.ingestionService.loadPortals().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
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

    this.ingestionService.scanPortals(body).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
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
    this.loadJobs();
  }

  onPageSizeChange(newSize: number): void {
    this.pageSize.set(newSize);
    this.page.set(1);
    this.loadJobs();
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
    this.applicationsService.createFromJob(jobId).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
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

  onSortChange(event: Event): void {
    const value = (event.target as HTMLSelectElement).value as '' | 'match_desc' | 'date_desc';
    this.sortMode.set(value);
    this.page.set(1);
    this.loadJobs();
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
}
