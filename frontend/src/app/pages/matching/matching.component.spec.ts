import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { ActivatedRoute } from '@angular/router';
import { of, throwError } from 'rxjs';
import { MatchingComponent } from './matching.component';
import { MatchingService } from '../../core/services/matching.service';
import { ProfileService } from '../../core/services/profile.service';
import { IngestionService } from '../../core/services/ingestion.service';

function makeProfile(over: Partial<Record<string, unknown>> = {}) {
  return {
    id: 'p-en',
    name: 'Ada Lovelace',
    email: null,
    phone: null,
    location: null,
    sections: [{ content: 'Built engines.' }],
    raw_tex: '',
    language: 'en',
    skills: ['python', 'sql'],
    linkedin_url: null,
    github_url: null,
    portfolio_url: null,
    ...over,
  };
}

function makeMatchResult(over: Partial<Record<string, unknown>> = {}) {
  return {
    id: 'm-1',
    job_id: 'manual',
    cv_id: 'manual',
    overall_score: 0.82,
    breakdown: { semantic_score: 0.8, skill_score: 0.9, experience_score: 0.7, language_score: 1 },
    matched_skills: ['python'],
    missing_skills: ['rust'],
    pros: ['Strong backend'],
    cons: [],
    recommendations: [],
    ...over,
  };
}

