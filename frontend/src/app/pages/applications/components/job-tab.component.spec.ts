import { TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';
import { JobTabComponent } from './job-tab.component';
import { ApplicationsService } from '../../../core/services/applications.service';
import { ApplicationAggregate } from '../models/application-aggregate.model';

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
    job_snapshot: {
      id: 'snap-1',
      description: 'Build great APIs.',
      required_skills: ['python', 'fastapi'],
      source: 'manual',
      updated_at: null,
    },
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

describe('JobTabComponent', () => {
  function mount(aggregate = makeAggregate(), service: Record<string, unknown> = {}) {
    const svc = {
      updateSnapshot: vi.fn(() => of(aggregate)),
      regenerateSkills: vi.fn(() => of(aggregate)),
      ...service,
    };
    TestBed.configureTestingModule({
      imports: [JobTabComponent],
      providers: [{ provide: ApplicationsService, useValue: svc }],
    });
    const fixture = TestBed.createComponent(JobTabComponent);
    fixture.componentRef.setInput('aggregate', aggregate);
    fixture.detectChanges();
    return { fixture, svc };
  }

  it('seeds description and skills from the snapshot via ngOnChanges', () => {
    const { fixture } = mount();
    expect(fixture.componentInstance.description()).toBe('Build great APIs.');
    expect(fixture.componentInstance.skills()).toEqual(['python', 'fastapi']);
    expect(fixture.componentInstance.source()).toBe('manual');
  });

  it('defaults source to manual when the snapshot is missing', () => {
    const { fixture } = mount(makeAggregate({ job_snapshot: null }));
    expect(fixture.componentInstance.source()).toBe('manual');
    expect(fixture.componentInstance.skills()).toEqual([]);
  });

  it('adds and removes skills locally', () => {
    const { fixture } = mount();
    fixture.componentInstance.addSkill('django');
    expect(fixture.componentInstance.skills()).toContain('django');
    fixture.componentInstance.removeSkill('python');
    expect(fixture.componentInstance.skills()).not.toContain('python');
  });

  it('saves the snapshot and emits changed', () => {
    const updateSnapshot = vi.fn(() => of(makeAggregate()));
    const { fixture } = mount(makeAggregate(), { updateSnapshot });
    let emitted = false;
    fixture.componentInstance.changed.subscribe(() => (emitted = true));
    fixture.componentInstance.save();
    expect(updateSnapshot).toHaveBeenCalledWith('app-1', {
      description: 'Build great APIs.',
      required_skills: ['python', 'fastapi'],
    });
    expect(emitted).toBe(true);
    expect(fixture.componentInstance.saving()).toBe(false);
  });

  it('shows the saved confirmation on success and clears it on edit', () => {
    const { fixture } = mount();
    expect(fixture.componentInstance.saved()).toBe(false);
    fixture.componentInstance.save();
    expect(fixture.componentInstance.saved()).toBe(true);
    // Editing the description must clear the stale confirmation.
    fixture.componentInstance.setDescription('changed');
    expect(fixture.componentInstance.saved()).toBe(false);
  });

  it('does not show the saved confirmation when save fails', () => {
    const { fixture } = mount(makeAggregate(), {
      updateSnapshot: () => throwError(() => ({ error: { detail: 'save boom' } })),
    });
    fixture.componentInstance.save();
    expect(fixture.componentInstance.saved()).toBe(false);
  });

  it('surfaces an error when save fails', () => {
    const { fixture } = mount(makeAggregate(), {
      updateSnapshot: () => throwError(() => ({ error: { detail: 'save boom' } })),
    });
    fixture.componentInstance.save();
    expect(fixture.componentInstance.error()).toBe('save boom');
    expect(fixture.componentInstance.saving()).toBe(false);
  });

  it('regenerates skills from the returned aggregate and emits changed', () => {
    const regenerated = makeAggregate({
      job_snapshot: {
        id: 'snap-1',
        description: 'Build great APIs.',
        required_skills: ['python', 'kafka'],
        source: 'llm_extracted',
        updated_at: null,
      },
    });
    const regenerateSkills = vi.fn(() => of(regenerated));
    const { fixture } = mount(makeAggregate(), { regenerateSkills });
    let emitted = false;
    fixture.componentInstance.changed.subscribe(() => (emitted = true));
    fixture.componentInstance.regenerate();
    expect(regenerateSkills).toHaveBeenCalledWith('app-1');
    expect(fixture.componentInstance.skills()).toEqual(['python', 'kafka']);
    expect(emitted).toBe(true);
    expect(fixture.componentInstance.regenerating()).toBe(false);
  });

  it('surfaces an error when regenerate fails', () => {
    const { fixture } = mount(makeAggregate(), {
      regenerateSkills: () => throwError(() => ({ error: { detail: 'regen boom' } })),
    });
    fixture.componentInstance.regenerate();
    expect(fixture.componentInstance.error()).toBe('regen boom');
    expect(fixture.componentInstance.regenerating()).toBe(false);
  });
});
