import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, Router } from '@angular/router';
import { Subject, of, throwError } from 'rxjs';
import { InterviewComponent } from './interview.component';
import { InterviewService } from '../../core/services/interview.service';
import { IngestionService } from '../../core/services/ingestion.service';
import { ApplicationsService } from '../../core/services/applications.service';

function makeStory(over: Partial<Record<string, unknown>> = {}) {
  return {
    id: 's-1',
    title: 'Led migration',
    competency: 'leadership',
    situation: 'Legacy system',
    task: 'Modernize it',
    action: 'Built a plan',
    result: 'Shipped on time',
    reflection: null,
    tags: null,
    created_at: '2026-01-01',
    updated_at: '2026-01-01',
    ...over,
  };
}

function makePrep(over: Partial<Record<string, unknown>> = {}) {
  return {
    job_title: 'Backend Engineer',
    company: 'Acme',
    matched_stories: [],
    competencies_to_probe: ['leadership'],
    technical_topics: ['Python'],
    negotiation_points: [],
    ...over,
  };
}

describe('InterviewComponent', () => {
  function mount(
    opts: {
      listStories?: () => unknown;
      interview?: Partial<Record<string, unknown>>;
      jobId?: string | null;
    } = {},
  ) {
    const interview = {
      listStories: opts.listStories ?? (() => of([makeStory()])),
      createStory: () => of(makeStory({ id: 's-new' })),
      deleteStory: () => of(undefined),
      prepare: () => of(makePrep()),
      ...opts.interview,
    };
    const ingestion = { getJob: () => of({ title: 'X', company: 'Y', description: 'Z' }) };
    const route = {
      snapshot: {
        queryParamMap: { get: (key: string) => (key === 'job_id' ? (opts.jobId ?? null) : null) },
      },
    };

    TestBed.configureTestingModule({
      imports: [InterviewComponent],
      providers: [
        { provide: InterviewService, useValue: interview },
        { provide: IngestionService, useValue: ingestion },
        { provide: ActivatedRoute, useValue: route },
        // Required by the embedded <app-applications-prep-list>
        { provide: ApplicationsService, useValue: { list: () => of([]) } },
        { provide: Router, useValue: { navigate: () => {} } },
      ],
    });
    const fixture = TestBed.createComponent(InterviewComponent);
    fixture.detectChanges();
    return { fixture, interview };
  }

  it('loads stories and clears loading on init (happy path)', () => {
    const { fixture } = mount({ listStories: () => of([makeStory(), makeStory({ id: 's-2' })]) });
    const cmp = fixture.componentInstance;

    expect(cmp.stories().length).toBe(2);
    expect(cmp.storiesLoading()).toBe(false);
    expect(cmp.storiesError()).toBe('');
  });

  it('surfaces an error and clears loading when listStories fails (error state)', () => {
    const { fixture } = mount({
      listStories: () => throwError(() => ({ error: { detail: 'no stories' } })),
    });
    const cmp = fixture.componentInstance;

    expect(cmp.storiesLoading()).toBe(false);
    expect(cmp.storiesError()).toBe('no stories');
    expect(cmp.stories()).toEqual([]);
  });

  it('prepends the created story on a successful addStory', () => {
    const createStory = vi.fn(() => of(makeStory({ id: 's-new', title: 'New' })));
    const { fixture } = mount({ interview: { createStory } });
    const cmp = fixture.componentInstance;

    cmp.newTitle.set('New');
    cmp.newSituation.set('S');
    cmp.newTask.set('T');
    cmp.newAction.set('A');
    cmp.newResult.set('R');
    cmp.addStory();

    expect(createStory).toHaveBeenCalled();
    expect(cmp.addingStory()).toBe(false);
    expect(cmp.stories()[0].id).toBe('s-new');
  });

  it('populates prepResult on a successful generatePrep', () => {
    const prepare = vi.fn(() => of(makePrep({ company: 'Globex' })));
    const { fixture } = mount({ interview: { prepare } });
    const cmp = fixture.componentInstance;

    cmp.prepJobTitle.set('Engineer');
    cmp.prepCompany.set('Globex');
    cmp.prepDescription.set('Build things');
    cmp.generatePrep();

    expect(prepare).toHaveBeenCalled();
    expect(cmp.preparing()).toBe(false);
    expect(cmp.prepResult()?.company).toBe('Globex');
    expect(cmp.prepError()).toBe('');
  });

  it('surfaces a prep error when generatePrep fails', () => {
    const { fixture } = mount({
      interview: { prepare: () => throwError(() => ({ error: { detail: 'prep failed' } })) },
    });
    const cmp = fixture.componentInstance;

    cmp.prepJobTitle.set('Engineer');
    cmp.prepCompany.set('Globex');
    cmp.prepDescription.set('Build things');
    cmp.generatePrep();

    expect(cmp.preparing()).toBe(false);
    expect(cmp.prepResult()).toBeNull();
    expect(cmp.prepError()).toBe('prep failed');
  });

  it('keeps a prep result readable from a fresh component instance after the original is destroyed mid-run (survives navigation)', () => {
    const subject = new Subject<ReturnType<typeof makePrep>>();
    const interview = {
      listStories: () => of([]),
      createStory: () => of(makeStory()),
      deleteStory: () => of(undefined),
      prepare: () => subject.asObservable(),
    };
    const ingestion = { getJob: () => of({ title: 'X', company: 'Y', description: 'Z' }) };
    const route = { snapshot: { queryParamMap: { get: () => null } } };

    // One TestBed configuration shared by both fixtures, so both component
    // instances resolve the same root-scoped LlmRunnerService — the way two
    // navigations to the same page would in the real app.
    TestBed.configureTestingModule({
      imports: [InterviewComponent],
      providers: [
        { provide: InterviewService, useValue: interview },
        { provide: IngestionService, useValue: ingestion },
        { provide: ActivatedRoute, useValue: route },
        { provide: ApplicationsService, useValue: { list: () => of([]) } },
        { provide: Router, useValue: { navigate: () => {} } },
      ],
    });

    const first = TestBed.createComponent(InterviewComponent);
    first.detectChanges();
    first.componentInstance.prepJobTitle.set('Engineer');
    first.componentInstance.prepCompany.set('Globex');
    first.componentInstance.prepDescription.set('Build things');
    first.componentInstance.generatePrep();
    expect(first.componentInstance.preparing()).toBe(true);

    // Simulate navigating away: the component is destroyed while the
    // request is still in flight.
    first.destroy();

    // The request completes after the originating component is gone.
    subject.next(makePrep({ company: 'Globex' }));
    subject.complete();

    // A newly mounted instance (as if the user navigated back) reads the
    // cached result without re-triggering generatePrep().
    const second = TestBed.createComponent(InterviewComponent);
    second.detectChanges();
    expect(second.componentInstance.preparing()).toBe(false);
    expect(second.componentInstance.prepResult()?.company).toBe('Globex');
  });
});