describe('MatchingComponent', () => {
  function mount(
    opts: {
      profiles?: Record<string, unknown>;
      listProfiles?: () => unknown;
      queryJobs?: () => unknown;
      matching?: Partial<Record<string, unknown>>;
      jobId?: string | null;
    } = {},
  ) {
    const profileService = {
      profiles: signal<Record<string, unknown>>(opts.profiles ?? {}),
      listProfiles: opts.listProfiles ?? (() => of([])),
      getCurrentProfile: () => of(makeProfile()),
    };
    const ingestion = {
      queryJobs: opts.queryJobs ?? (() => of({ jobs: [], total: 0, page: 1, page_size: 100 })),
      getJob: () => of({}),
    };
    const matching = {
      analyze: () => of(makeMatchResult()),
      evaluate: () => of({ composite_score: 0.7, job_title: 'X', company: 'Y', dimensions: [] }),
      ...opts.matching,
    };
    const route = {
      snapshot: {
        queryParamMap: { get: (key: string) => (key === 'job_id' ? (opts.jobId ?? null) : null) },
      },
    };

    TestBed.configureTestingModule({
      imports: [MatchingComponent],
      providers: [
        { provide: ProfileService, useValue: profileService },
        { provide: IngestionService, useValue: ingestion },
        { provide: MatchingService, useValue: matching },
        { provide: ActivatedRoute, useValue: route },
      ],
    });
    const fixture = TestBed.createComponent(MatchingComponent);
    fixture.detectChanges();
    return { fixture, profileService, ingestion, matching };
  }

  it('hydrates the CV form from cached profiles on init (happy path)', () => {
    const { fixture } = mount({ profiles: { en: makeProfile() } });
    const cmp = fixture.componentInstance;

    expect(cmp.profileLoaded()).toBe(true);
    expect(cmp.cvSkills()).toBe('python, sql');
    expect(cmp.cvSummary()).toContain('Built engines.');
    expect(cmp.availableLanguages()).toEqual(['en']);
  });

  it('falls back to getCurrentProfile when listProfiles fails', () => {
    const getCurrentProfile = vi.fn(() => of(makeProfile()));
    const profileService = {
      profiles: signal<Record<string, unknown>>({}),
      listProfiles: () => throwError(() => new Error('boom')),
      getCurrentProfile,
    };
    TestBed.configureTestingModule({
      imports: [MatchingComponent],
      providers: [
        { provide: ProfileService, useValue: profileService },
        {
          provide: IngestionService,
          useValue: { queryJobs: () => of({ jobs: [] }), getJob: () => of({}) },
        },
        {
          provide: MatchingService,
          useValue: { analyze: () => of(makeMatchResult()), evaluate: () => of({}) },
        },
        { provide: ActivatedRoute, useValue: { snapshot: { queryParamMap: { get: () => null } } } },
      ],
    });
    const fixture = TestBed.createComponent(MatchingComponent);
    fixture.detectChanges();

    expect(getCurrentProfile).toHaveBeenCalled();
  });

  it('populates the result signal on a successful analyze', () => {
    const analyze = vi.fn(() => of(makeMatchResult({ overall_score: 0.9 })));
    const { fixture } = mount({ profiles: { en: makeProfile() }, matching: { analyze } });
    const cmp = fixture.componentInstance;

    cmp.analyze();

    expect(analyze).toHaveBeenCalled();
    expect(cmp.loading()).toBe(false);
    expect(cmp.result()?.overall_score).toBe(0.9);
    expect(cmp.error()).toBe('');
  });

  it('surfaces an error and clears loading when analyze fails', () => {
    const { fixture } = mount({
      profiles: { en: makeProfile() },
      matching: { analyze: () => throwError(() => ({ error: { detail: 'no match' } })) },
    });
    const cmp = fixture.componentInstance;

    cmp.analyze();

    expect(cmp.loading()).toBe(false);
    expect(cmp.result()).toBeNull();
    expect(cmp.error()).toBe('no match');
  });

  describe('dropdown lazy load', () => {
    function makeJob(over: Partial<Record<string, unknown>> = {}) {
      return {
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
        match_score: null,
        llm_score: null,
        verdict: null,
        reasons: [],
        dealbreakers: [],
        ...over,
      };
    }

    it('does not fetch the job list on init', () => {
      const queryJobs = vi.fn(() => of({ jobs: [], total: 0, page: 1, page_size: 25 }));
      mount({ profiles: { en: makeProfile() }, queryJobs });

      expect(queryJobs).not.toHaveBeenCalled();
    });

    it('fetches a 25-item page only once the dropdown is first opened', () => {
      const queryJobs = vi.fn(() => of({ jobs: [makeJob()], total: 1, page: 1, page_size: 25 }));
      const { fixture } = mount({ profiles: { en: makeProfile() }, queryJobs });
      const cmp = fixture.componentInstance;

      cmp.ensureJobsLoaded();

      expect(queryJobs).toHaveBeenCalledWith('boards', 1, 25);
      expect(cmp.jobs().map((j) => j.id)).toEqual(['job-1']);
    });

    it('does not refetch on a second dropdown open', () => {
      const queryJobs = vi.fn(() => of({ jobs: [makeJob()], total: 1, page: 1, page_size: 25 }));
      const { fixture } = mount({ profiles: { en: makeProfile() }, queryJobs });
      const cmp = fixture.componentInstance;

      cmp.ensureJobsLoaded();
      cmp.ensureJobsLoaded();

      expect(queryJobs).toHaveBeenCalledTimes(1);
    });

    it('allows a retry on the next open after a failed load', () => {
      const queryJobs = vi
        .fn()
        .mockReturnValueOnce(throwError(() => ({ error: { detail: 'boom' } })))
        .mockReturnValueOnce(of({ jobs: [makeJob()], total: 1, page: 1, page_size: 25 }));
      const { fixture } = mount({ profiles: { en: makeProfile() }, queryJobs });
      const cmp = fixture.componentInstance;

      cmp.ensureJobsLoaded();
      cmp.ensureJobsLoaded();

      expect(queryJobs).toHaveBeenCalledTimes(2);
      expect(cmp.jobs().map((j) => j.id)).toEqual(['job-1']);
    });

    it('prefills from ?job_id= via the single-job fallback without waiting on the dropdown list', () => {
      const queryJobs = vi.fn(() => of({ jobs: [], total: 0, page: 1, page_size: 25 }));
      const getJob = vi.fn(() => of(makeJob({ id: 'job-42', title: 'Deep linked' })));
      TestBed.configureTestingModule({
        imports: [MatchingComponent],
        providers: [
          {
            provide: ProfileService,
            useValue: { profiles: signal<Record<string, unknown>>({}), listProfiles: () => of([]) },
          },
          { provide: IngestionService, useValue: { queryJobs, getJob } },
          { provide: MatchingService, useValue: { analyze: () => of(makeMatchResult()) } },
          {
            provide: ActivatedRoute,
            useValue: { snapshot: { queryParamMap: { get: () => 'job-42' } } },
          },
        ],
      });
      const fixture = TestBed.createComponent(MatchingComponent);
      fixture.detectChanges();
      const cmp = fixture.componentInstance;

      expect(getJob).toHaveBeenCalledWith('job-42');
      expect(cmp.selectedJobId()).toBe('job-42');
      expect(cmp.jobDescription()).toBe('Build things.');
      // The dropdown list itself is still lazy — untouched until first open.
      expect(queryJobs).not.toHaveBeenCalled();
    });

    it('keeps the deep-linked job visible after a later dropdown load that omits it', () => {
      const queryJobs = vi.fn(() =>
        of({ jobs: [makeJob({ id: 'job-9' })], total: 1, page: 1, page_size: 25 }),
      );
      const getJob = vi.fn(() => of(makeJob({ id: 'job-42', title: 'Deep linked' })));
      TestBed.configureTestingModule({
        imports: [MatchingComponent],
        providers: [
          {
            provide: ProfileService,
            useValue: { profiles: signal<Record<string, unknown>>({}), listProfiles: () => of([]) },
          },
          { provide: IngestionService, useValue: { queryJobs, getJob } },
          { provide: MatchingService, useValue: { analyze: () => of(makeMatchResult()) } },
          {
            provide: ActivatedRoute,
            useValue: { snapshot: { queryParamMap: { get: () => 'job-42' } } },
          },
        ],
      });
      const fixture = TestBed.createComponent(MatchingComponent);
      fixture.detectChanges();
      const cmp = fixture.componentInstance;

      cmp.ensureJobsLoaded();

      expect(cmp.jobs().map((j) => j.id)).toEqual(['job-42', 'job-9']);
      expect(cmp.selectedJobId()).toBe('job-42');
    });
  });
});
