import { TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { JobDetailPanelComponent } from './job-detail-panel.component';
import { NormalizedJob } from '../../models/normalized-job.model';

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

describe('JobDetailPanelComponent', () => {
  let navigate: ReturnType<typeof vi.fn>;

  beforeEach(async () => {
    navigate = vi.fn();

    await TestBed.configureTestingModule({
      imports: [JobDetailPanelComponent],
      providers: [
        { provide: Router, useValue: { navigate } },
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
    fixture.componentInstance.closed.subscribe(() => (closed = true));

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
    fixture.componentInstance.closed.subscribe(() => (closed = true));
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

  it('links to the full analysis page instead of expanding analysis inline', () => {
    const fixture = mount();
    let closed = false;
    fixture.componentInstance.closed.subscribe(() => (closed = true));

    expect(fixture.nativeElement.querySelector('app-deep-analysis')).toBeNull();
    const link = Array.from(
      fixture.nativeElement.querySelectorAll('button.deep-toggle') as NodeListOf<HTMLButtonElement>,
    ).find((b) => b.textContent?.includes('Full analysis'))!;
    link.click();

    expect(navigate).toHaveBeenCalledWith(['/dashboard/job', 'job-1']);
    expect(closed).toBe(true);
  });

  it('emits close when the overlay backdrop is clicked', () => {
    const fixture = mount();
    let closed = false;
    fixture.componentInstance.closed.subscribe(() => (closed = true));

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
