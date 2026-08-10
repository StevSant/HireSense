import { DestroyRef, Injectable, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { HttpErrorResponse } from '@angular/common/http';
import { ActivatedRoute, Router } from '@angular/router';
import { ApplicationsService } from '@core/services/applications.service';
import { LlmRunnerService } from '@core/services/llm-runner.service';
import { ResearchService } from '@core/services/research.service';
import { TrackingService } from '@core/services/tracking.service';
import { ApplicationListItem } from '@core/contracts/application-list-item.model';
import { ApplicationStatus } from '@core/contracts/application-status.model';
import { BatchEvaluationResponse } from '@core/contracts/batch-evaluation-response.model';
import { BatchResult } from '@core/contracts/batch-result.model';
import { CompanyResearch } from '@core/contracts/company-research.model';
import { UpdateApplicationRequest } from '@core/contracts/update-application-request.model';
import { createSortState } from '@core/utils/sort-state';
import { sortItems } from '@core/utils/sort-items';
import { STATUS_TABS } from './lib/status-tabs';

export type AppSortField = 'title' | 'company' | 'status' | 'match' | 'created';

// Rows per page in the applications table before the user changes it.
const DEFAULT_PAGE_SIZE = 20;

/**
 * State and orchestration for the Applications list page.
 *
 * Provided by ApplicationsComponent rather than the route, so the page shares
 * one instance that is discarded on leave. The batch-evaluation run itself
 * lives in the root-scoped LlmRunnerService precisely so it does NOT die with
 * this store.
 *
 * Six concerns live here, in this order below: loading the list, the
 * client-side search/sort/filter/paging pipeline, per-row mutations (status
 * and delete), batch evaluation + leaderboard, company research, and
 * navigation. They share one store because every one of them reads or writes
 * the single `applications` array.
 */
@Injectable()
export class ApplicationsStore {
  private service = inject(ApplicationsService);
  private trackingService = inject(TrackingService);
  private researchService = inject(ResearchService);
  private llmRunner = inject(LlmRunnerService);
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);

  // ---------------------------------------------------------------------
  // List loading
  // ---------------------------------------------------------------------

  applications = signal<ApplicationListItem[]>([]);
  loading = signal(false);
  // Shared error banner for this page's non-LLM actions (load/delete/status
  // update/research); merged with the batch-evaluate run's mapped error.
  private manualError = signal('');
  error = computed(() => this.manualError() || this.llmRunner.error(this.batchEvaluateKey));
  // Dismissible notice shown when the detail page bounced us here (e.g. a
  // stale/deleted application id produced a 404).
  notice = signal('');
  showCreateDialog = signal(false);
  deletingId = signal<string | null>(null);

  // Set when the server holds more applications than the load walk pulled in
  // (environment.listMaxItems), so the UI can say so instead of implying the
  // list is complete.
  truncatedAt = signal<number | null>(null);

  // ---------------------------------------------------------------------
  // Search / sort / filter / paging — all client-side over the loaded list
  // ---------------------------------------------------------------------

  // Client-side sort + filter over the fully-loaded list.
  sort = createSortState<AppSortField>('created', 'desc', ['title', 'company', 'status']);
  query = signal('');
  statusFilter = signal<ApplicationStatus | ''>('');

  // Client-side paging over the filtered rows — the table is a slice, but the
  // search, sort and status badges still see every loaded application.
  page = signal(1);
  pageSize = signal(DEFAULT_PAGE_SIZE);

  // Count per status across the full (search-filtered) list, for the tab badges.
  // The status filter itself is excluded so each tab shows its own total.
  private searchFiltered = computed(() => {
    const q = this.query().trim().toLowerCase();
    if (!q) return this.applications();
    return this.applications().filter(
      (a) => a.title.toLowerCase().includes(q) || a.company.toLowerCase().includes(q),
    );
  });

  statusCounts = computed<Record<string, number>>(() => {
    const counts: Record<string, number> = { '': this.searchFiltered().length };
    for (const tab of STATUS_TABS) {
      if (tab.value === '') continue;
      counts[tab.value] = 0;
    }
    for (const a of this.searchFiltered()) {
      counts[a.status] = (counts[a.status] ?? 0) + 1;
    }
    return counts;
  });

  // Every row that survives the search + status filter, sorted. The whole list
  // is loaded up front (see load()), so this stays client-side.
  filteredApplications = computed(() => {
    let rows = this.searchFiltered();
    const status = this.statusFilter();
    if (status) rows = rows.filter((a) => a.status === status);
    const field = this.sort.field();
    return sortItems(rows, (a) => this.sortValue(a, field), this.sort.dir());
  });

  totalPages = computed(() =>
    Math.max(1, Math.ceil(this.filteredApplications().length / this.pageSize())),
  );

  // Clamped read of `page`: narrowing the filter can strand the user past the
  // last page, and this pulls them back without an extra effect.
  currentPage = computed(() => Math.min(this.page(), this.totalPages()));

  // The slice actually rendered into the table.
  visibleApplications = computed(() => {
    const start = (this.currentPage() - 1) * this.pageSize();
    return this.filteredApplications().slice(start, start + this.pageSize());
  });

  private sortValue(a: ApplicationListItem, field: AppSortField): string | number | null {
    switch (field) {
      case 'title':
        return a.title;
      case 'company':
        return a.company;
      case 'status':
        return a.status;
      case 'match':
        return a.latest_match_score;
      case 'created':
        return a.created_at;
    }
  }

  // ---------------------------------------------------------------------
  // Evaluate-all + leaderboard
  // ---------------------------------------------------------------------

  // Evaluate-all leaderboard state. Constant key — only one batch evaluation
  // run makes sense per page — run lives in LlmRunnerService so it survives
  // navigating away mid-evaluation.
  private readonly batchEvaluateKey = 'applications:batch-evaluate';
  leaderboard = computed(
    () => this.llmRunner.result<BatchEvaluationResponse>(this.batchEvaluateKey)?.results ?? [],
  );
  evaluating = computed(() => this.llmRunner.isRunning(this.batchEvaluateKey));
  expandedResultId = signal<string | null>(null);

  // ---------------------------------------------------------------------
  // Company research (keyed by application id)
  // ---------------------------------------------------------------------

  researchCache = signal<Record<string, CompanyResearch>>({});
  researchingCompany = signal<string | null>(null);
  expandedResearchId = signal<string | null>(null);

  private initialized = false;

  /**
   * Consumes the `notFound` redirect flag, then loads the list.
   *
   * Driven from the component's ngOnInit rather than the constructor so the
   * order stays exactly as it was: the notice is set and the flag stripped
   * before the list request goes out.
   */
  init(): void {
    if (this.initialized) return;
    this.initialized = true;
    if (this.route.snapshot.queryParamMap.has('notFound')) {
      this.notice.set(
        'That application no longer exists — it may have been deleted, or the link is stale (the database was reset).',
      );
      // Strip the flag so a manual refresh doesn't re-show the notice.
      this.router.navigate([], {
        relativeTo: this.route,
        queryParams: {},
        replaceUrl: true,
      });
    }
    this.load();
  }

  dismissNotice(): void {
    this.notice.set('');
  }

  load(): void {
    this.loading.set(true);
    this.manualError.set('');
    this.service
      .listAll()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: ({ items, total }) => {
          this.applications.set(items);
          this.truncatedAt.set(items.length < total ? total : null);
          this.loading.set(false);
        },
        error: (err: HttpErrorResponse) => {
          this.manualError.set(err?.error?.detail ?? 'Failed to load applications');
          this.loading.set(false);
        },
      });
  }

  setQuery(value: string): void {
    this.query.set(value);
    this.page.set(1);
  }

  selectStatus(value: ApplicationStatus | ''): void {
    this.statusFilter.set(value);
    this.page.set(1);
  }

  goToPage(page: number): void {
    this.page.set(page);
  }

  setPageSize(size: number): void {
    this.pageSize.set(size);
    this.page.set(1);
  }

  statusCount(value: ApplicationStatus | ''): number {
    return this.statusCounts()[value] ?? 0;
  }

  // ----- inline status change (folded in from the Tracking page) ----------
  // Applications share their id with the tracked-application row, so the
  // tracking PATCH endpoint updates the same record.
  //
  // `onFailure` puts the <select> back: once the user has picked an option the
  // element is uncontrolled (its [value] binding doesn't re-fire, because the
  // row's status never changed), so reverting it is a DOM write only the view
  // can perform. The caller supplies it rather than the store reaching for the
  // element.
  updateStatus(
    app: ApplicationListItem,
    newStatus: ApplicationStatus,
    onFailure: () => void,
  ): void {
    const body: UpdateApplicationRequest = { status: newStatus };
    this.trackingService
      .update(app.id, body)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (updated) => {
          this.applications.update((rows) =>
            rows.map((r) =>
              r.id === app.id
                ? { ...r, status: updated.status, applied_at: updated.applied_at }
                : r,
            ),
          );
        },
        error: (err: HttpErrorResponse) => {
          this.manualError.set(err?.error?.detail ?? 'Failed to update status');
          onFailure();
        },
      });
  }

  remove(app: ApplicationListItem): void {
    const label = `${app.title} · ${app.company}`;
    if (
      !confirm(
        `Delete "${label}"?\n\nThis removes the application and all its matches, optimizations, cover letters and interview prep. The original job in Ingestion is not affected.`,
      )
    ) {
      return;
    }
    this.deletingId.set(app.id);
    this.service
      .remove(app.id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.applications.update((rows) => rows.filter((r) => r.id !== app.id));
          this.deletingId.set(null);
        },
        error: (err: HttpErrorResponse) => {
          this.manualError.set(err?.error?.detail ?? 'Failed to delete application');
          this.deletingId.set(null);
        },
      });
  }

  // ----- evaluate-all + leaderboard ---------------------------------------
  evaluateAll(): void {
    const apps = this.applications();
    if (apps.length === 0) return;
    const ids = apps.map((a) => a.id);
    this.llmRunner.clear(this.batchEvaluateKey);
    this.llmRunner.run(
      this.batchEvaluateKey,
      this.trackingService.batchEvaluate(ids),
      (err) => err?.error?.detail ?? 'Batch evaluation failed',
    );
  }

  toggleExpand(sourceId: string): void {
    this.expandedResultId.update((current) => (current === sourceId ? null : sourceId));
  }

  // ----- company research -------------------------------------------------
  researchCompany(app: ApplicationListItem): void {
    this.researchingCompany.set(app.id);
    this.researchService
      .research({ company_name: app.company, job_description: app.notes || '' })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.researchCache.update((cache) => ({ ...cache, [app.id]: res }));
          this.researchingCompany.set(null);
          this.expandedResearchId.set(app.id);
        },
        error: (err: HttpErrorResponse) => {
          this.manualError.set(err?.error?.detail ?? 'Research failed');
          this.researchingCompany.set(null);
        },
      });
  }

  refreshResearch(app: ApplicationListItem): void {
    this.researchingCompany.set(app.id);
    this.researchService
      .refresh({ company_name: app.company, job_description: app.notes || '' })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.researchCache.update((cache) => ({ ...cache, [app.id]: res }));
          this.researchingCompany.set(null);
        },
        error: (err: HttpErrorResponse) => {
          this.manualError.set(err?.error?.detail ?? 'Research refresh failed');
          this.researchingCompany.set(null);
        },
      });
  }

  toggleResearch(appId: string): void {
    this.expandedResearchId.update((current) => (current === appId ? null : appId));
  }

  hasResearch(appId: string): boolean {
    return appId in this.researchCache();
  }

  // ----- navigation --------------------------------------------------------
  open(id: string): void {
    this.router.navigate(['/dashboard/applications', id]);
  }

  openCreate(): void {
    this.showCreateDialog.set(true);
  }

  onCreated(id: string): void {
    this.showCreateDialog.set(false);
    this.router.navigate(['/dashboard/applications', id]);
  }

  // Leaderboard rows for tracked applications carry the application id as
  // source_id, so the card links straight to that application's detail page.
  openLeaderboardResult(result: BatchResult): void {
    if (result.source === 'tracked') {
      this.router.navigate(['/dashboard/applications', result.source_id]);
    }
  }
}
