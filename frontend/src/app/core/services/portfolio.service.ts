import { Injectable, inject } from '@angular/core';
import { HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ApiClient, API_ROUTES } from '@core/api';
import { PortfolioProjectsResponse } from '@core/contracts/portfolio-projects-response.model';
import { PortfolioSyncResult } from '@core/contracts/portfolio-sync-result.model';
import { PortfolioEngagementResponse } from '@core/contracts/portfolio-engagement.model';

@Injectable({ providedIn: 'root' })
export class PortfolioService {
  private api = inject(ApiClient);

  listProjects(limit?: number, offset?: number): Observable<PortfolioProjectsResponse> {
    let params = new HttpParams();
    if (limit != null) params = params.set('limit', limit);
    if (offset != null) params = params.set('offset', offset);
    return this.api.get<PortfolioProjectsResponse>(API_ROUTES.portfolio.projects(), { params });
  }

  sync(): Observable<PortfolioSyncResult> {
    return this.api.post<PortfolioSyncResult>(API_ROUTES.portfolio.sync(), {});
  }

  setMatching(
    id: string,
    include_in_matching: boolean,
  ): Observable<{ include_in_matching: boolean }> {
    return this.api.patch<{ include_in_matching: boolean }>(
      API_ROUTES.portfolio.projectMatching({ id }),
      { include_in_matching },
    );
  }

  engagement(): Observable<PortfolioEngagementResponse> {
    return this.api.get<PortfolioEngagementResponse>(API_ROUTES.portfolio.engagement());
  }
}
