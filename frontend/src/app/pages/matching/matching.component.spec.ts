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
});
