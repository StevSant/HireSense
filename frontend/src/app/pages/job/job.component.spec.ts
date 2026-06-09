import { TestBed } from '@angular/core/testing';
import { provideRouter, ActivatedRoute, convertToParamMap } from '@angular/router';
import { of, throwError } from 'rxjs';
import { JobDetailComponent } from './job.component';
import { IngestionService } from '../../core/services/ingestion.service';
import { ApplicationsService } from '../../core/services/applications.service';

function job(over: Record<string, unknown> = {}) {
  return {
    id: 'j1', title: 'Backend Engineer', company: 'Acme', description: 'Plain description.',
    skills: ['python'], location: 'Remote', salary_range: null, source: 'remotive',
    source_type: 'api', platform: null, categories: [], department: null,
    url: 'https://e.com/1', posted_date: null, match_score: 0.82, llm_score: null,
    verdict: 'strong', reasons: ['Good skill overlap'], dealbreakers: [], status: 'open', ...over,
  };
}

const analysis = {
  job_id: 'j1', overall_score: 0.8, verdict: 'strong', dimensions: [],
  matched_skills: ['python'], missing_skills: [], pros: ['Remote'], cons: ['Low pay'],
  recommendations: [], narrative: 'Solid fit.',
};

function mount(over: Partial<Record<string, unknown>> = {}, appsOver: Record<string, unknown> = {}, id = 'j1') {
  const ingestion = {
    getJob: () => of(job()),
    getCachedAnalysis: () => undefined,
    getJobAnalysis: () => of(analysis),
    trackedJobIds: () => new Set<string>(),
    markTracked: () => {},
    ...over,
  };
  TestBed.configureTestingModule({
    imports: [JobDetailComponent],
    providers: [
      provideRouter([]),
      { provide: IngestionService, useValue: ingestion },
      { provide: ApplicationsService, useValue: { createFromJob: () => of({}), ...appsOver } },
      { provide: ActivatedRoute, useValue: { snapshot: { paramMap: convertToParamMap({ id }) } } },
    ],
  });
  const fixture = TestBed.createComponent(JobDetailComponent);
  fixture.detectChanges();
  return fixture;
}

describe('JobDetailComponent', () => {
  it('renders the job header with a company link and the analysis', () => {
    const fixture = mount();
    expect(fixture.nativeElement.textContent).toContain('Backend Engineer');
    const companyLink = fixture.nativeElement.querySelector('a.job-company') as HTMLAnchorElement;
    expect(companyLink?.getAttribute('href')).toBe('/dashboard/company/Acme');
    expect(fixture.nativeElement.querySelector('app-deep-analysis')).not.toBeNull();
  });

  it('shows the job error state when the fetch fails', () => {
    const fixture = mount({ getJob: () => throwError(() => new Error('boom')) });
    expect(fixture.nativeElement.querySelector('.job-state-error')).not.toBeNull();
  });

  it('shows the analysis error state when analysis fails', () => {
    const fixture = mount({ getJobAnalysis: () => throwError(() => ({ error: { detail: 'nope' } })) });
    expect(fixture.nativeElement.querySelector('.job-analysis-error')).not.toBeNull();
  });

  it('does not mark tracked and shows an error when tracking fails (non-409)', () => {
    const marked: string[] = [];
    const fixture = mount(
      { markTracked: (id: string) => marked.push(id) },
      { createFromJob: () => throwError(() => ({ status: 500, error: { detail: 'server boom' } })) },
    );
    fixture.componentInstance.track();
    fixture.detectChanges();
    expect(marked).toEqual([]);
    expect(fixture.componentInstance.trackError()).toContain('server boom');
  });
});
