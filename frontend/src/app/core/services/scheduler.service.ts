import { HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiClient, API_ROUTES } from '@core/api';
import { JobRun, ScheduledJob } from '@core/contracts/scheduler.model';

@Injectable({ providedIn: 'root' })
export class SchedulerService {
  private readonly api = inject(ApiClient);

  listJobs(): Observable<ScheduledJob[]> {
    return this.api.get<ScheduledJob[]>(API_ROUTES.scheduler.jobs());
  }

  runs(name: string, limit = 20): Observable<JobRun[]> {
    return this.api.get<JobRun[]>(API_ROUTES.scheduler.jobRuns({ name }), {
      params: new HttpParams().set('limit', limit),
    });
  }

  toggle(name: string, enabled: boolean): Observable<ScheduledJob> {
    return this.api.post<ScheduledJob>(API_ROUTES.scheduler.toggleJob({ name }), { enabled });
  }

  runNow(name: string): Observable<JobRun> {
    return this.api.post<JobRun>(API_ROUTES.scheduler.runJobNow({ name }), {});
  }
}
