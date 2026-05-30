import { Injectable, signal } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, tap } from 'rxjs';
import { environment } from '../../../environments/environment';
import { FetchResponse } from '../../pages/ingestion/models/fetch-response.model';
import { JobAnalysis } from '../../pages/ingestion/models/job-analysis.model';
import { NormalizedJob } from '../../pages/ingestion/models/normalized-job.model';
import { PaginatedJobsResponse } from '../../pages/ingestion/models/paginated-jobs-response.model';
import { PortalEntry } from '../../pages/ingestion/models/portal-entry.model';
import { ScanPortalsRequest } from '../../pages/ingestion/models/scan-portals-request.model';
import { ScanResult } from '../../pages/ingestion/models/scan-result.model';

export type SeniorityLevel = 'intern' | 'junior' | 'mid' | 'senior' | 'lead' | 'unknown';

export interface JobFilters {
  source?: string;
  keyword?: string;
  location?: string;
  skills?: string;
  date_from?: string;
  date_to?: string;
  user_location?: string;
  strict_location?: boolean;
  sort?: 'match_desc' | 'date_desc';
  seniority?: SeniorityLevel[];
  max_years_experience?: number;
}

@Injectable({ providedIn: 'root' })
export class IngestionService {
  readonly trackedJobIds = signal<Set<string>>(new Set());
  // Deep-analysis results cached by job id. Lives in the (root) service so it
  // survives the detail panel being destroyed on close — re-opening a job
  // shows its analysis instantly without refetching.
  readonly jobAnalysisCache = signal<Record<string, JobAnalysis>>({});

  constructor(private http: HttpClient) {}

  fetchJobs(): Observable<FetchResponse> {
    return this.http.post<FetchResponse>(`${environment.apiUrl}/ingestion/fetch`, {});
  }

  queryJobs(
    tab: 'boards' | 'portals',
    page: number,
    pageSize: number,
    filters: JobFilters = {},
  ): Observable<PaginatedJobsResponse> {
    let params = new HttpParams()
      .set('tab', tab)
      .set('page', page.toString())
      .set('page_size', pageSize.toString());

    if (filters.source) params = params.set('source', filters.source);
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

    return this.http.get<PaginatedJobsResponse>(`${environment.apiUrl}/ingestion/jobs`, { params });
  }

  getJob(jobId: string): Observable<NormalizedJob> {
    return this.http.get<NormalizedJob>(`${environment.apiUrl}/ingestion/jobs/${jobId}`);
  }

  getCachedAnalysis(jobId: string): JobAnalysis | undefined {
    return this.jobAnalysisCache()[jobId];
  }

  getJobAnalysis(jobId: string, force = false): Observable<JobAnalysis> {
    let params = new HttpParams();
    if (force) params = params.set('force', 'true');
    return this.http
      .get<JobAnalysis>(`${environment.apiUrl}/ingestion/jobs/${jobId}/analysis`, { params })
      .pipe(
        tap((analysis) =>
          this.jobAnalysisCache.update((cache) => ({ ...cache, [jobId]: analysis })),
        ),
      );
  }

  loadPortals(): Observable<PortalEntry[]> {
    return this.http.get<PortalEntry[]>(`${environment.apiUrl}/ingestion/portals`);
  }

  scanPortals(body: ScanPortalsRequest): Observable<ScanResult> {
    return this.http.post<ScanResult>(`${environment.apiUrl}/ingestion/scan-portals`, body);
  }

  markTracked(jobId: string): void {
    this.trackedJobIds.update((ids) => new Set([...ids, jobId]));
  }
}
