import { Component, OnInit, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { DatePipe, TitleCasePipe } from '@angular/common';
import { CompanyLinkComponent } from '@core/components/company-link';
import { PaginatorComponent } from '@core/components/paginator';
import { SortableHeaderDirective } from '@core/components/sortable-header';
import { ApplicationListItem } from '@core/contracts/application-list-item.model';
import { ApplicationStatus } from '@core/contracts/application-status.model';
import { BatchResult } from '@core/contracts/batch-result.model';
import { dimensionLabel as toDimensionLabel } from '@core/utils/dimension-label';
import { formatScorePercent } from '@core/utils/format-score-percent';
import { scoreColor as toScoreColor } from '@core/utils/score-color';
import { ApplicationCreateDialogComponent } from './components/application-create-dialog.component';
import { ApplicationsStore } from './applications.store';
import { STATUS_TABS } from './lib/status-tabs';

/**
 * Applications list page.
 *
 * A view over ApplicationsStore: every signal below is the store's own signal
 * re-exposed under the name the template already used, and every handler is
 * either a DOM-event adapter (stopping propagation on a row-nested control,
 * reading an input's value, reverting a <select>) or a straight delegation.
 * The pure formatters stay here because nothing but the template needs them.
 */
@Component({
  selector: 'app-applications',
  standalone: true,
  imports: [
    DatePipe,
    TitleCasePipe,
    RouterLink,
    ApplicationCreateDialogComponent,
    SortableHeaderDirective,
    CompanyLinkComponent,
    PaginatorComponent,
  ],
  providers: [ApplicationsStore],
  templateUrl: './applications.component.html',
  styleUrl: './applications.component.scss',
})
export class ApplicationsComponent implements OnInit {
  private store = inject(ApplicationsStore);

  applications = this.store.applications;
  loading = this.store.loading;
  error = this.store.error;
  notice = this.store.notice;
  showCreateDialog = this.store.showCreateDialog;
  deletingId = this.store.deletingId;
  truncatedAt = this.store.truncatedAt;

  sort = this.store.sort;
  query = this.store.query;
  statusFilter = this.store.statusFilter;
  page = this.store.page;
  pageSize = this.store.pageSize;
  statusCounts = this.store.statusCounts;
  filteredApplications = this.store.filteredApplications;
  totalPages = this.store.totalPages;
  currentPage = this.store.currentPage;
  visibleApplications = this.store.visibleApplications;

  leaderboard = this.store.leaderboard;
  evaluating = this.store.evaluating;
  expandedResultId = this.store.expandedResultId;

  researchCache = this.store.researchCache;
  researchingCompany = this.store.researchingCompany;
  expandedResearchId = this.store.expandedResearchId;

  readonly statusTabs = STATUS_TABS;
  readonly statusOptions: ApplicationStatus[] = [
    'saved',
    'applied',
    'interviewing',
    'offered',
    'accepted',
    'rejected',
  ];

  ngOnInit(): void {
    this.store.init();
  }

  dismissNotice(): void {
    this.store.dismissNotice();
  }

  load(): void {
    this.store.load();
  }

  onQueryInput(event: Event): void {
    this.store.setQuery((event.target as HTMLInputElement).value);
  }

  selectStatus(value: ApplicationStatus | ''): void {
    this.store.selectStatus(value);
  }

  onPageChange(page: number): void {
    this.store.goToPage(page);
  }

  onPageSizeChange(size: number): void {
    this.store.setPageSize(size);
  }

  statusCount(value: ApplicationStatus | ''): number {
    return this.store.statusCount(value);
  }

  open(id: string): void {
    this.store.open(id);
  }

  openCreate(): void {
    this.store.openCreate();
  }

  onCreated(id: string): void {
    this.store.onCreated(id);
  }

  scoreColor(score: number | null): string {
    return toScoreColor(score);
  }

  scorePct(score: number | null): string {
    return formatScorePercent(score);
  }

  workModeLabel(mode: ApplicationListItem['remote_modality']): string {
    if (mode === 'on_site') return 'On-site';
    if (mode === 'remote') return 'Remote';
    if (mode === 'hybrid') return 'Hybrid';
    return '';
  }

  updateStatus(app: ApplicationListItem, event: Event): void {
    const select = event.target as HTMLSelectElement;
    const newStatus = select.value as ApplicationStatus;
    // The revert is a DOM write on an element only the view holds a handle to.
    this.store.updateStatus(app, newStatus, () => {
      select.value = app.status;
    });
  }

  remove(app: ApplicationListItem, event: MouseEvent): void {
    event.stopPropagation();
    this.store.remove(app);
  }

  evaluateAll(): void {
    this.store.evaluateAll();
  }

  toggleExpand(sourceId: string, event: Event): void {
    event.stopPropagation();
    this.store.toggleExpand(sourceId);
  }

  openLeaderboardResult(result: BatchResult): void {
    this.store.openLeaderboardResult(result);
  }

  dimensionLabel(dimension: string): string {
    return toDimensionLabel(dimension);
  }

  researchCompany(app: ApplicationListItem, event: Event): void {
    event.stopPropagation();
    this.store.researchCompany(app);
  }

  refreshResearch(app: ApplicationListItem): void {
    this.store.refreshResearch(app);
  }

  toggleResearch(appId: string, event: Event): void {
    event.stopPropagation();
    this.store.toggleResearch(appId);
  }

  hasResearch(appId: string): boolean {
    return this.store.hasResearch(appId);
  }
}
