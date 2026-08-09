import { DatePipe } from '@angular/common';
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
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ApplicationsService } from '../../../../core/services/applications.service';
import { CoverLetterLibraryItem } from '../../../applications/models/cover-letter-library-item.model';
import { createSortState } from '../../../../core/utils/sort-state';
import { sortItems } from '../../../../core/utils/sort-items';
import { parseSortToken } from '../../../../core/utils/parse-sort-token';
import { PaginatorComponent } from '../../../../core/components/paginator';

type LibrarySortField = 'created' | 'company' | 'title';

// Letters are tall rows (each carries a preview), so page smaller than a table.
const DEFAULT_PAGE_SIZE = 10;
const PAGE_SIZE_OPTIONS = [10, 25, 50];

@Component({
  selector: 'app-cover-letter-library',
  standalone: true,
  imports: [FormsModule, RouterLink, DatePipe, PaginatorComponent],
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

  // Client-side paging over the searched/sorted library.
  page = signal(1);
  pageSize = signal(DEFAULT_PAGE_SIZE);

  // Server total when the load walk stopped short of it (environment.listMaxItems).
  truncatedAt = signal<number | null>(null);

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

  totalPages = computed(() => Math.max(1, Math.ceil(this.filtered().length / this.pageSize())));

  // Clamped so narrowing the search can't strand the user past the last page.
  currentPage = computed(() => Math.min(this.page(), this.totalPages()));

  visible = computed(() => {
    const start = (this.currentPage() - 1) * this.pageSize();
    return this.filtered().slice(start, start + this.pageSize());
  });

  readonly pageSizeOptions = PAGE_SIZE_OPTIONS;

  onQueryChange(value: string): void {
    this.query.set(value);
    this.page.set(1);
  }

  onPageChange(page: number): void {
    this.page.set(page);
  }

  onPageSizeChange(size: number): void {
    this.pageSize.set(size);
    this.page.set(1);
  }

  private sortValue(l: CoverLetterLibraryItem, field: LibrarySortField): string | null {
    switch (field) {
      case 'created':
        return l.created_at;
      case 'company':
        return l.company;
      case 'title':
        return l.title;
    }
  }

  onSortSelect(event: Event): void {
    const parsed = parseSortToken<LibrarySortField>((event.target as HTMLSelectElement).value);
    if (parsed) this.sort.set(parsed.field, parsed.dir);
  }

  ngOnInit(): void {
    this.service
      .listAllCoverLetters()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: ({ items, total }) => {
          this.letters.set(items);
          this.truncatedAt.set(items.length < total ? total : null);
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
