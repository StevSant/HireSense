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
import { PortfolioProject } from '@core/contracts/portfolio-project.model';
import { PaginatorComponent } from '../../../../core/components/paginator';

// Max tech chips shown per card before collapsing the rest into a "+N more" pill.
const MAX_VISIBLE_TECH = 6;

// Project cards are tall, so the page sizes stay well below the list defaults.
const PAGE_SIZE_OPTIONS = [12, 24, 48];

@Component({
  selector: 'app-portfolio-card',
  imports: [DatePipe, PaginatorComponent],
  templateUrl: './portfolio-card.component.html',
  styleUrl: './portfolio-card.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PortfolioCardComponent implements OnInit {
  private service = inject(PortfolioService);
  private destroyRef = inject(DestroyRef);

  readonly pageSize = signal(PAGE_SIZE_OPTIONS[0]);
  readonly pageSizeOptions = PAGE_SIZE_OPTIONS;

  readonly projects = signal<PortfolioProject[]>([]);
  readonly total = signal(0);
  readonly offset = signal(0);
  readonly lastSyncedAt = signal<string | null>(null);
  readonly syncing = signal(false);
  readonly error = signal('');

  // The shared paginator speaks pages; this endpoint speaks offsets.
  readonly page = computed(() => Math.floor(this.offset() / this.pageSize()) + 1);
  readonly totalPages = computed(() => Math.max(1, Math.ceil(this.total() / this.pageSize())));

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

  onPageChange(page: number): void {
    this.offset.set(Math.max(0, (page - 1) * this.pageSize()));
    this.load();
  }

  onPageSizeChange(size: number): void {
    this.pageSize.set(size);
    this.offset.set(0);
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
      .listProjects(this.pageSize(), this.offset())
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
