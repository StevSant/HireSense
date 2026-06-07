import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, Router } from '@angular/router';
import { of, throwError } from 'rxjs';
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
  function mount(opts: {
    listStories?: () => unknown;
    interview?: Partial<Record<string, unknown>>;
    jobId?: string | null;
  } = {}) {
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
        queryParamMap: { get: (key: string) => (key === 'job_id' ? opts.jobId ?? null : null) },
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
});
