import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { JobRun, ScheduledJob } from '../models/scheduler.model';

@Injectable({ providedIn: 'root' })
export class SchedulerService {
  private readonly http = inject(HttpClient);
  private readonly base = '/api/scheduler';

  listJobs(): Observable<ScheduledJob[]> {
    return this.http.get<ScheduledJob[]>(`${this.base}/jobs`);
  }

  runs(name: string, limit = 20): Observable<JobRun[]> {
    return this.http.get<JobRun[]>(`${this.base}/jobs/${name}/runs?limit=${limit}`);
  }

  toggle(name: string, enabled: boolean): Observable<ScheduledJob> {
    return this.http.post<ScheduledJob>(`${this.base}/jobs/${name}/toggle`, { enabled });
  }

  runNow(name: string): Observable<JobRun> {
    return this.http.post<JobRun>(`${this.base}/jobs/${name}/run-now`, {});
  }
}
