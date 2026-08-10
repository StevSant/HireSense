import { Component, OnInit, inject } from '@angular/core';
import { DatePipe } from '@angular/common';
import { CompanyLinkComponent } from '@core/components/company-link';
import { PaginatorComponent } from '@core/components/paginator';
import { SortableHeaderDirective } from '@core/components/sortable-header';
import { FeedbackKind } from '@core/contracts/feedback-kind.model';
import { JobFilters } from '@core/contracts/job-filters.model';
import { NormalizedJob } from '@core/contracts/normalized-job.model';
import { scoreClass } from '@core/utils/score-class';
import { FeedbackControlsComponent } from './components/feedback-controls/feedback-controls.component';
import { JobDetailPanelComponent } from './components/job-detail-panel/job-detail-panel.component';
import { JobFiltersComponent } from './components/job-filters/job-filters.component';
import { PreferenceTuningComponent } from './components/preference-tuning/preference-tuning.component';
import { IngestionStore, IngestionTab } from './ingestion.store';

/**
 * Ingestion page — the job board / company portal browser.
 *
 * A view over IngestionStore: every signal below is the store's own signal
 * re-exposed under the name the template already used, and every handler is
 * either a DOM-event adapter (unwrapping the `Event` a native control emits)
 * or a straight delegation. Keeping the store's API in plain values rather
 * than DOM events is what lets it be exercised without a fixture.
 */
@Component({
  selector: 'app-ingestion',
  standalone: true,
  imports: [
    PaginatorComponent,
    JobFiltersComponent,
    JobDetailPanelComponent,
    DatePipe,
    FeedbackControlsComponent,
    PreferenceTuningComponent,
    SortableHeaderDirective,
    CompanyLinkComponent,
  ],
  providers: [IngestionStore],
  templateUrl: './ingestion.component.html',
  styleUrl: './ingestion.component.scss',
})
export class IngestionComponent implements OnInit {
  private store = inject(IngestionStore);

  activeTab = this.store.activeTab;

  jobs = this.store.jobs;
  total = this.store.total;
  page = this.store.page;
  pageSize = this.store.pageSize;
  totalPages = this.store.totalPages;

  filters = this.store.filters;
  sort = this.store.sort;
  includeClosed = this.store.includeClosed;
  includeLowQuality = this.store.includeLowQuality;
  boardSources = this.store.boardSources;
  portalSources = this.store.portalSources;
  sourceWarnings = this.store.sourceWarnings;

  loading = this.store.loading;
  fetching = this.store.fetching;
  revalidating = this.store.revalidating;
  revalidateNotice = this.store.revalidateNotice;
  fetchNotice = this.store.fetchNotice;
  error = this.store.error;

  portals = this.store.portals;
  availableCategories = this.store.availableCategories;
  scanKeyword = this.store.scanKeyword;
  scanning = this.store.scanning;
  scanSummary = this.store.scanSummary;
  scanErrors = this.store.scanErrors;
  showScanFilters = this.store.showScanFilters;

  selectedJob = this.store.selectedJob;
  trackingJobId = this.store.trackingJobId;

  ngOnInit(): void {
    this.store.init();
  }

  switchTab(tab: IngestionTab): void {
    this.store.switchTab(tab);
  }

  loadJobs(rescore = true): void {
    this.store.loadJobs(rescore);
  }

  fetchJobs(): void {
    this.store.fetchJobs();
  }

  revalidate(): void {
    this.store.revalidate();
  }

  scanPortals(): void {
    this.store.scanPortals();
  }

  onFiltersChange(newFilters: JobFilters): void {
    this.store.applyFilters(newFilters);
  }

  onPageChange(newPage: number): void {
    this.store.goToPage(newPage);
  }

  onPageSizeChange(newSize: number): void {
    this.store.setPageSize(newSize);
  }

  onSorted(): void {
    this.store.applySort();
  }

  onIncludeClosedChange(event: Event): void {
    this.store.setIncludeClosed((event.target as HTMLInputElement).checked);
  }

  onIncludeLowQualityChange(event: Event): void {
    this.store.setIncludeLowQuality((event.target as HTMLInputElement).checked);
  }

  openDetail(job: NormalizedJob): void {
    this.store.openDetail(job);
  }

  closeDetail(): void {
    this.store.closeDetail();
  }

  toggleScanFilters(): void {
    this.store.toggleScanFilters();
  }

  onCategoryChange(event: Event): void {
    const select = event.target as HTMLSelectElement;
    this.store.setSelectedCategories(Array.from(select.selectedOptions).map((o) => o.value));
  }

  onCompanyChange(event: Event): void {
    const select = event.target as HTMLSelectElement;
    this.store.setSelectedCompanies(Array.from(select.selectedOptions).map((o) => o.value));
  }

  onScanKeywordInput(event: Event): void {
    this.store.setScanKeyword((event.target as HTMLInputElement).value);
  }

  trackJob(jobId: string): void {
    this.store.trackJob(jobId);
  }

  isTracking(jobId: string): boolean {
    return this.store.isTracking(jobId);
  }

  isTracked(jobId: string): boolean {
    return this.store.isTracked(jobId);
  }

  onFeedback(jobId: string, kind: FeedbackKind): void {
    this.store.recordFeedback(jobId, kind);
  }

  isDimmed(jobId: string): boolean {
    return this.store.isDimmed(jobId);
  }

  scoreBadgeClass(score: number): string {
    return scoreClass(score);
  }

  connectionsCount(jobId: string): number | undefined {
    return this.store.connectionsCount(jobId);
  }
}
