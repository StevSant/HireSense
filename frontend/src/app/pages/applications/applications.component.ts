import { Component, DestroyRef, OnInit, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { DatePipe, TitleCasePipe } from '@angular/common';
import { ApplicationsService } from '../../core/services/applications.service';
import { TrackingService } from '../../core/services/tracking.service';
import { ResearchService } from '../../core/services/research.service';
import { LlmRunnerService } from '../../core/services/llm-runner.service';
import { ApplicationListItem } from './models/application-list-item.model';
import { ApplicationCreateDialogComponent } from './components/application-create-dialog.component';
import { ApplicationStatus } from '../../core/models/application-status.model';
import { UpdateApplicationRequest } from '../tracking/models/update-application-request.model';
import { BatchEvaluationResponse } from '../tracking/models/batch-evaluation-response.model';
import { BatchResult } from '../tracking/models/batch-result.model';
import { CompanyResearch } from '../tracking/models/company-research.model';
import { scoreColor as toScoreColor } from '../../core/utils/score-color';
import { formatScorePercent } from '../../core/utils/format-score-percent';
import { dimensionLabel as toDimensionLabel } from '../../core/utils/dimension-label';
import { SortableHeaderDirective } from '../../core/components/sortable-header';
import { CompanyLinkComponent } from '../../core/components/company-link';
import { createSortState } from '../../core/utils/sort-state';
import { sortItems } from '../../core/utils/sort-items';

type AppSortField = 'title' | 'company' | 'status' | 'match' | 'created';

interface StatusTab {
  readonly value: ApplicationStatus | '';
  readonly label: string;
}

// Canonical status tabs. Values mirror the backend ApplicationStatus enum
// (tracking/domain/models.py); '' is the "All" pseudo-tab.
const STATUS_TABS: readonly StatusTab[] = [
  { value: '', label: 'All' },
  { value: 'saved', label: 'Saved' },
  { value: 'applied', label: 'Applied' },
  { value: 'interviewing', label: 'Interviewing' },
  { value: 'offered', label: 'Offer' },
  { value: 'accepted', label: 'Accepted' },
  { value: 'rejected', label: 'Rejected' },
];

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
  ],
  templateUrl: './applications.component.html',
  styleUrl: './applications.component.scss',
})
export class ApplicationsComponent implements OnInit {
  private service = inject(ApplicationsService);
  private trackingService = inject(TrackingService);
  private researchService = inject(ResearchService);
  private llmRunner = inject(LlmRunnerService);
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);

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

  // Client-side sort + filter over the fully-loaded list.
  sort = createSortState<AppSortField>('created', 'desc', ['title', 'company', 'status']);
  query = signal('');
  statusFilter = signal<ApplicationStatus | ''>('');

  readonly statusTabs = STATUS_TABS;
  readonly statusOptions: ApplicationStatus[] = [
    'saved',
    'applied',
    'interviewing',
    'offered',
    'accepted',
    'rejected',
  ];

  // Evaluate-all leaderboard state. Constant key — only one batch evaluation
  // run makes sense per page — run lives in LlmRunnerService so it survives
  // navigating away mid-evaluation.
  private readonly batchEvaluateKey = 'applications:batch-evaluate';
  leaderboard = computed(
    () => this.llmRunner.result<BatchEvaluationResponse>(this.batchEvaluateKey)?.results ?? [],
  );
  evaluating = computed(() => this.llmRunner.isRunning(this.batchEvaluateKey));
  expandedResultId = signal<string | null>(null);

  // Per-company research state (keyed by application id).
  researchCache = signal<Record<string, CompanyResearch>>({});
  researchingCompany = signal<string | null>(null);
  expandedResearchId = signal<string | null>(null);

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

  visibleApplications = computed(() => {
    let rows = this.searchFiltered();
    const status = this.statusFilter();
    if (status) rows = rows.filter((a) => a.status === status);
    const field = this.sort.field();
    return sortItems(rows, (a) => this.sortValue(a, field), this.sort.dir());
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

  onQueryInput(event: Event): void {
    this.query.set((event.target as HTMLInputElement).value);
  }

  selectStatus(value: ApplicationStatus | ''): void {
    this.statusFilter.set(value);
  }

  statusCount(value: ApplicationStatus | ''): number {
    return this.statusCounts()[value] ?? 0;
  }

  ngOnInit(): void {
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
      .list()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (rows) => {
          this.applications.set(rows);
          this.loading.set(false);
        },
        error: (err) => {
          this.manualError.set(err?.error?.detail ?? 'Failed to load applications');
          this.loading.set(false);
        },
      });
  }

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

  // ----- inline status change (folded in from the Tracking page) ----------
  // Applications share their id with the tracked-application row, so the
  // tracking PATCH endpoint updates the same record.
  updateStatus(app: ApplicationListItem, event: Event): void {
    const select = event.target as HTMLSelectElement;
    const newStatus = select.value as ApplicationStatus;
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
        error: (err) => {
          this.manualError.set(err?.error?.detail ?? 'Failed to update status');
          select.value = app.status;
        },
      });
  }

  remove(app: ApplicationListItem, event: MouseEvent): void {
    event.stopPropagation();
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
        error: (err) => {
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

  toggleExpand(sourceId: string, event: Event): void {
    event.stopPropagation();
    this.expandedResultId.update((current) => (current === sourceId ? null : sourceId));
  }

  // Leaderboard rows for tracked applications carry the application id as
  // source_id, so the card links straight to that application's detail page.
  openLeaderboardResult(result: BatchResult): void {
    if (result.source === 'tracked') {
      this.router.navigate(['/dashboard/applications', result.source_id]);
    }
  }

  dimensionLabel(dimension: string): string {
    return toDimensionLabel(dimension);
  }

  // ----- company research -------------------------------------------------
  researchCompany(app: ApplicationListItem, event: Event): void {
    event.stopPropagation();
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
        error: (err) => {
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
        error: (err) => {
          this.manualError.set(err?.error?.detail ?? 'Research refresh failed');
          this.researchingCompany.set(null);
        },
      });
  }

  toggleResearch(appId: string, event: Event): void {
    event.stopPropagation();
    this.expandedResearchId.update((current) => (current === appId ? null : appId));
  }

  hasResearch(appId: string): boolean {
    return appId in this.researchCache();
  }
}
