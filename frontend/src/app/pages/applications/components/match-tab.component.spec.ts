import { TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';
import { MatchTabComponent } from './match-tab.component';
import { ApplicationsService } from '../../../core/services/applications.service';
import { ApplicationAggregate } from '../models/application-aggregate.model';
import { ApplicationMatch } from '../models/application-match.model';

function makeMatch(over: Partial<ApplicationMatch> = {}): ApplicationMatch {
  return {
    id: 'm-1',
    overall_score: 0.82,
    semantic_score: 0.8,
    skill_score: 0.7,
    experience_score: 0.9,
    language_score: 1,
    matched_skills: ['python'],
    missing_skills: ['rust'],
    pros: ['strong backend'],
    cons: ['no rust'],
    recommendations: ['learn rust'],
    cv_language: 'en',
    created_at: null,
    ...over,
  };
}

function makeAggregate(over: Partial<ApplicationAggregate> = {}): ApplicationAggregate {
  return {
    id: 'app-1',
    job_id: 'job-1',
    title: 'Senior Backend Engineer',
    company: 'Acme Corp',
    url: null,
    status: 'saved',
    notes: null,
    applied_at: null,
    created_at: null,
    updated_at: null,
    job_snapshot: null,
    latest_match: null,
    latest_optimization: null,
    latest_interview_prep: null,
    latest_cover_letter: null,
    match_count: 0,
    optimization_count: 0,
    interview_prep_count: 0,
    cover_letter_count: 0,
    ...over,
  };
}

describe('MatchTabComponent', () => {
  function mount(aggregate = makeAggregate(), service: Record<string, unknown> = {}) {
    const svc = {
      generateMatch: vi.fn(() => of(makeMatch())),
      ...service,
    };
    TestBed.configureTestingModule({
      imports: [MatchTabComponent],
      providers: [{ provide: ApplicationsService, useValue: svc }],
    });
    const fixture = TestBed.createComponent(MatchTabComponent);
    fixture.componentRef.setInput('aggregate', aggregate);
    fixture.detectChanges();
    return { fixture, svc };
  }

  it('exposes the latest match from the aggregate', () => {
    const { fixture } = mount(makeAggregate({ latest_match: makeMatch() }));
    expect(fixture.componentInstance.match()?.id).toBe('m-1');
  });

  it('reports null when there is no match yet', () => {
    const { fixture } = mount();
    expect(fixture.componentInstance.match()).toBeNull();
  });

  it('generates a match with the chosen language and emits changed', () => {
    const generateMatch = vi.fn(() => of(makeMatch()));
    const { fixture } = mount(makeAggregate(), { generateMatch });
    fixture.componentInstance.onLangChange({ target: { value: 'es' } } as unknown as Event);
    let emitted = false;
    fixture.componentInstance.changed.subscribe(() => (emitted = true));
    fixture.componentInstance.run();
    expect(generateMatch).toHaveBeenCalledWith('app-1', 'es');
    expect(emitted).toBe(true);
    expect(fixture.componentInstance.running()).toBe(false);
  });

  it('surfaces an error and does not emit when match generation fails', () => {
    const { fixture } = mount(makeAggregate(), {
      generateMatch: () => throwError(() => ({ error: { detail: 'match boom' } })),
    });
    let emitted = false;
    fixture.componentInstance.changed.subscribe(() => (emitted = true));
    fixture.componentInstance.run();
    expect(fixture.componentInstance.error()).toBe('match boom');
    expect(emitted).toBe(false);
    expect(fixture.componentInstance.running()).toBe(false);
  });
});
