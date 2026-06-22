import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { SchedulerComponent } from './scheduler.component';

describe('SchedulerComponent', () => {
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [SchedulerComponent],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    httpMock = TestBed.inject(HttpTestingController);
  });

  it('loads jobs on init', () => {
    const fixture = TestBed.createComponent(SchedulerComponent);
    fixture.detectChanges();
    const req = httpMock.expectOne('/api/scheduler/jobs');
    req.flush([
      { name: 'ingestion_fetch', cron: '0 */6 * * *', enabled: true, last_run: null, next_run_at: null },
    ]);
    expect(fixture.componentInstance.jobs().length).toBe(1);
    httpMock.verify();
  });
});
