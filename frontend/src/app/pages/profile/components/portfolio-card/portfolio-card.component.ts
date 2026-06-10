import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { DatePipe } from '@angular/common';
import { PortfolioService } from '../../../../core/services/portfolio.service';
import { PortfolioProject } from '../../models/portfolio-project.model';

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

  readonly projects = signal<PortfolioProject[]>([]);
  readonly lastSyncedAt = signal<string | null>(null);
  readonly syncing = signal(false);
  readonly error = signal('');

  ngOnInit(): void {
    this.load();
  }

  titleOf(project: PortfolioProject): string {
    const text = project.translations['en'] ?? Object.values(project.translations)[0];
    return text?.title ?? project.source_key;
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
          this.load();
        },
        error: (err) => {
          this.syncing.set(false);
          this.error.set(err?.error?.detail ?? 'Portfolio sync failed');
        },
      });
  }

  private load(): void {
    this.service
      .listProjects()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.projects.set(res.projects);
          this.lastSyncedAt.set(res.last_synced_at);
        },
        error: () => this.error.set('Could not load portfolio projects'),
      });
  }
}
