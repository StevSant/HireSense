import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { ProfileService } from '../../../../core/services/profile.service';
import { ApplyProfileCardComponent } from '../../components/apply-profile-card/apply-profile-card.component';
import { ProfileRequiredEmptyStateComponent } from '../../components/profile-required-empty-state/profile-required-empty-state.component';

/**
 * Profile → Apply profile.
 *
 * One card, one save action. It lived on the Personal details tab until the
 * page grew four unrelated write flows and the last one sat below a paginated
 * project grid.
 */
@Component({
  selector: 'app-profile-apply-tab',
  standalone: true,
  imports: [ApplyProfileCardComponent, ProfileRequiredEmptyStateComponent],
  templateUrl: './profile-apply-tab.component.html',
  styleUrl: './profile-apply-tab.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProfileApplyTabComponent {
  private profileService = inject(ProfileService);

  profile = this.profileService.profile;
}
