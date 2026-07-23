import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import { ApplyProfileCardComponent } from './apply-profile-card.component';
import { CandidateProfile } from '../../models/candidate-profile.model';
import { ProfileService } from '../../../../core/services/profile.service';

function makeProfile(overrides: Partial<CandidateProfile> = {}): CandidateProfile {
  return {
    id: 'p-1',
    name: 'Ada Lovelace',
    email: 'ada@example.com',
    phone: null,
    location: null,
    sections: [],
    raw_tex: '',
    language: 'en',
    skills: [],
    linkedin_url: null,
    github_url: null,
    portfolio_url: null,
    apply_profile: null,
    ...overrides,
  };
}

describe('ApplyProfileCardComponent', () => {
  let setApplyProfile: ReturnType<typeof vi.fn>;

  beforeEach(async () => {
    setApplyProfile = vi.fn().mockReturnValue(of(makeProfile()));
    await TestBed.configureTestingModule({
      imports: [ApplyProfileCardComponent],
      providers: [{ provide: ProfileService, useValue: { setApplyProfile } }],
    }).compileComponents();
  });

  function mount(profile: CandidateProfile = makeProfile()) {
    const fixture = TestBed.createComponent(ApplyProfileCardComponent);
    fixture.componentRef.setInput('profile', profile);
    fixture.detectChanges();
    return fixture;
  }

  it('prefills the form from an existing apply profile', () => {
    const fixture = mount(
      makeProfile({
        apply_profile: {
          preferred_name: 'Ada',
          work_authorization: 'EU work permit',
          work_authorization_status: 'authorized',
          requires_visa_sponsorship: false,
          desired_salary: '€70k',
          years_of_experience: 8,
          willing_to_relocate: true,
          start_availability: '2 weeks',
          screening_answers: [{ question: 'Why us?', answer: 'Fit' }],
        },
      }),
    );

    const form = fixture.componentInstance.form();
    expect(form.work_authorization).toBe('EU work permit');
    expect(form.work_authorization_status).toBe('authorized');
    expect(form.years_of_experience).toBe('8');
    expect(form.screening_answers.length).toBe(1);
    expect(fixture.componentInstance.isDirty()).toBe(false);
  });

  it('maps the form to a typed payload on save (bools and ints, empties to null)', () => {
    const fixture = mount();
    const c = fixture.componentInstance;

    c.set('work_authorization', '  US Citizen  ');
    c.set('work_authorization_status', 'authorized');
    c.set('years_of_experience', '5');
    c.addScreeningAnswer();
    c.updateScreeningAnswer(0, 'question', 'Q1');
    c.updateScreeningAnswer(0, 'answer', 'A1');
    c.save();

    expect(setApplyProfile).toHaveBeenCalledTimes(1);
    const payload = setApplyProfile.mock.calls[0][0];
    expect(payload.work_authorization).toBe('US Citizen');
    expect(payload.work_authorization_status).toBe('authorized');
    expect(payload.requires_visa_sponsorship).toBe(false);
    expect(payload.years_of_experience).toBe(5);
    expect(payload.preferred_name).toBeNull();
    expect(payload.screening_answers).toEqual([{ question: 'Q1', answer: 'A1' }]);
  });

  it('does not call the service when nothing changed', () => {
    const fixture = mount();
    fixture.componentInstance.save();
    expect(setApplyProfile).not.toHaveBeenCalled();
  });
});
