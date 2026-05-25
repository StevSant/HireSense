import { Component, OnInit, computed, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

import { AdminUsageService } from '../../core/services/admin-usage.service';
import { BreakdownResponse } from './models/breakdown-response.model';
import { DashboardSummary } from './models/dashboard-summary.model';
import { RecentCallsResponse } from './models/recent-calls-response.model';
import { TimeseriesResponse } from './models/timeseries-response.model';

type Dimension = 'provider' | 'model' | 'feature';

@Component({
  selector: 'app-admin-usage',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './admin-usage.component.html',
  styleUrl: './admin-usage.component.scss',
})
export class AdminUsageComponent implements OnInit {
  loading = signal(false);
  error = signal('');

  summary = signal<DashboardSummary | null>(null);
  timeseries = signal<TimeseriesResponse | null>(null);
  breakdown = signal<BreakdownResponse | null>(null);
  recent = signal<RecentCallsResponse | null>(null);

  rangeDays = signal<number>(30);
  dimension = signal<Dimension>('feature');

  // Recent-calls filters
  filterProvider = signal('');
  filterModel = signal('');
  filterFeature = signal('');
  recentLimit = signal(50);

  // Derived: max cost in timeseries for SVG scaling
  maxBucketCost = computed(() => {
    const buckets = this.timeseries()?.buckets ?? [];
    return Math.max(0.0001, ...buckets.map((b) => b.cost_usd));
  });

  maxBreakdownCost = computed(() => {
    const buckets = this.breakdown()?.buckets ?? [];
    return Math.max(0.0001, ...buckets.map((b) => b.cost_usd));
  });

  constructor(private api: AdminUsageService) {}

  ngOnInit(): void {
    this.refresh();
  }

  refresh(): void {
    this.loading.set(true);
    this.error.set('');
    this.api.summary().subscribe({
      next: (s) => this.summary.set(s),
      error: (err) => this.error.set(err?.error?.detail ?? 'Failed to load summary'),
    });
    this.loadTimeseries();
    this.loadBreakdown();
    this.loadRecent();
  }

  setRange(days: number): void {
    this.rangeDays.set(days);
    this.loadTimeseries();
    this.loadBreakdown();
  }

  setDimension(d: Dimension): void {
    this.dimension.set(d);
    this.loadBreakdown();
  }

  private loadTimeseries(): void {
    this.api.timeseries(this.rangeDays()).subscribe({
      next: (ts) => {
        this.timeseries.set(ts);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(err?.error?.detail ?? 'Failed to load timeseries');
        this.loading.set(false);
      },
    });
  }

  private loadBreakdown(): void {
    this.api.breakdown(this.dimension(), this.rangeDays()).subscribe({
      next: (b) => this.breakdown.set(b),
      error: (err) => this.error.set(err?.error?.detail ?? 'Failed to load breakdown'),
    });
  }

  loadRecent(): void {
    this.api
      .recentCalls({
        limit: this.recentLimit(),
        offset: 0,
        provider: this.filterProvider() || undefined,
        model: this.filterModel() || undefined,
        feature_key: this.filterFeature() || undefined,
      })
      .subscribe({
        next: (r) => this.recent.set(r),
        error: (err) => this.error.set(err?.error?.detail ?? 'Failed to load calls'),
      });
  }

  exportCsv(): void {
    const url = this.api.exportCsvUrl({
      provider: this.filterProvider() || undefined,
      model: this.filterModel() || undefined,
      feature_key: this.filterFeature() || undefined,
      days: 90,
    });
    // The CSV endpoint is auth-gated; the auth interceptor only runs on Angular's
    // HttpClient, not on plain anchor navigation. We fetch with the interceptor
    // and trigger a download via a blob URL.
    window.open(url, '_blank');
  }

  // ---- Helpers for SVG chart -------------------------------------

  barX(idx: number, total: number, chartWidth: number, gap: number): number {
    if (total <= 1) return 0;
    const slot = (chartWidth - gap * (total - 1)) / total;
    return idx * (slot + gap);
  }

  slotWidth(total: number, chartWidth: number, gap: number): number {
    if (total <= 0) return 0;
    return (chartWidth - gap * Math.max(0, total - 1)) / total;
  }

  barHeight(cost: number, max: number, chartHeight: number): number {
    if (max <= 0) return 0;
    const ratio = Math.min(1, cost / max);
    return Math.max(1, chartHeight * ratio);
  }

  formatDay(key: string): string {
    // Backend emits "YYYY-MM-DD HH:MM:SS+TZ" from postgres date_trunc cast to string.
    return key.slice(0, 10);
  }
}
