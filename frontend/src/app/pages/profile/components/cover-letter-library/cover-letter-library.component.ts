import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ApplicationsService } from '../../../../core/services/applications.service';
import { CoverLetterLibraryItem } from '../../../applications/models/cover-letter-library-item.model';
import { createSortState } from '../../../../core/utils/sort-state';
import { sortItems } from '../../../../core/utils/sort-items';
import { parseSortToken } from '../../../../core/utils/parse-sort-token';

type LibrarySortField = 'created' | 'company' | 'title';

@Component({
  selector: 'app-cover-letter-library',
  standalone: true,
  imports: [FormsModule, RouterLink, DatePipe],
  templateUrl: './cover-letter-library.component.html',
  styleUrl: './cover-letter-library.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CoverLetterLibraryComponent implements OnInit {
  private service = inject(ApplicationsService);
  private readonly destroyRef = inject(DestroyRef);

  letters = signal<CoverLetterLibraryItem[]>([]);
  loading = signal(true);
  error = signal('');
  query = signal('');
  expandedId = signal<string | null>(null);
  copiedId = signal<string | null>(null);

  sort = createSortState<LibrarySortField>('created', 'desc', ['company', 'title']);

  filtered = computed(() => {
    const q = this.query().trim().toLowerCase();
    let all = this.letters();
    if (q) {
      all = all.filter(
        (l) =>
          l.company.toLowerCase().includes(q) ||
          l.title.toLowerCase().includes(q) ||
          l.body.toLowerCase().includes(q),
      );
    }
    const field = this.sort.field();
    return sortItems(all, (l) => this.sortValue(l, field), this.sort.dir());
  });

  private sortValue(l: CoverLetterLibraryItem, field: LibrarySortField): string | null {
    switch (field) {
      case 'created': return l.created_at;
      case 'company': return l.company;
      case 'title': return l.title;
    }
  }

  onSortSelect(event: Event): void {
    const parsed = parseSortToken<LibrarySortField>((event.target as HTMLSelectElement).value);
    if (parsed) this.sort.set(parsed.field, parsed.dir);
  }

  ngOnInit(): void {
    this.service.listAllCoverLetters().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (list) => {
        this.letters.set(list);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(err?.error?.detail ?? 'Could not load cover letters');
        this.loading.set(false);
      },
    });
  }

  toggle(id: string): void {
    this.expandedId.update((current) => (current === id ? null : id));
  }

  preview(body: string): string {
    const flat = body.replace(/\s+/g, ' ').trim();
    return flat.length > 220 ? `${flat.slice(0, 220)}…` : flat;
  }

  async copy(item: CoverLetterLibraryItem, event: Event): Promise<void> {
    event.stopPropagation();
    try {
      await navigator.clipboard.writeText(item.body);
      this.copiedId.set(item.id);
      setTimeout(() => {
        if (this.copiedId() === item.id) this.copiedId.set(null);
      }, 1800);
    } catch {
      this.error.set('Clipboard access denied — copy manually.');
    }
  }
}
