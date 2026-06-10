import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { IngestionComponent } from './ingestion.component';
import { environment } from '../../../environments/environment';

const jobsPayload = (connectionsByJob: Record<string, number> = {}) => ({
  jobs: [
    {
      id: 'job-1',
      title: 'Engineer',
      company: 'Acme',
      description: 'Build things.',
      skills: ['python'],
      location: 'Remote',
      salary_range: null,
      source: 'remotive',
      source_type: 'feed',
      platform: null,
      categories: [],
      department: null,
      url: 'https://example.com/job-1',
      posted_date: null,
      match_score: 0.8,
      llm_score: 0.8,
      verdict: 'strong',
      reasons: [],
      dealbreakers: [],
      status: 'open',
    },
  ],
  total: 1,
  page: 1,
  page_size: 20,
  total_pages: 1,
  connections_by_job: connectionsByJob,
});

describe('IngestionComponent — connections badge', () => {
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [IngestionComponent],
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    }).compileComponents();
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('renders the connections badge for a job present in connections_by_job', () => {
    const fixture = TestBed.createComponent(IngestionComponent);
    fixture.detectChanges();

    // Flush portals call (order may vary)
    httpMock.match((r) => r.url === `${environment.apiUrl}/ingestion/portals`).forEach((r) => r.flush([]));

    // Flush all pending queryJobs calls (ngOnInit may issue one or two depending on route params)
    const jobReqs = httpMock.match((r) => r.url === `${environment.apiUrl}/ingestion/jobs`);
    expect(jobReqs.length).toBeGreaterThanOrEqual(1);
    jobReqs.forEach((r) => r.flush(jobsPayload({ 'job-1': 3 })));

    fixture.detectChanges();

    const badge = (fixture.nativeElement as HTMLElement).querySelector('.connections-badge');
    expect(badge).toBeTruthy();
    expect(badge!.textContent?.trim()).toContain('3');
    expect(badge!.getAttribute('title')).toContain('3 LinkedIn connections');
  });
});
