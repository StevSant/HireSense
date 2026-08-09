import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { CommonModule, DatePipe, PercentPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { OpportunitiesService } from '../../core/services/opportunities.service';
import { SortableHeaderDirective } from '../../core/components/sortable-header';
import { createSortState } from '../../core/utils/sort-state';
import { PaginatorComponent } from '../../core/components/paginator';
import { FetchOpportunitiesResponse } from './models/fetch-opportunities-response.model';
import { Opportunity } from './models/opportunity.model';

type OppSortField = 'match' | 'title' | 'country' | 'language' | 'cost' | 'when' | 'source';

@Component({
  selector: 'app-opportunities',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    DatePipe,
    PercentPipe,
    PaginatorComponent,
    SortableHeaderDirective,
  ],
  templateUrl: './opportunities.component.html',
  styleUrl: './opportunities.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class OpportunitiesComponent implements OnInit {
  private opportunities = inject(OpportunitiesService);
  private destroyRef = inject(DestroyRef);

  readonly items = signal<Opportunity[]>([]);
  readonly total = signal(0);
  readonly loading = signal(false);
  readonly fetchRunning = signal(false);
  readonly error = signal<string | null>(null);
  readonly fetchSummary = signal<FetchOpportunitiesResponse | null>(null);

  readonly page = signal(1);
  readonly pageSize = signal(20);

  sort = createSortState<OppSortField>('match', 'desc', ['title', 'country', 'language', 'source']);

  kind = '';
  topic = '';
  excludeTopics = 'php';
  country = '';
  q = '';
  fundedOnly = false;
  matchedOnly = true;
  hideStale = true;
  status = 'open';

  readonly hasFilters = computed(
    () =>
      !!this.kind ||
      !!this.topic.trim() ||
      this.excludeTopics.trim() !== 'php' ||
      !!this.country.trim() ||
      !!this.q.trim() ||
      this.fundedOnly ||
      !this.matchedOnly ||
      !this.hideStale ||
      this.status !== 'open',
  );

  readonly totalPages = computed(() => Math.max(1, Math.ceil(this.total() / this.pageSize())));

  ngOnInit(): void {
    this.load();
  }

  private splitList(value: string): string[] | undefined {
    const parts = value
      .split(',')
      .map((part) => part.trim())
      .filter(Boolean);
    return parts.length ? parts : undefined;
  }

  load(page = this.page()): void {
    this.loading.set(true);
    this.error.set(null);
    this.page.set(page);
    this.opportunities
      .list({
        page,
        pageSize: this.pageSize(),
        kind: this.kind || undefined,
        topics: this.splitList(this.topic),
        excludeTopics: this.splitList(this.excludeTopics),
        country: this.country.trim() || undefined,
        q: this.q.trim() || undefined,
        fundedOnly: this.fundedOnly,
        hideStale: this.hideStale,
        matchedOnly: this.matchedOnly,
        status: this.status || undefined,
        sort: this.sort.token(),
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (response) => {
          this.items.set(response.items);
          this.total.set(response.total);
          this.loading.set(false);
        },
        error: () => {
          this.error.set('Could not load opportunities.');
          this.loading.set(false);
        },
      });
  }

  runFetch(): void {
    this.fetchRunning.set(true);
    this.fetchSummary.set(null);
    this.opportunities
      .fetch()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (summary) => {
          this.fetchSummary.set(summary);
          this.fetchRunning.set(false);
          this.load(1);
        },
        error: () => {
          this.error.set('Could not refresh opportunities.');
          this.fetchRunning.set(false);
        },
      });
  }

  applyFilters(): void {
    this.load(1);
  }

  clearFilters(): void {
    this.kind = '';
    this.topic = '';
    this.excludeTopics = 'php';
    this.country = '';
    this.q = '';
    this.fundedOnly = false;
    this.matchedOnly = true;
    this.hideStale = true;
    this.status = 'open';
    this.sort.set('match', 'desc');
    this.load(1);
  }

  onToggleChange(): void {
    this.load(1);
  }

  onSorted(): void {
    this.load(1);
  }

  onPageChange(page: number): void {
    this.load(page);
  }

  onPageSizeChange(size: number): void {
    this.pageSize.set(size);
    this.load(1);
  }

  deadlineLabel(item: Opportunity): string | null {
    return item.application_deadline ?? item.cfp_deadline ?? null;
  }

  deadlinePrefix(item: Opportunity): string {
    if (item.application_deadline) return 'Apply due';
    if (item.cfp_deadline) return 'CFP due';
    return 'Due';
  }

  applyActionLabel(item: Opportunity): string {
    if (item.kind === 'cfp') return 'Submit talk';
    if (item.kind === 'grant' || item.kind === 'fellowship') return 'Apply';
    if (item.application_deadline || item.funding) return 'Apply';
    return 'Apply';
  }

  organizationLabel(item: Opportunity): string | null {
    const org = (item.organization || '').trim();
    if (!org || org.toLowerCase() === item.title.toLowerCase()) {
      return null;
    }
    return org;
  }

  countryLabel(item: Opportunity): string {
    if (item.source_metadata?.['online']) return 'Online';
    return item.country?.trim() || '—';
  }

  cityLabel(item: Opportunity): string | null {
    if (item.source_metadata?.['online']) return null;
    return item.city?.trim() || null;
  }

  languageLabel(item: Opportunity): string {
    const locales = item.source_metadata?.['locales'];
    if (typeof locales === 'string' && locales.trim()) return locales.trim();
    if (Array.isArray(locales) && locales.length) {
      return locales.map(String).filter(Boolean).join(', ');
    }
    return '—';
  }

  costLabel(item: Opportunity): string {
    const stored = item.source_metadata?.['attendance_cost'];
    // Prefer explicit stored labels, but re-infer when older ingest wrote "Unknown".
    if (typeof stored === 'string' && stored.trim() && stored.trim() !== 'Unknown') {
      return stored.trim();
    }
    if (item.funding?.trim() || item.kind === 'grant' || item.kind === 'fellowship') {
      return 'Funded';
    }
    const blob =
      `${item.title} ${item.description} ${item.funding ?? ''} ${item.url} ${item.apply_url ?? ''}`.toLowerCase();
    if (
      /\bfree(\s+to\s+attend)?\b|\bno[- ]?fee\b|\bgratis\b|\bcomplimentary\b|\bfree[- ]?(admission|entry|event|conference)/.test(
        blob,
      )
    ) {
      return 'Free';
    }
    if (
      /eventbrite\.|ti\.to\/|ticketailor\.|\/tickets?\b|buy[-_]?ticket|early[- ]bird|registration\s+fee|from\s+\$\d|\$\d/.test(
        blob,
      )
    ) {
      return 'Paid';
    }
    if (['conference', 'cfp', 'event', 'summer_school'].includes(item.kind)) {
      return 'Likely paid';
    }
    return 'Unknown';
  }

  costClass(item: Opportunity): string {
    const label = this.costLabel(item);
    if (label === 'Funded' || label === 'Free') return 'cost-good';
    if (label === 'Paid' || label === 'Likely paid') return 'cost-paid';
    return 'cost-unknown';
  }

  kindLabel(kind: string): string {
    if (kind === 'cfp') return 'Call for papers';
    return kind.replaceAll('_', ' ');
  }

  kindTitle(kind: string): string {
    if (kind === 'cfp') {
      return 'This conference currently accepts speaker/paper submissions (CFP).';
    }
    return kind.replaceAll('_', ' ');
  }

  costHint(item: Opportunity): string {
    const label = this.costLabel(item);
    if (label === 'Likely paid') {
      return 'Source has no fee field; industry conferences usually charge attendance.';
    }
    if (label === 'Unknown') {
      return 'Fee not published in the source data.';
    }
    if (label === 'Paid') {
      return 'Inferred from ticket/registration URL or wording.';
    }
    if (label === 'Free') {
      return 'Marked free from title/description/URL signals.';
    }
    if (label === 'Funded') {
      return 'Travel/lodging or grant-style support is indicated.';
    }
    return label;
  }

  scoreBadgeClass(score: number | null | undefined): string {
    if (score == null) return 'score-na';
    if (score >= 0.7) return 'score-high';
    if (score >= 0.4) return 'score-mid';
    return 'score-low';
  }
}
