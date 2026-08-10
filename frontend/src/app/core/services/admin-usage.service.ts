import { Injectable } from '@angular/core';
import { HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

import { ApiClient, API_ROUTES } from '@core/api';
import { BreakdownResponse } from '@core/contracts/breakdown-response.model';
import { DashboardSummary } from '@core/contracts/dashboard-summary.model';
import { RecentCallsFilters } from '@core/contracts/recent-calls-filters.model';
import { RecentCallsResponse } from '@core/contracts/recent-calls-response.model';
import { TimeseriesResponse } from '@core/contracts/timeseries-response.model';

@Injectable({ providedIn: 'root' })
export class AdminUsageService {
  constructor(private api: ApiClient) {}

  summary(): Observable<DashboardSummary> {
    return this.api.get<DashboardSummary>(API_ROUTES.admin.usage.summary());
  }

  timeseries(days = 30): Observable<TimeseriesResponse> {
    return this.api.get<TimeseriesResponse>(API_ROUTES.admin.usage.timeseries(), {
      params: new HttpParams().set('days', String(days)),
    });
  }

  breakdown(
    dimension: 'provider' | 'model' | 'feature',
    days: number | null = 30,
  ): Observable<BreakdownResponse> {
    let params = new HttpParams().set('dimension', dimension);
    if (days !== null) {
      params = params.set('days', String(days));
    }
    return this.api.get<BreakdownResponse>(API_ROUTES.admin.usage.breakdown(), { params });
  }

  recentCalls(filters: RecentCallsFilters = {}): Observable<RecentCallsResponse> {
    let params = new HttpParams();
    for (const [k, v] of Object.entries(filters)) {
      if (v !== undefined && v !== null && v !== '') {
        params = params.set(k, String(v));
      }
    }
    return this.api.get<RecentCallsResponse>(API_ROUTES.admin.usage.calls(), { params });
  }

  exportCsvUrl(filters: RecentCallsFilters = {}): string {
    const qs = Object.entries(filters)
      .filter(([, v]) => v !== undefined && v !== null && v !== '')
      .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
      .join('&');
    return `${this.api.url(API_ROUTES.admin.usage.exportCsv())}${qs ? `?${qs}` : ''}`;
  }
}
