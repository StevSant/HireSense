import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { CandidateProfile } from '@core/contracts/candidate-profile.model';
import { PROFILE_ROUTES } from '@core/nav';

interface ProfileSetupStep {
  label: string;
  guidance: string;
  /** Tab that owns the control which completes this step. */
  route: string;
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
  imports: [RouterLink],
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
        guidance: 'Open Personal details to add an address employers can contact you at.',
        route: PROFILE_ROUTES.personal,
        complete: hasText(profile.email),
      },
      {
        label: 'Add your location',
        guidance: 'Location helps us prioritize roles you can realistically pursue.',
        route: PROFILE_ROUTES.personal,
        complete: hasText(profile.location),
      },
      {
        label: 'Add a professional link',
        guidance: 'A LinkedIn, GitHub, or portfolio link gives hiring teams more context.',
        route: PROFILE_ROUTES.personal,
        complete: hasProfessionalLink,
      },
      {
        label: 'Add application basics',
        guidance: 'Add work authorization, experience, or availability in your Apply profile.',
        route: PROFILE_ROUTES.apply,
        complete: hasApplicationBasics(profile),
      },
    ];
  });

  completedCount = computed(() => this.steps().filter((step) => step.complete).length);
  isComplete = computed(() => this.completedCount() === this.steps().length);
}
