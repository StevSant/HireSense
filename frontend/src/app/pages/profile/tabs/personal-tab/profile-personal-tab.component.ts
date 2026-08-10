import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { ProfileService } from '../../../../core/services/profile.service';
import { ManualFieldsFormComponent } from '../../components/manual-fields-form/manual-fields-form.component';
import { ProfileRequiredEmptyStateComponent } from '../../components/profile-required-empty-state/profile-required-empty-state.component';

/**
 * Profile → Personal details.
 *
 * Only the parsed-details view and its edit form. The apply profile, portfolio
 * and network cards moved to their own tabs: each owned an independent save
 * action, so stacking them here meant scrolling past unrelated work to reach
 * the one you wanted.
 */
@Component({
  selector: 'app-profile-personal-tab',
  standalone: true,
  imports: [ManualFieldsFormComponent, ProfileRequiredEmptyStateComponent],
  templateUrl: './profile-personal-tab.component.html',
  styleUrl: './profile-personal-tab.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProfilePersonalTabComponent {
  private profileService = inject(ProfileService);

  profile = this.profileService.profile;

  editingPersonal = signal(false);
}
