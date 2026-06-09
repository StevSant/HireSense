import { Component, DestroyRef, OnInit, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { AutohuntService } from '../../core/services/autohunt.service';
import { Digest } from './models/digest.model';
import { createSortState } from '../../core/utils/sort-state';
import { parseSortToken } from '../../core/utils/parse-sort-token';
import { CompanyLinkComponent } from '../../core/components/company-link';

type DigestSortField = 'created' | 'count';

@Component({
  selector: 'app-autohunt',
  standalone: true,
  imports: [RouterLink, CompanyLinkComponent],
  templateUrl: './autohunt.component.html',
  styleUrl: './autohunt.component.scss',
})
export class AutohuntComponent implements OnInit {
  private autohunt = inject(AutohuntService);
  private readonly destroyRef = inject(DestroyRef);

  // Digest history is server-paginated (limit), so sorting re-queries.
  historySort = createSortState<DigestSortField>('created', 'desc', []);

  // Latest digest (hero)
  latestDigest = signal<Digest | null>(null);
  latestLoading = signal(false);
  latestError = signal('');

  // Run now
  running = signal(false);
  runError = signal('');

  // History
  history = signal<Digest[]>([]);
  historyLoading = signal(false);
  historyError = signal('');
  expandedId = signal<string | null>(null);

  ngOnInit(): void {
    this.loadLatest();
    this.loadHistory();
  }

  private loadLatest(): void {
    this.latestLoading.set(true);
    this.latestError.set('');
    this.autohunt
      .latest()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (digest) => {
          this.latestDigest.set(digest);
          this.latestLoading.set(false);
        },
        error: (err) => {
          this.latestLoading.set(false);
          this.latestError.set(err?.error?.detail ?? 'Could not load the latest digest.');
        },
      });
  }

  onHistorySort(event: Event): void {
    const parsed = parseSortToken<DigestSortField>((event.target as HTMLSelectElement).value);
    if (parsed) {
      this.historySort.set(parsed.field, parsed.dir);
      this.loadHistory();
    }
  }

  private loadHistory(): void {
    this.historyLoading.set(true);
    this.historyError.set('');
    this.autohunt
      .listRecent(20, this.historySort.token())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (digests) => {
          this.history.set(digests);
          this.historyLoading.set(false);
        },
        error: (err) => {
          this.historyLoading.set(false);
          this.historyError.set(err?.error?.detail ?? 'Could not load digest history.');
        },
      });
  }

  run(): void {
    this.running.set(true);
    this.runError.set('');
    this.autohunt
      .run()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (digest) => {
          this.running.set(false);
          this.latestDigest.set(digest);
          this.loadHistory();
        },
        error: (err) => {
          this.running.set(false);
          this.runError.set(err?.error?.detail ?? 'Could not run a digest.');
        },
      });
  }

  toggleExpanded(id: string): void {
    this.expandedId.set(this.expandedId() === id ? null : id);
  }

  scorePercent(score: number): number {
    return Math.round(score * 100);
  }
}
