import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { DatePipe } from '@angular/common';
import { PortfolioService } from '../../../../core/services/portfolio.service';
import { PortfolioProject } from '../../models/portfolio-project.model';

// Max tech chips shown per card before collapsing the rest into a "+N more" pill.
const MAX_VISIBLE_TECH = 6;

@Component({
  selector: 'app-portfolio-card',
  imports: [DatePipe],
  templateUrl: './portfolio-card.component.html',
  styleUrl: './portfolio-card.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PortfolioCardComponent implements OnInit {
  private service = inject(PortfolioService);
  private destroyRef = inject(DestroyRef);

  readonly pageSize = 12;

  readonly projects = signal<PortfolioProject[]>([]);
  readonly total = signal(0);
  readonly offset = signal(0);
  readonly lastSyncedAt = signal<string | null>(null);
  readonly syncing = signal(false);
  readonly error = signal('');

  readonly showingFrom = computed(() => (this.total() === 0 ? 0 : this.offset() + 1));
  readonly showingTo = computed(() =>
    Math.min(this.offset() + this.projects().length, this.total()),
  );
  readonly canPrev = computed(() => this.offset() > 0);
  readonly canNext = computed(() => this.offset() + this.pageSize < this.total());

  ngOnInit(): void {
    this.load();
  }

  titleOf(project: PortfolioProject): string {
    return this.textOf(project)?.title ?? project.source_key;
  }

  descriptionOf(project: PortfolioProject): string | null {
    return this.textOf(project)?.description ?? null;
  }

  visibleTech(project: PortfolioProject): string[] {
    return project.tech.slice(0, MAX_VISIBLE_TECH);
  }

  extraTechCount(project: PortfolioProject): number {
    return Math.max(0, project.tech.length - MAX_VISIBLE_TECH);
  }

  toggleMatching(project: PortfolioProject, event: Event): void {
    const value = (event.target as HTMLInputElement).checked;
    this.setMatchingFlag(project.id, value); // optimistic
    this.service
      .setMatching(project.id, value)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        error: () => {
          this.setMatchingFlag(project.id, !value); // revert
          this.error.set('Could not update the matching setting');
        },
      });
  }

  private setMatchingFlag(id: string, value: boolean): void {
    this.projects.update((list) =>
      list.map((p) => (p.id === id ? { ...p, include_in_matching: value } : p)),
    );
  }

  prev(): void {
    if (!this.canPrev()) return;
    this.offset.set(Math.max(0, this.offset() - this.pageSize));
    this.load();
  }

  next(): void {
    if (!this.canNext()) return;
    this.offset.set(this.offset() + this.pageSize);
    this.load();
  }

  sync(): void {
    if (this.syncing()) return;
    this.syncing.set(true);
    this.error.set('');
    this.service
      .sync()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.syncing.set(false);
          this.offset.set(0); // re-sync may resize the snapshot; restart at page 1.
          this.load();
        },
        error: (err) => {
          this.syncing.set(false);
          this.error.set(err?.error?.detail ?? 'Portfolio sync failed');
        },
      });
  }

  private textOf(project: PortfolioProject) {
    return project.translations['en'] ?? Object.values(project.translations)[0];
  }

  private load(): void {
    this.service
      .listProjects(this.pageSize, this.offset())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.projects.set(res.projects);
          this.total.set(res.total);
          this.lastSyncedAt.set(res.last_synced_at);
        },
        error: () => this.error.set('Could not load portfolio projects'),
      });
  }
}