describe('InterviewComponent story sorting/filtering', () => {
  function mountWith(stories: ReturnType<typeof makeStory>[]): InterviewComponent {
    const interview = {
      listStories: () => of(stories),
      createStory: () => of(makeStory()),
      deleteStory: () => of(undefined),
      prepare: () => of(makePrep()),
    };
    TestBed.configureTestingModule({
      imports: [InterviewComponent],
      providers: [
        { provide: InterviewService, useValue: interview },
        {
          provide: IngestionService,
          useValue: { getJob: () => of({ title: '', company: '', description: '' }) },
        },
        { provide: ActivatedRoute, useValue: { snapshot: { queryParamMap: { get: () => null } } } },
        { provide: ApplicationsService, useValue: { list: () => of([]) } },
        { provide: Router, useValue: { navigate: () => {} } },
      ],
    });
    const fixture = TestBed.createComponent(InterviewComponent);
    fixture.detectChanges();
    return fixture.componentInstance;
  }

  it('defaults to created descending', () => {
    const comp = mountWith([
      makeStory({ id: 'a', created_at: '2026-01-01' }),
      makeStory({ id: 'b', created_at: '2026-05-01' }),
      makeStory({ id: 'c', created_at: '2026-03-01' }),
    ]);
    expect(comp.visibleStories().map((s) => s.id)).toEqual(['b', 'c', 'a']);
  });

  it('filters by competency', () => {
    const comp = mountWith([
      makeStory({ id: 'a', competency: 'leadership' }),
      makeStory({ id: 'b', competency: 'technical' }),
    ]);
    comp.competencyFilter.set('technical');
    expect(comp.visibleStories().map((s) => s.id)).toEqual(['b']);
  });

  it('sorts by title ascending when toggled', () => {
    const comp = mountWith([
      makeStory({ id: 'a', title: 'Zeta' }),
      makeStory({ id: 'b', title: 'Alpha' }),
    ]);
    comp.storySort.toggle('title'); // text default asc
    expect(comp.visibleStories().map((s) => s.id)).toEqual(['b', 'a']);
  });
});
