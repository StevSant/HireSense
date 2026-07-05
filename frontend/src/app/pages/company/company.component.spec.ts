import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { ActivatedRoute, convertToParamMap } from '@angular/router';
import { of, throwError } from 'rxjs';
import { CompanyComponent } from './company.component';
import { IngestionService } from '../../core/services/ingestion.service';
import { ApplicationsService } from '../../core/services/applications.service';
import { PreferenceService } from '../../core/services/preference.service';

function job(over: Record<string, unknown> = {}) {
  return {
    id: '1',
    title: 'Backend Engineer',
    company: 'Acme',
    description: '',
    skills: [],
    location: 'Remote',
    salary_range: null,
    source: 'remotive',
    source_type: 'api',
    platform: null,
    categories: [],
    department: null,
    url: 'https://e.com/1',
    posted_date: null,
    match_score: 0.82,
    llm_score: null,
    verdict: null,
    reasons: [],
    dealbreakers: [],
    status: 'open',
    ...over,
  };
}

function page(jobs: unknown[]) {
  return { jobs, total: jobs.length, page: 1, page_size: 100, total_pages: 1 };
}

function mount(service: Record<string, unknown>, name = 'Acme') {
  TestBed.configureTestingModule({
    imports: [CompanyComponent],
    providers: [
      provideRouter([]),
      {
        provide: IngestionService,
        useValue: { trackedJobIds: signal(new Set<string>()), markTracked: () => {}, ...service },
      },
      { provide: ApplicationsService, useValue: { createFromJob: () => of({ id: 'app-1' }) } },
      { provide: PreferenceService, useValue: { submitFeedback: () => of({}) } },
      {
        provide: ActivatedRoute,
        useValue: { snapshot: { paramMap: convertToParamMap({ name }) } },
      },
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
    expect(fixture.nativeElement.querySelectorAll('tbody tr').length).toBe(1);
    expect(fixture.nativeElement.textContent).toContain('82%');
  });

  it('merges boards + portals and de-dupes by id', () => {
    const service = {
      queryJobs: (tab: string) =>
        of(page(tab === 'boards' ? [job({ id: '1' })] : [job({ id: '1' }), job({ id: '2' })])),
    };
    const fixture = mount(service);
    expect(fixture.nativeElement.querySelectorAll('tbody tr').length).toBe(2);
  });

  it('shows the empty state when the company has no jobs', () => {
    const service = { queryJobs: () => of(page([])) };
    const fixture = mount(service);
    expect(fixture.nativeElement.querySelector('.company-state')).not.toBeNull();
    expect(fixture.nativeElement.querySelectorAll('tbody tr').length).toBe(0);
  });

  it('shows the error state when a request fails', () => {
    const service = { queryJobs: () => throwError(() => new Error('boom')) };
    const fixture = mount(service);
    expect(fixture.nativeElement.querySelector('.company-state-error')).not.toBeNull();
  });

  it('prefers the LLM quick score over the heuristic blend (matches the ingestion table)', () => {
    const service = {
      queryJobs: (tab: string) =>
        of(page(tab === 'boards' ? [job({ match_score: 0.62, llm_score: 0.52 })] : [])),
    };
    const fixture = mount(service);
    const badge = fixture.nativeElement.querySelector('.score-badge') as HTMLElement;
    expect(badge.textContent).toContain('52%');
    expect(fixture.nativeElement.textContent).not.toContain('62%');
  });

  it('re-sorts rows client-side when a column header is clicked', () => {
    const service = {
      queryJobs: (tab: string) =>
        of(
          page(
            tab === 'boards'
              ? [
                  job({ id: 'a', title: 'Zebra', llm_score: 0.9 }),
                  job({ id: 'b', title: 'Alpha', llm_score: 0.4 }),
                ]
              : [],
          ),
        ),
    };
    const fixture = mount(service);
    // Default sort is match desc → Zebra (0.9) first.
    let titles = [...fixture.nativeElement.querySelectorAll('td.title')].map((e: Element) =>
      e.textContent?.trim(),
    );
    expect(titles[0]).toContain('Zebra');

    // Click the Title header → ascending alpha → Alpha first.
    const titleHeader = [...fixture.nativeElement.querySelectorAll('th')].find(
      (th: Element) => th.textContent?.trim() === 'Title',
    ) as HTMLElement;
    titleHeader.click();
    fixture.detectChanges();
    titles = [...fixture.nativeElement.querySelectorAll('td.title')].map((e: Element) =>
      e.textContent?.trim(),
    );
    expect(titles[0]).toContain('Alpha');
  });

  it('navigates to the job detail page on row click', () => {
    const service = { queryJobs: (tab: string) => of(page(tab === 'boards' ? [job()] : [])) };
    const fixture = mount(service);
    const router = TestBed.inject(Router);
    const navigate = vi.spyOn(router, 'navigate').mockResolvedValue(true);
    (fixture.nativeElement.querySelector('tbody tr.clickable-row') as HTMLElement).click();
    expect(navigate).toHaveBeenCalledWith(['/dashboard/job', '1']);
  });
});
