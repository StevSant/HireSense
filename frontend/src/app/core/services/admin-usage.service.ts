import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { BreakdownResponse } from '../../pages/admin/models/breakdown-response.model';
import { DashboardSummary } from '../../pages/admin/models/dashboard-summary.model';
import { RecentCallsFilters } from '../../pages/admin/models/recent-calls-filters.model';
import { RecentCallsResponse } from '../../pages/admin/models/recent-calls-response.model';
import { TimeseriesResponse } from '../../pages/admin/models/timeseries-response.model';

@Injectable({ providedIn: 'root' })
export class AdminUsageService {
  private readonly base = `${environment.apiUrl}/admin/usage`;

  constructor(private http: HttpClient) {}

  summary(): Observable<DashboardSummary> {
    return this.http.get<DashboardSummary>(`${this.base}/summary`);
  }

  timeseries(days = 30): Observable<TimeseriesResponse> {
    return this.http.get<TimeseriesResponse>(`${this.base}/timeseries`, {
      params: new HttpParams().set('days', String(days)),
    });
  }

  breakdown(dimension: 'provider' | 'model' | 'feature', days: number | null = 30): Observable<BreakdownResponse> {
    let params = new HttpParams().set('dimension', dimension);
    if (days !== null) {
      params = params.set('days', String(days));
    }
    return this.http.get<BreakdownResponse>(`${this.base}/breakdown`, { params });
  }

  recentCalls(filters: RecentCallsFilters = {}): Observable<RecentCallsResponse> {
    let params = new HttpParams();
    for (const [k, v] of Object.entries(filters)) {
      if (v !== undefined && v !== null && v !== '') {
        params = params.set(k, String(v));
      }
    }
    return this.http.get<RecentCallsResponse>(`${this.base}/calls`, { params });
  }

  exportCsvUrl(filters: RecentCallsFilters = {}): string {
    const qs = Object.entries(filters)
      .filter(([, v]) => v !== undefined && v !== null && v !== '')
      .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
      .join('&');
    return `${this.base}/export${qs ? `?${qs}` : ''}`;
  }
}
