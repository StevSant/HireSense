import { TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { SchedulerService } from './scheduler.service';

describe('SchedulerService', () => {
  let service: SchedulerService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [SchedulerService, provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(SchedulerService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('lists jobs', () => {
    let result: unknown;
    service.listJobs().subscribe((r) => (result = r));
    const req = httpMock.expectOne('/api/scheduler/jobs');
    expect(req.request.method).toBe('GET');
    req.flush([
      {
        name: 'ingestion_fetch',
        cron: '0 */6 * * *',
        enabled: true,
        last_run: null,
        next_run_at: null,
      },
    ]);
    expect((result as unknown[]).length).toBe(1);
  });

  it('toggles a job', () => {
    service.toggle('ingestion_fetch', false).subscribe();
    const req = httpMock.expectOne('/api/scheduler/jobs/ingestion_fetch/toggle');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ enabled: false });
    req.flush({
      name: 'ingestion_fetch',
      cron: '0 */6 * * *',
      enabled: false,
      last_run: null,
      next_run_at: null,
    });
  });

  it('runs a job now', () => {
    service.runNow('ingestion_fetch').subscribe();
    const req = httpMock.expectOne('/api/scheduler/jobs/ingestion_fetch/run-now');
    expect(req.request.method).toBe('POST');
    req.flush({ job_name: 'ingestion_fetch', status: 'success' });
  });
});
