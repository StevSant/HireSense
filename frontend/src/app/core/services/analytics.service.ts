import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiClient, API_ROUTES } from '@core/api';
import { FunnelMetrics } from '@core/contracts/funnel-metrics.model';
import { MarketIntel } from '@core/contracts/market-intel.model';
import { SkillGap } from '@core/contracts/skill-gap.model';
import { UpskillingPlan } from '@core/contracts/upskilling-plan.model';
import { TargetSalary } from '@core/contracts/target-salary.model';
import { CompBenchmark } from '@core/contracts/comp-benchmark.model';
import { SearchFocus } from '@core/contracts/search-focus.model';

@Injectable({ providedIn: 'root' })
export class AnalyticsService {
  constructor(private api: ApiClient) {}

  funnel(): Observable<FunnelMetrics> {
    return this.api.get<FunnelMetrics>(API_ROUTES.analytics.funnel());
  }

  market(): Observable<MarketIntel> {
    return this.api.get<MarketIntel>(API_ROUTES.analytics.market());
  }

  skillGap(): Observable<SkillGap> {
    return this.api.get<SkillGap>(API_ROUTES.analytics.skillGap());
  }

  upskillingPlan(): Observable<UpskillingPlan> {
    return this.api.get<UpskillingPlan>(API_ROUTES.analytics.upskillingPlan());
  }

  targetSalary(): Observable<TargetSalary> {
    return this.api.get<TargetSalary>(API_ROUTES.analytics.targetSalary());
  }

  comp(): Observable<CompBenchmark> {
    return this.api.get<CompBenchmark>(API_ROUTES.analytics.comp());
  }

  focus(): Observable<SearchFocus> {
    return this.api.get<SearchFocus>(API_ROUTES.analytics.focus());
  }
}
