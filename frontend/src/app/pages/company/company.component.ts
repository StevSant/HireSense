import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, computed, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { forkJoin } from 'rxjs';
import { IngestionService } from '../../core/services/ingestion.service';
import { ApplicationsService } from '../../core/services/applications.service';
import { NormalizedJob } from '../ingestion/models/normalized-job.model';
import { FeedbackKind } from '../ingestion/models/feedback-kind.model';
import { FeedbackControlsComponent } from '../ingestion/components/feedback-controls/feedback-controls.component';
import { SortableHeaderDirective } from '../../core/components/sortable-header';
import { createSortState } from '../../core/utils/sort-state';
import { scoreClass } from '../../core/utils/score-class';

const PERCENT = 100;
/** A single company's open-job count is small once filtered — one large page is enough. */
const COMPANY_PAGE_SIZE = 100;
const TOP_LOCATIONS = 4;

type SortField = 'match' | 'title' | 'location' | 'source' | 'posted';

@Component({
  selector: 'app-company',
  standalone: true,
  imports: [RouterLink, DatePipe, FeedbackControlsComponent, SortableHeaderDirective],
  templateUrl: './company.component.html',
  styleUrl: './company.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CompanyComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private ingestion = inject(IngestionService);
  private applications = inject(ApplicationsService);
  private destroyRef = inject(DestroyRef);

  scoreClass = scoreClass;

  company = signal('');
  jobs = signal<NormalizedJob[]>([]);
  loading = signal(true);
  error = signal(false);

  // The id of the job currently being tracked, so its row can show progress.
  trackingJobId = signal<string | null>(null);
  // Jobs the user marked "not interested" this session — dimmed locally.
  dimmedJobIds = signal<Set<string>>(new Set<string>());

  // Client-side sort — all jobs load in one page, so column clicks reorder in
  // place with no backend refetch (default Match descending).
  sort = createSortState<SortField>('match', 'desc', ['title', 'location', 'source']);

  scoredCount = computed(() => this.jobs().filter((j) => this.displayScore(j) !== null).length);

  avgMatchPct = computed<number | null>(() => {
    const scored = this.jobs().map((j) => this.displayScore(j)).filter((s): s is number => s !== null);
    if (!scored.length) return null;
    const sum = scored.reduce((acc, s) => acc + s, 0);
    return Math.round((sum / scored.length) * PERCENT);
  });

  sortedJobs = computed<NormalizedJob[]>(() => {
    const field = this.sort.field();
    const factor = this.sort.dir() === 'asc' ? 1 : -1;
    return [...this.jobs()].sort((a, b) => factor * this.compare(a, b, field));
  });

  topLocations = computed<{ label: string; count: number }[]>(() => {
    const counts = new Map<string, number>();
    for (const j of this.jobs()) {
      const loc = j.location?.trim();
      if (loc) counts.set(loc, (counts.get(loc) ?? 0) + 1);
    }
    return [...counts.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, TOP_LOCATIONS)
      .map(([label, count]) => ({ label, count }));
  });

  ngOnInit(): void {
    const name = this.route.snapshot.paramMap.get('name') ?? '';
    this.company.set(name);
    if (!name) {
      this.error.set(true);
      this.loading.set(false);
      return;
    }
    forkJoin({
      boards: this.ingestion.queryJobs('boards', 1, COMPANY_PAGE_SIZE, { company: name, sort: 'match_desc' }),
      portals: this.ingestion.queryJobs('portals', 1, COMPANY_PAGE_SIZE, { company: name, sort: 'match_desc' }),
    })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: ({ boards, portals }) => {
          const byId = new Map<string, NormalizedJob>();
          for (const j of [...boards.jobs, ...portals.jobs]) byId.set(j.id, j);
          this.jobs.set([...byId.values()]);
          this.loading.set(false);
        },
        error: () => {
          this.error.set(true);
          this.loading.set(false);
        },
      });
  }

  // Prefer the Tier-1 LLM quick score (the value the ingestion table shows),
  // falling back to the persisted heuristic blend. Keeps this list in sync with
  // the ingestion table instead of diverging on the lower heuristic %.
  private displayScore(job: NormalizedJob): number | null {
    return job.llm_score ?? job.match_score;
  }

  private compare(a: NormalizedJob, b: NormalizedJob, field: SortField): number {
    switch (field) {
      case 'match':
        return (this.displayScore(a) ?? -1) - (this.displayScore(b) ?? -1);
      case 'title':
        return (a.title ?? '').localeCompare(b.title ?? '');
      case 'location':
        return (a.location ?? '').localeCompare(b.location ?? '');
      case 'source':
        return (a.source ?? '').localeCompare(b.source ?? '');
      case 'posted':
        return (a.posted_date ?? '').localeCompare(b.posted_date ?? '');
    }
  }

  matchPct(job: NormalizedJob): number | null {
    const score = this.displayScore(job);
    return score === null ? null : Math.round(score * PERCENT);
  }

  scoreBadgeClass(job: NormalizedJob): string {
    return scoreClass(this.displayScore(job) ?? 0);
  }

  openJob(job: NormalizedJob): void {
    this.router.navigate(['/dashboard/job', job.id]);
  }

  isTracked(jobId: string): boolean {
    return this.ingestion.trackedJobIds().has(jobId);
  }

  isTracking(jobId: string): boolean {
    return this.trackingJobId() === jobId;
  }

  isDimmed(jobId: string): boolean {
    return this.dimmedJobIds().has(jobId);
  }

  trackJob(jobId: string): void {
    if (this.trackingJobId() !== null || this.isTracked(jobId)) return;
    this.trackingJobId.set(jobId);
    this.applications.createFromJob(jobId).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (agg) => {
        this.ingestion.markTracked(jobId);
        this.trackingJobId.set(null);
        this.router.navigate(['/dashboard/applications', agg.id]);
      },
      error: (err) => {
        this.trackingJobId.set(null);
        if (err?.status === 409) {
          this.ingestion.markTracked(jobId);
          this.router.navigate(['/dashboard/applications']);
        }
      },
    });
  }

  onFeedback(jobId: string, kind: FeedbackKind): void {
    if (kind === 'not_interested') {
      const next = new Set(this.dimmedJobIds());
      next.add(jobId);
      this.dimmedJobIds.set(next);
    }
  }
}
