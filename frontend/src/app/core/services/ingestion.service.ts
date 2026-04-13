import { Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';
import { environment } from '../../../environments/environment';
import { FetchResponse } from '../../pages/ingestion/models/fetch-response.model';
import { NormalizedJob } from '../../pages/ingestion/models/normalized-job.model';
import { PortalEntry } from '../../pages/ingestion/models/portal-entry.model';
import { ScanPortalsRequest } from '../../pages/ingestion/models/scan-portals-request.model';
import { ScanResult } from '../../pages/ingestion/models/scan-result.model';

@Injectable({ providedIn: 'root' })
export class IngestionService {
  /** Persisted job list — survives page navigation. */
  readonly jobs = signal<NormalizedJob[]>([]);
  readonly trackedJobIds = signal<Set<string>>(new Set());

  constructor(private http: HttpClient) {}

  fetchJobs(): Observable<FetchResponse> {
    return this.http.post<FetchResponse>(`${environment.apiUrl}/ingestion/fetch`, {}).pipe(
      tap((res) => this.jobs.set(res.jobs)),
    );
  }

  listJobs(): Observable<NormalizedJob[]> {
    return this.http.get<NormalizedJob[]>(`${environment.apiUrl}/ingestion/jobs`);
  }

  loadPortals(): Observable<PortalEntry[]> {
    return this.http.get<PortalEntry[]>(`${environment.apiUrl}/ingestion/portals`);
  }

  scanPortals(body: ScanPortalsRequest): Observable<ScanResult> {
    return this.http.post<ScanResult>(`${environment.apiUrl}/ingestion/scan-portals`, body).pipe(
      tap((res) => {
        const existing = this.jobs();
        const existingIds = new Set(existing.map((j) => j.id));
        const merged = [...existing, ...res.jobs.filter((j) => !existingIds.has(j.id))];
        this.jobs.set(merged);
      }),
    );
  }

  markTracked(jobId: string): void {
    this.trackedJobIds.update((ids) => new Set([...ids, jobId]));
  }
}
