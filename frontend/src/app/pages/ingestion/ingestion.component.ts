import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { IngestionService, JobFilters } from '../../core/services/ingestion.service';
import { TrackingService } from '../../core/services/tracking.service';
import { CreateApplicationRequest } from '../../core/models/create-application-request.model';
import { NormalizedJob } from './models/normalized-job.model';
import { PortalEntry } from './models/portal-entry.model';
import { ScanPortalsRequest } from './models/scan-portals-request.model';
import { ScanError } from './models/scan-result.model';
import { PaginationComponent } from './components/pagination/pagination.component';
import { JobFiltersComponent } from './components/job-filters/job-filters.component';
import { JobDetailPanelComponent } from './components/job-detail-panel/job-detail-panel.component';
import { DatePipe } from '@angular/common';

@Component({
  selector: 'app-ingestion',
  standalone: true,
  imports: [PaginationComponent, JobFiltersComponent, JobDetailPanelComponent, DatePipe],
  templateUrl: './ingestion.component.html',
  styleUrl: './ingestion.component.scss',
})
export class IngestionComponent implements OnInit {
  private ingestionService = inject(IngestionService);
  private trackingService = inject(TrackingService);
  private route = inject(ActivatedRoute);

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
  error = signal('');

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

  // Sort
  sortMode = signal<'' | 'match_desc' | 'date_desc'>('');

  ngOnInit(): void {
    this.loadPortals();
    this.loadJobs();
    this.openDetailFromQueryParam();
  }

  private openDetailFromQueryParam(): void {
    const jobId = this.route.snapshot.queryParamMap.get('job_id');
    if (!jobId) return;
    this.ingestionService.getJob(jobId).subscribe({
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
      .queryJobs(this.activeTab(), this.page(), this.pageSize(), filtersWithSort)
      .subscribe({
        next: (res) => {
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
    this.error.set('');
    this.ingestionService.fetchJobs().subscribe({
      next: () => {
        this.loadJobs();
      },
      error: (err) => {
        this.error.set(err.error?.detail || 'Failed to fetch jobs');
        this.loading.set(false);
      },
    });
  }

  loadPortals(): void {
    this.ingestionService.loadPortals().subscribe({
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

    this.ingestionService.scanPortals(body).subscribe({
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
    const body: CreateApplicationRequest = { job_id: jobId };
    this.trackingService.create(body).subscribe({
      next: () => this.ingestionService.markTracked(jobId),
      error: (err) => {
        if (err.status === 409) this.ingestionService.markTracked(jobId);
      },
    });
  }

  isTracked(jobId: string): boolean {
    return this.trackedJobIds().has(jobId);
  }

  onSortChange(event: Event): void {
    const value = (event.target as HTMLSelectElement).value as '' | 'match_desc' | 'date_desc';
    this.sortMode.set(value);
    this.page.set(1);
    this.loadJobs();
  }

  scoreBadgeClass(score: number): string {
    if (score >= 0.7) return 'score-high';
    if (score >= 0.4) return 'score-mid';
    return 'score-low';
  }
}
