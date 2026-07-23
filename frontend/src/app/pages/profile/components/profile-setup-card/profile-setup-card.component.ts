import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { CandidateProfile } from '../../models/candidate-profile.model';

interface ProfileSetupStep {
  label: string;
  guidance: string;
  complete: boolean;
}

function hasText(value: string | null | undefined): boolean {
  return Boolean(value?.trim());
}

function hasApplicationBasics(profile: CandidateProfile): boolean {
  const applyProfile = profile.apply_profile;
  if (!applyProfile) return false;

  return (
    hasText(applyProfile.work_authorization) ||
    typeof applyProfile.years_of_experience === 'number' ||
    hasText(applyProfile.start_availability)
  );
}

@Component({
  selector: 'app-profile-setup-card',
  standalone: true,
  templateUrl: './profile-setup-card.component.html',
  styleUrl: './profile-setup-card.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProfileSetupCardComponent {
  profile = input.required<CandidateProfile>();

  steps = computed<ProfileSetupStep[]>(() => {
    const profile = this.profile();
    const hasProfessionalLink = [
      profile.linkedin_url,
      profile.github_url,
      profile.portfolio_url,
    ].some(hasText);

    return [
      {
        label: 'Add an email address',
        guidance: 'Use the Edit control below so employers can contact you.',
        complete: hasText(profile.email),
      },
      {
        label: 'Add your location',
        guidance: 'Location helps us prioritize roles you can realistically pursue.',
        complete: hasText(profile.location),
      },
      {
        label: 'Add a professional link',
        guidance: 'A LinkedIn, GitHub, or portfolio link gives hiring teams more context.',
        complete: hasProfessionalLink,
      },
      {
        label: 'Add application basics',
        guidance: 'Add work authorization, experience, or availability in your Apply profile.',
        complete: hasApplicationBasics(profile),
      },
    ];
  });

  completedCount = computed(() => this.steps().filter((step) => step.complete).length);
  isComplete = computed(() => this.completedCount() === this.steps().length);
}
