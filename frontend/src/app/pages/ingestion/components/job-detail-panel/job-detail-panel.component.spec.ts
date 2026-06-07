import { TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { of, throwError } from 'rxjs';
import { JobDetailPanelComponent } from './job-detail-panel.component';
import { IngestionService } from '../../../../core/services/ingestion.service';
import { NormalizedJob } from '../../models/normalized-job.model';
import { JobAnalysis } from '../../models/job-analysis.model';

function makeJob(overrides: Partial<NormalizedJob> = {}): NormalizedJob {
  return {
    id: 'job-1',
    title: 'Senior Backend Engineer',
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
    match_score: 0.7,
    llm_score: 0.8,
    verdict: 'strong',
    reasons: ['Good skill overlap'],
    dealbreakers: [],
    status: 'open',
    ...overrides,
  };
}

const ANALYSIS: JobAnalysis = {
  job_id: 'job-1',
  overall_score: 0.82,
  verdict: 'strong',
  dimensions: [],
  matched_skills: [],
  missing_skills: [],
  pros: [],
  cons: [],
  recommendations: [],
  narrative: 'Looks good.',
};

describe('JobDetailPanelComponent', () => {
  let navigate: ReturnType<typeof vi.fn>;
  let getJobAnalysis: ReturnType<typeof vi.fn>;
  let getCachedAnalysis: ReturnType<typeof vi.fn>;

  beforeEach(async () => {
    navigate = vi.fn();
    getJobAnalysis = vi.fn().mockReturnValue(of(ANALYSIS));
    getCachedAnalysis = vi.fn().mockReturnValue(undefined);

    await TestBed.configureTestingModule({
      imports: [JobDetailPanelComponent],
      providers: [
        { provide: Router, useValue: { navigate } },
        { provide: IngestionService, useValue: { getJobAnalysis, getCachedAnalysis } },
      ],
    }).compileComponents();
  });

  function mount(job: NormalizedJob = makeJob(), inputs: Partial<{ tracked: boolean; tracking: boolean }> = {}) {
    const fixture = TestBed.createComponent(JobDetailPanelComponent);
    fixture.componentRef.setInput('job', job);
    if (inputs.tracked !== undefined) fixture.componentRef.setInput('tracked', inputs.tracked);
    if (inputs.tracking !== undefined) fixture.componentRef.setInput('tracking', inputs.tracking);
    fixture.detectChanges();
    return fixture;
  }

  it('renders the match score percentage from the LLM score', () => {
    const fixture = mount();
    expect(fixture.nativeElement.querySelector('.match-score-num').textContent.trim()).toBe('80%');
    expect(fixture.componentInstance.scorePercent()).toBe('80%');
  });

  it('shows the no-score note when both scores are null', () => {
    const fixture = mount(makeJob({ llm_score: null, match_score: null }));
    expect(fixture.componentInstance.pillScore()).toBeNull();
    expect(fixture.nativeElement.querySelector('.match-na-note')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('.match-score-num')).toBeNull();
  });

  it('navigates to the optimization page with the job id and closes', () => {
    const fixture = mount();
    let closed = false;
    fixture.componentInstance.close.subscribe(() => (closed = true));

    const optimizeBtn = Array.from(
      fixture.nativeElement.querySelectorAll('button.btn-shortcut') as NodeListOf<HTMLButtonElement>,
    ).find((b) => b.textContent?.includes('Optimize CV'))!;
    optimizeBtn.click();

    expect(navigate).toHaveBeenCalledWith(['/dashboard/optimization'], {
      queryParams: { job_id: 'job-1' },
    });
    expect(closed).toBe(true);
  });

  it('navigates to matching and interview pages with the job id', () => {
    const fixture = mount();
    fixture.componentInstance.goToMatching();
    expect(navigate).toHaveBeenCalledWith(['/dashboard/matching'], {
      queryParams: { job_id: 'job-1' },
    });

    fixture.componentInstance.goToInterview();
    expect(navigate).toHaveBeenCalledWith(['/dashboard/interview'], {
      queryParams: { job_id: 'job-1' },
    });
  });

  it('emits track with the job id when Track is clicked', () => {
    const fixture = mount();
    let tracked: string | null = null;
    fixture.componentInstance.track.subscribe((id) => (tracked = id));

    const trackBtn = Array.from(
      fixture.nativeElement.querySelectorAll('button.btn-action') as NodeListOf<HTMLButtonElement>,
    ).find((b) => b.textContent?.trim() === 'Track')!;
    trackBtn.click();

    expect(tracked).toBe('job-1');
  });

  it('shows a disabled "Tracked" affordance when already tracked', () => {
    const fixture = mount(makeJob(), { tracked: true });
    const btn = fixture.nativeElement.querySelector('button.btn-tracked') as HTMLButtonElement;
    expect(btn).not.toBeNull();
    expect(btn.disabled).toBe(true);
  });

  it('emits close on the close button', () => {
    const fixture = mount();
    let closed = false;
    fixture.componentInstance.close.subscribe(() => (closed = true));
    (fixture.nativeElement.querySelector('button.btn-close') as HTMLButtonElement).click();
    expect(closed).toBe(true);
  });

  it('re-emits feedbackSubmitted from the embedded feedback controls', () => {
    const fixture = mount();
    let kind: string | null = null;
    fixture.componentInstance.feedbackSubmitted.subscribe((k) => (kind = k));
    fixture.componentInstance.feedbackSubmitted.emit('thumbs_up');
    expect(kind).toBe('thumbs_up');
  });

  it('loads deep analysis on first expand and renders the success state', () => {
    const fixture = mount();

    // Uncached at expand time, so the toggle triggers a service load.
    fixture.componentInstance.toggleDeepAnalysis();
    fixture.detectChanges();
    expect(getJobAnalysis).toHaveBeenCalledWith('job-1', false);
    expect(fixture.componentInstance.analysisLoading()).toBe(false);

    // Service now reports the result as cached. The `analysis` computed reads it
    // via the `job` signal, so re-setting `job` recomputes it and the
    // <app-deep-analysis> child renders.
    getCachedAnalysis.mockReturnValue(ANALYSIS);
    fixture.componentRef.setInput('job', makeJob());
    fixture.detectChanges();

    expect(fixture.componentInstance.analysis()).toEqual(ANALYSIS);
    expect(fixture.nativeElement.querySelector('app-deep-analysis')).not.toBeNull();
  });

  it('surfaces the deep analysis error state and retries', () => {
    getJobAnalysis.mockReturnValue(throwError(() => ({ error: { detail: 'boom' } })));
    const fixture = mount();

    fixture.componentInstance.toggleDeepAnalysis();
    fixture.detectChanges();

    expect(fixture.componentInstance.analysisError()).toBe('boom');
    expect(fixture.nativeElement.querySelector('.deep-error')).not.toBeNull();

    // Retry re-invokes the service.
    getJobAnalysis.mockClear();
    fixture.componentInstance.retryAnalysis();
    expect(getJobAnalysis).toHaveBeenCalledWith('job-1', false);
  });

  it('emits close when the overlay backdrop is clicked', () => {
    const fixture = mount();
    let closed = false;
    fixture.componentInstance.close.subscribe(() => (closed = true));

    const overlay = fixture.nativeElement.querySelector('.panel-overlay') as HTMLElement;
    overlay.dispatchEvent(new MouseEvent('click'));
    fixture.detectChanges();

    // The handler only closes when the click target is the overlay itself.
    fixture.componentInstance.onOverlayClick({
      target: overlay,
    } as unknown as MouseEvent);
    expect(closed).toBe(true);
  });
});
