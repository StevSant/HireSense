import { Injectable, inject, signal } from '@angular/core';
import { HttpParams } from '@angular/common/http';
import { Observable, tap } from 'rxjs';
import { ApiClient, API_ROUTES } from '@core/api';
import { FetchResponse } from '@core/contracts/fetch-response.model';
import { IngestionRunDetail, IngestionRunSummary } from '@core/contracts/ingestion-run.model';
import { JobAnalysis } from '@core/contracts/job-analysis.model';
import { JobFilters } from '@core/contracts/job-filters.model';
import { JobHistoryEvent } from '@core/contracts/job-history-event.model';
import { NormalizedJob } from '@core/contracts/normalized-job.model';
import { RevalidationStatus } from '@core/contracts/revalidation-status.model';
import { PaginatedJobsResponse } from '@core/contracts/paginated-jobs-response.model';
import { PortalEntry } from '@core/contracts/portal-entry.model';
import { ScanPortalsRequest } from '@core/contracts/scan-portals-request.model';
import { ScanResult } from '@core/contracts/scan-result.model';
import { SourcesHealthResponse, SourcesResponse } from '@core/contracts/source-capability.model';

@Injectable({ providedIn: 'root' })
export class IngestionService {
  readonly trackedJobIds = signal<Set<string>>(new Set());
  // Deep-analysis results cached by job id. Lives in the (root) service so it
  // survives the detail panel being destroyed on close — re-opening a job
  // shows its analysis instantly without refetching.
  readonly jobAnalysisCache = signal<Record<string, JobAnalysis>>({});

  private readonly api = inject(ApiClient);

  fetchJobs(): Observable<FetchResponse> {
    return this.api.post<FetchResponse>(API_ROUTES.ingestion.fetch(), {});
  }

  // "Check closed": probe the given (visible) jobs synchronously for an
  // immediate result, while the server also kicks off a full-corpus background
  // sweep for the rest. `closed_ids` are the jobs closed in the sync pass.
  revalidate(
    jobIds: string[],
  ): Observable<{ started: boolean; closed: number; closed_ids: string[] }> {
    return this.api.post<{ started: boolean; closed: number; closed_ids: string[] }>(
      API_ROUTES.ingestion.revalidate(),
      { job_ids: jobIds },
    );
  }

  // Progress of the background sweep started by revalidate(). Cheap enough to
  // poll: the backend answers from in-memory counters without touching the DB.
  revalidationStatus(): Observable<RevalidationStatus> {
    return this.api.get<RevalidationStatus>(API_ROUTES.ingestion.revalidateStatus());
  }

  queryJobs(
    tab: 'boards' | 'portals',
    page: number,
    pageSize: number,
    filters: JobFilters = {},
    includeClosed = false,
    // Pure reorder/pagination passes rescore=false so the server keeps the full
    // skill+ANN+min_score pipeline (set/order unchanged) but defers the blocking
    // LLM call, reusing cached scores (#76). Defaults to true (full scoring).
    rescore = true,
    // Reveal jobs flagged low-quality / spam (hidden by default).
    includeLowQuality = false,
  ): Observable<PaginatedJobsResponse> {
    let params = new HttpParams()
      .set('tab', tab)
      .set('page', page.toString())
      .set('page_size', pageSize.toString());

    if (includeClosed) params = params.set('include_closed', 'true');
    if (!rescore) params = params.set('rescore', 'false');
    if (includeLowQuality) params = params.set('include_low_quality', 'true');

    if (filters.source) params = params.set('source', filters.source);
    if (filters.company) params = params.set('company', filters.company);
    if (filters.keyword) params = params.set('keyword', filters.keyword);
    if (filters.location) params = params.set('location', filters.location);
    if (filters.skills) params = params.set('skills', filters.skills);
    if (filters.date_from) params = params.set('date_from', filters.date_from);
    if (filters.date_to) params = params.set('date_to', filters.date_to);
    if (filters.user_location) params = params.set('user_location', filters.user_location);
    if (filters.strict_location) params = params.set('strict_location', 'true');
    if (filters.sort) params = params.set('sort', filters.sort);
    if (filters.seniority && filters.seniority.length) {
      for (const level of filters.seniority) {
        params = params.append('seniority', level);
      }
    }
    if (filters.max_years_experience !== undefined && filters.max_years_experience !== null) {
      params = params.set('max_years_experience', filters.max_years_experience.toString());
    }

    return this.api.get<PaginatedJobsResponse>(API_ROUTES.ingestion.jobs(), { params });
  }

  getJob(jobId: string): Observable<NormalizedJob> {
    return this.api.get<NormalizedJob>(API_ROUTES.ingestion.job({ jobId }));
  }

  getCachedAnalysis(jobId: string): JobAnalysis | undefined {
    return this.jobAnalysisCache()[jobId];
  }

  getJobAnalysis(jobId: string, force = false): Observable<JobAnalysis> {
    let params = new HttpParams();
    if (force) params = params.set('force', 'true');
    return this.api
      .get<JobAnalysis>(API_ROUTES.ingestion.jobAnalysis({ jobId }), { params })
      .pipe(
        tap((analysis) =>
          this.jobAnalysisCache.update((cache) => ({ ...cache, [jobId]: analysis })),
        ),
      );
  }

  getJobHistory(jobId: string, limit?: number): Observable<{ events: JobHistoryEvent[] }> {
    let params = new HttpParams();
    if (limit !== undefined) params = params.set('limit', String(limit));
    return this.api.get<{ events: JobHistoryEvent[] }>(API_ROUTES.ingestion.jobHistory({ jobId }), {
      params,
    });
  }

  listRuns(limit?: number, offset?: number): Observable<{ runs: IngestionRunSummary[] }> {
    let params = new HttpParams();
    if (limit !== undefined) params = params.set('limit', String(limit));
    if (offset !== undefined) params = params.set('offset', String(offset));
    return this.api.get<{ runs: IngestionRunSummary[] }>(API_ROUTES.ingestion.runs(), { params });
  }

  getRun(runId: string): Observable<IngestionRunDetail> {
    return this.api.get<IngestionRunDetail>(API_ROUTES.ingestion.run({ runId }));
  }

  loadPortals(): Observable<PortalEntry[]> {
    return this.api.get<PortalEntry[]>(API_ROUTES.ingestion.portals());
  }

  listSources(): Observable<SourcesResponse> {
    return this.api.get<SourcesResponse>(API_ROUTES.ingestion.sources());
  }

  sourcesHealth(): Observable<SourcesHealthResponse> {
    return this.api.get<SourcesHealthResponse>(API_ROUTES.ingestion.sourcesHealth());
  }

  scanPortals(body: ScanPortalsRequest): Observable<ScanResult> {
    return this.api.post<ScanResult>(API_ROUTES.ingestion.scanPortals(), body);
  }

  markTracked(jobId: string): void {
    this.trackedJobIds.update((ids) => new Set([...ids, jobId]));
  }
}
