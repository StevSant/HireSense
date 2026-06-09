import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { ActivatedRoute, convertToParamMap } from '@angular/router';
import { of, throwError } from 'rxjs';
import { CompanyComponent } from './company.component';
import { IngestionService } from '../../core/services/ingestion.service';

function job(over: Record<string, unknown> = {}) {
  return {
    id: '1', title: 'Backend Engineer', company: 'Acme', description: '', skills: [],
    location: 'Remote', salary_range: null, source: 'remotive', source_type: 'api',
    platform: null, categories: [], department: null, url: 'https://e.com/1',
    posted_date: null, match_score: 0.82, llm_score: null, verdict: null,
    reasons: [], dealbreakers: [], status: 'open', ...over,
  };
}

function page(jobs: unknown[]) {
  return { jobs, total: jobs.length, page: 1, page_size: 100, total_pages: 1 };
}

function mount(service: unknown, name = 'Acme') {
  TestBed.configureTestingModule({
    imports: [CompanyComponent],
    providers: [
      provideRouter([]),
      { provide: IngestionService, useValue: service },
      { provide: ActivatedRoute, useValue: { snapshot: { paramMap: convertToParamMap({ name }) } } },
    ],
  });
  const fixture = TestBed.createComponent(CompanyComponent);
  fixture.detectChanges();
  return fixture;
}

describe('CompanyComponent', () => {
  it('renders the company name, summary and a job row', () => {
    const service = {
      queryJobs: (tab: string) => of(page(tab === 'boards' ? [job()] : [])),
    };
    const fixture = mount(service);
    expect(fixture.nativeElement.textContent).toContain('Acme');
    expect(fixture.nativeElement.querySelectorAll('.company-job').length).toBe(1);
    expect(fixture.nativeElement.textContent).toContain('82%');
  });

  it('merges boards + portals and de-dupes by id', () => {
    const service = {
      queryJobs: (tab: string) =>
        of(page(tab === 'boards' ? [job({ id: '1' })] : [job({ id: '1' }), job({ id: '2' })])),
    };
    const fixture = mount(service);
    expect(fixture.nativeElement.querySelectorAll('.company-job').length).toBe(2);
  });

  it('shows the empty state when the company has no jobs', () => {
    const service = { queryJobs: () => of(page([])) };
    const fixture = mount(service);
    expect(fixture.nativeElement.querySelector('.company-state')).not.toBeNull();
    expect(fixture.nativeElement.querySelectorAll('.company-job').length).toBe(0);
  });

  it('shows the error state when a request fails', () => {
    const service = { queryJobs: () => throwError(() => new Error('boom')) };
    const fixture = mount(service);
    expect(fixture.nativeElement.querySelector('.company-state-error')).not.toBeNull();
  });
});
