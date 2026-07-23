import { ComponentRef } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ProfileSetupCardComponent } from './profile-setup-card.component';
import { CandidateProfile } from '../../models/candidate-profile.model';

function makeProfile(overrides: Partial<CandidateProfile> = {}): CandidateProfile {
  return {
    id: 'profile-1',
    name: 'Ada Lovelace',
    email: null,
    phone: null,
    location: null,
    sections: [],
    raw_tex: '',
    language: 'en',
    skills: ['TypeScript'],
    linkedin_url: null,
    github_url: null,
    portfolio_url: null,
    ...overrides,
  };
}

describe('ProfileSetupCardComponent', () => {
  let component: ProfileSetupCardComponent;
  let componentRef: ComponentRef<ProfileSetupCardComponent>;
  let fixture: ComponentFixture<ProfileSetupCardComponent>;

  beforeEach(() => {
    fixture = TestBed.createComponent(ProfileSetupCardComponent);
    component = fixture.componentInstance;
    componentRef = fixture.componentRef;
  });

  it('identifies the specific setup steps still needed', () => {
    componentRef.setInput('profile', makeProfile());

    expect(component.completedCount()).toBe(0);
    expect(component.steps().map((step) => step.label)).toEqual([
      'Add an email address',
      'Add your location',
      'Add a professional link',
      'Add application basics',
    ]);
  });

  it('marks the profile complete when each onboarding field is present', () => {
    componentRef.setInput(
      'profile',
      makeProfile({
        email: 'ada@example.com',
        location: 'London, UK',
        linkedin_url: 'https://linkedin.com/in/ada',
        apply_profile: {
          preferred_name: null,
          work_authorization: 'UK citizen',
          requires_visa_sponsorship: false,
          desired_salary: null,
          years_of_experience: 5,
          willing_to_relocate: null,
          start_availability: null,
          screening_answers: [],
        },
      }),
    );

    expect(component.completedCount()).toBe(4);
    expect(component.isComplete()).toBe(true);
    expect(component.steps().every((step) => step.complete)).toBe(true);
  });

  it('does not count a missing experience value as application basics', () => {
    componentRef.setInput(
      'profile',
      makeProfile({
        apply_profile: {
          preferred_name: null,
          work_authorization: null,
          requires_visa_sponsorship: null,
          desired_salary: null,
          years_of_experience: undefined as unknown as null,
          willing_to_relocate: null,
          start_availability: null,
          screening_answers: [],
        },
      }),
    );

    expect(component.completedCount()).toBe(0);
  });

  it('renders remaining steps and exposes progress to assistive technology', () => {
    componentRef.setInput('profile', makeProfile({ email: 'ada@example.com' }));
    fixture.detectChanges();

    const element = fixture.nativeElement as HTMLElement;
    const progress = element.querySelector<HTMLElement>('[role="progressbar"]');

    expect(progress?.getAttribute('aria-valuenow')).toBe('1');
    expect(progress?.getAttribute('aria-valuemax')).toBe('4');
    expect(element.textContent).toContain('Add your location');
    expect(element.textContent).not.toContain('Add an email address');
  });
});
