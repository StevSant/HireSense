import { Injectable } from '@angular/core';
import { HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ApiClient, API_ROUTES } from '@core/api';
import { FetchOpportunitiesResponse } from '@core/contracts/fetch-opportunities-response.model';
import { Opportunity } from '@core/contracts/opportunity.model';
import { PaginatedOpportunitiesResponse } from '@core/contracts/paginated-opportunities-response.model';

@Injectable({ providedIn: 'root' })
export class OpportunitiesService {
  constructor(private api: ApiClient) {}

  list(params: {
    page: number;
    pageSize: number;
    kind?: string;
    topic?: string;
    topics?: string[];
    excludeTopics?: string[];
    country?: string;
    q?: string;
    fundedOnly?: boolean;
    deadlineBefore?: string;
    deadlineAfter?: string;
    hideStale?: boolean;
    matchedOnly?: boolean;
    status?: string;
    sort?: string;
  }): Observable<PaginatedOpportunitiesResponse> {
    let httpParams = new HttpParams()
      .set('page', params.page.toString())
      .set('page_size', params.pageSize.toString());

    if (params.kind) httpParams = httpParams.set('kind', params.kind);
    if (params.topic) httpParams = httpParams.set('topic', params.topic);
    if (params.topics?.length) {
      for (const topic of params.topics) {
        httpParams = httpParams.append('topics', topic);
      }
    }
    if (params.excludeTopics?.length) {
      for (const topic of params.excludeTopics) {
        httpParams = httpParams.append('exclude_topics', topic);
      }
    }
    if (params.country) httpParams = httpParams.set('country', params.country);
    if (params.q) httpParams = httpParams.set('q', params.q);
    if (params.fundedOnly) httpParams = httpParams.set('funded_only', 'true');
    if (params.deadlineBefore)
      httpParams = httpParams.set('deadline_before', params.deadlineBefore);
    if (params.deadlineAfter) httpParams = httpParams.set('deadline_after', params.deadlineAfter);
    if (params.hideStale === false) httpParams = httpParams.set('hide_stale', 'false');
    if (params.matchedOnly === false) httpParams = httpParams.set('matched_only', 'false');
    if (params.matchedOnly === true) httpParams = httpParams.set('matched_only', 'true');
    if (params.status) httpParams = httpParams.set('status', params.status);
    if (params.sort) httpParams = httpParams.set('sort', params.sort);

    return this.api.get<PaginatedOpportunitiesResponse>(API_ROUTES.opportunities.root(), {
      params: httpParams,
    });
  }

  get(id: string): Observable<Opportunity> {
    return this.api.get<Opportunity>(API_ROUTES.opportunities.byId({ id }));
  }

  fetch(): Observable<FetchOpportunitiesResponse> {
    return this.api.post<FetchOpportunitiesResponse>(API_ROUTES.opportunities.fetch(), {});
  }
}
