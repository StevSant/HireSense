import { Component, DestroyRef, OnInit, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { TitleCasePipe, DatePipe } from '@angular/common';
import { TrackingService } from '../../core/services/tracking.service';
import { ResearchService } from '../../core/services/research.service';
import { ApplicationStatus } from '../../core/models/application-status.model';
import { CreateApplicationRequest } from '../../core/models/create-application-request.model';
import { BatchResult } from './models/batch-result.model';
import { CompanyResearch } from './models/company-research.model';
import { TrackedApplication } from './models/tracked-application.model';
import { UpdateApplicationRequest } from './models/update-application-request.model';
import { scoreColor as toScoreColor } from '../../core/utils/score-color';
import { SortableHeaderComponent } from '../../core/components/sortable-header';
import { createSortState } from '../../core/utils/sort-state';
import { sortItems } from '../../core/utils/sort-items';

type TrackSortField = 'company' | 'title' | 'status' | 'posted' | 'applied';

@Component({
  selector: 'app-tracking',
  standalone: true,
  imports: [FormsModule, TitleCasePipe, DatePipe, RouterLink, SortableHeaderComponent],
  templateUrl: './tracking.component.html',
  styleUrl: './tracking.component.scss',
})
export class TrackingComponent implements OnInit {
  applications = signal<TrackedApplication[]>([]);
  loading = signal(false);
  error = signal('');
  statusFilter = signal<ApplicationStatus | ''>('');
  showAddForm = signal(false);

  // Client-side sort + text search over the loaded list. The status filter
  // above stays server-side (re-queries); these compose on top of its result.
  sort = createSortState<TrackSortField>('company', 'asc', ['company', 'title', 'status']);
  query = signal('');

  visibleApplications = computed(() => {
    let rows = this.applications();
    const q = this.query().trim().toLowerCase();
    if (q) {
      rows = rows.filter(
        (a) => a.company.toLowerCase().includes(q) || a.title.toLowerCase().includes(q),
      );
    }
    const field = this.sort.field();
    return sortItems(rows, (a) => this.sortValue(a, field), this.sort.dir());
  });

  private sortValue(a: TrackedApplication, field: TrackSortField): string | null {
    switch (field) {
      case 'company': return a.company;
      case 'title': return a.title;
      case 'status': return a.status;
      case 'posted': return a.posted_date;
      case 'applied': return a.applied_at;
    }
  }

  onQueryInput(event: Event): void {
    this.query.set((event.target as HTMLInputElement).value);
  }

  newTitle = signal('');
  newCompany = signal('');
  newUrl = signal('');
  newNotes = signal('');
  adding = signal(false);

  leaderboard = signal<BatchResult[]>([]);
  evaluating = signal(false);
  expandedResultId = signal<string | null>(null);

  researchCache = signal<Record<string, CompanyResearch>>({});
  researchingCompany = signal<string | null>(null);
  expandedResearchId = signal<string | null>(null);

  readonly statusOptions: ApplicationStatus[] = [
    'saved',
    'applied',
    'interviewing',
    'offered',
    'accepted',
    'rejected',
  ];

  private readonly destroyRef = inject(DestroyRef);

  constructor(
    private trackingService: TrackingService,
    private researchService: ResearchService,
  ) {}

  ngOnInit(): void {
    this.loadApplications();
  }

  loadApplications(): void {
    this.loading.set(true);
    this.error.set('');
    const filter = this.statusFilter();
    this.trackingService.list(filter || undefined).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (apps) => {
        this.applications.set(apps);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(err.error?.detail || 'Failed to load applications');
        this.loading.set(false);
      },
    });
  }

  onStatusFilterChange(event: Event): void {
    const select = event.target as HTMLSelectElement;
    this.statusFilter.set(select.value as ApplicationStatus | '');
    this.loadApplications();
  }

  toggleAddForm(): void {
    this.showAddForm.update((v) => !v);
    if (!this.showAddForm()) {
      this.resetForm();
    }
  }

  addApplication(): void {
    const title = this.newTitle().trim();
    const company = this.newCompany().trim();
    if (!title && !company) {
      return;
    }
    this.adding.set(true);
    const body: CreateApplicationRequest = {};
    if (title) body.title = title;
    if (company) body.company = company;
    const url = this.newUrl().trim();
    if (url) body.url = url;
    const notes = this.newNotes().trim();
    if (notes) body.notes = notes;

    this.trackingService.create(body).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (app) => {
        this.applications.update((list) => [app, ...list]);
        this.adding.set(false);
        this.showAddForm.set(false);
        this.resetForm();
      },
      error: (err) => {
        this.error.set(err.error?.detail || 'Failed to add application');
        this.adding.set(false);
      },
    });
  }

  updateStatus(app: TrackedApplication, event: Event): void {
    const select = event.target as HTMLSelectElement;
    const newStatus = select.value as ApplicationStatus;
    const body: UpdateApplicationRequest = { status: newStatus };
    this.trackingService.update(app.id, body).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (updated) => {
        this.applications.update((list) =>
          list.map((a) => (a.id === updated.id ? updated : a)),
        );
      },
      error: (err) => {
        this.error.set(err.error?.detail || 'Failed to update status');
        select.value = app.status;
      },
    });
  }

  deleteApplication(id: string): void {
    this.trackingService.delete(id).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: () => {
        this.applications.update((list) => list.filter((a) => a.id !== id));
      },
      error: (err) => {
        this.error.set(err.error?.detail || 'Failed to delete application');
      },
    });
  }

  evaluateAll(): void {
    const apps = this.applications();
    if (apps.length === 0) return;
    this.evaluating.set(true);
    this.leaderboard.set([]);
    const ids = apps.map((a) => a.id);
    this.trackingService.batchEvaluate(ids).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (res) => {
        this.leaderboard.set(res.results);
        this.evaluating.set(false);
      },
      error: (err) => {
        this.error.set(err.error?.detail || 'Batch evaluation failed');
        this.evaluating.set(false);
      },
    });
  }

  toggleExpand(sourceId: string): void {
    this.expandedResultId.update((current) => (current === sourceId ? null : sourceId));
  }

  scoreColor(score: number): string {
    return toScoreColor(score);
  }

  dimensionLabel(dimension: string): string {
    const labels: Record<string, string> = {
      seniority_fit: 'Seniority Fit',
      compensation: 'Compensation',
      growth_potential: 'Growth Potential',
      culture_fit: 'Culture Fit',
      application_strength: 'Application Strength',
      interview_readiness: 'Interview Readiness',
    };
    return labels[dimension] || dimension.replace(/_/g, ' ');
  }

  researchCompany(app: TrackedApplication): void {
    this.researchingCompany.set(app.id);
    this.researchService
      .research({
        company_name: app.company,
        job_description: app.notes || '',
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.researchCache.update((cache) => ({ ...cache, [app.id]: res }));
          this.researchingCompany.set(null);
          this.expandedResearchId.set(app.id);
        },
        error: (err) => {
          this.error.set(err.error?.detail || 'Research failed');
          this.researchingCompany.set(null);
        },
      });
  }

  refreshResearch(app: TrackedApplication): void {
    this.researchingCompany.set(app.id);
    this.researchService
      .refresh({
        company_name: app.company,
        job_description: app.notes || '',
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.researchCache.update((cache) => ({ ...cache, [app.id]: res }));
          this.researchingCompany.set(null);
        },
        error: (err) => {
          this.error.set(err.error?.detail || 'Research refresh failed');
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

  private resetForm(): void {
    this.newTitle.set('');
    this.newCompany.set('');
    this.newUrl.set('');
    this.newNotes.set('');
  }

  onNewTitleInput(event: Event): void {
    this.newTitle.set((event.target as HTMLInputElement).value);
  }

  onNewCompanyInput(event: Event): void {
    this.newCompany.set((event.target as HTMLInputElement).value);
  }

  onNewUrlInput(event: Event): void {
    this.newUrl.set((event.target as HTMLInputElement).value);
  }

  onNewNotesInput(event: Event): void {
    this.newNotes.set((event.target as HTMLTextAreaElement).value);
  }
}
