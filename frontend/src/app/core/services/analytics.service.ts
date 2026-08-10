import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { FunnelMetrics } from '@core/contracts/funnel-metrics.model';
import { MarketIntel } from '@core/contracts/market-intel.model';
import { SkillGap } from '@core/contracts/skill-gap.model';
import { UpskillingPlan } from '@core/contracts/upskilling-plan.model';
import { TargetSalary } from '@core/contracts/target-salary.model';
import { CompBenchmark } from '@core/contracts/comp-benchmark.model';
import { SearchFocus } from '@core/contracts/search-focus.model';

@Injectable({ providedIn: 'root' })
export class AnalyticsService {
  constructor(private http: HttpClient) {}

  funnel(): Observable<FunnelMetrics> {
    return this.http.get<FunnelMetrics>(`${environment.apiUrl}/analytics/funnel`);
  }

  market(): Observable<MarketIntel> {
    return this.http.get<MarketIntel>(`${environment.apiUrl}/analytics/market`);
  }

  skillGap(): Observable<SkillGap> {
    return this.http.get<SkillGap>(`${environment.apiUrl}/analytics/skill-gap`);
  }

  upskillingPlan(): Observable<UpskillingPlan> {
    return this.http.get<UpskillingPlan>(`${environment.apiUrl}/analytics/upskilling-plan`);
  }

  targetSalary(): Observable<TargetSalary> {
    return this.http.get<TargetSalary>(`${environment.apiUrl}/analytics/target-salary`);
  }

  comp(): Observable<CompBenchmark> {
    return this.http.get<CompBenchmark>(`${environment.apiUrl}/analytics/comp`);
  }

  focus(): Observable<SearchFocus> {
    return this.http.get<SearchFocus>(`${environment.apiUrl}/analytics/focus`);
  }
}
