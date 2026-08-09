import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ProfileService } from '../../../../core/services/profile.service';
import { ApplyProfileCardComponent } from '../../components/apply-profile-card/apply-profile-card.component';
import { ManualFieldsFormComponent } from '../../components/manual-fields-form/manual-fields-form.component';
import { NetworkCardComponent } from '../../components/network-card/network-card.component';
import { PortfolioCardComponent } from '../../components/portfolio-card/portfolio-card.component';
import { ProfileSetupCardComponent } from '../../components/profile-setup-card/profile-setup-card.component';

/**
 * Profile → Personal details.
 *
 * The portfolio and network cards sit outside the `@if (profile())` block on
 * purpose: both are usable before a CV has been uploaded.
 */
@Component({
  selector: 'app-profile-personal-tab',
  standalone: true,
  imports: [
    RouterLink,
    ApplyProfileCardComponent,
    ManualFieldsFormComponent,
    NetworkCardComponent,
    PortfolioCardComponent,
    ProfileSetupCardComponent,
  ],
  templateUrl: './profile-personal-tab.component.html',
  styleUrl: './profile-personal-tab.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProfilePersonalTabComponent {
  private profileService = inject(ProfileService);

  profile = this.profileService.profile;
  initialLoading = computed(() => !this.profileService.loaded());

  editingPersonal = signal(false);
}
