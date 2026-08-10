import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

import { PaginatorComponent } from '@core/components/paginator';
import { SortableHeaderDirective } from '@core/components/sortable-header';
import { AdminUsageStore, Dimension } from './admin-usage.store';

/** Mirrors the backend's `limit` bounds for /admin/usage/calls (max 500). */
const CALLS_PAGE_SIZE_OPTIONS = [50, 100, 250, 500];

/**
 * Admin → LLM usage dashboard.
 *
 * A view over AdminUsageStore: every signal below is the store's own signal
 * re-exposed under the name the template already used. The bar-chart geometry
 * helpers stay here — they are pure view maths over values the template
 * already holds, and nothing but the SVG needs them.
 */
@Component({
  selector: 'app-admin-usage',
  standalone: true,
  imports: [CommonModule, FormsModule, SortableHeaderDirective, PaginatorComponent],
  providers: [AdminUsageStore],
  templateUrl: './admin-usage.component.html',
  styleUrl: './admin-usage.component.scss',
})
export class AdminUsageComponent implements OnInit {
  private store = inject(AdminUsageStore);

  loading = this.store.loading;
  error = this.store.error;

  summary = this.store.summary;
  timeseries = this.store.timeseries;
  breakdown = this.store.breakdown;
  recent = this.store.recent;

  rangeDays = this.store.rangeDays;
  dimension = this.store.dimension;

  filterProvider = this.store.filterProvider;
  filterModel = this.store.filterModel;
  filterFeature = this.store.filterFeature;
  recentLimit = this.store.recentLimit;

  maxBucketCost = this.store.maxBucketCost;
  maxBreakdownCost = this.store.maxBreakdownCost;

  breakdownSort = this.store.breakdownSort;
  visibleBuckets = this.store.visibleBuckets;

  callsSort = this.store.callsSort;
  callsPage = this.store.callsPage;
  callsTotal = this.store.callsTotal;
  callsTotalPages = this.store.callsTotalPages;

  // The backend caps a usage page at 500.
  readonly callsPageSizeOptions = CALLS_PAGE_SIZE_OPTIONS;

  ngOnInit(): void {
    this.store.init();
  }

  refresh(): void {
    this.store.refresh();
  }

  setRange(days: number): void {
    this.store.setRange(days);
  }

  setDimension(d: Dimension): void {
    this.store.setDimension(d);
  }

  loadRecent(): void {
    this.store.loadRecent();
  }

  reloadRecent(): void {
    this.store.reloadRecent();
  }

  onCallsPageChange(page: number): void {
    this.store.goToCallsPage(page);
  }

  onCallsPageSizeChange(size: number): void {
    this.store.setCallsPageSize(size);
  }

  exportCsv(): void {
    const url = this.store.exportCsvUrl();
    // The CSV endpoint is auth-gated. Session auth is a same-origin httpOnly
    // cookie, so the browser attaches it automatically to this navigation — no
    // interceptor needed (unlike the old bearer header, which couldn't ride a
    // plain window.open).
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
