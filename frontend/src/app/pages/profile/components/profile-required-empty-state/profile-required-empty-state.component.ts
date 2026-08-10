import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { PROFILE_ROUTES } from '@core/nav';

/**
 * Shown by the Profile tabs that cannot render anything until a CV has been
 * parsed (Personal details, Apply profile). Sources deliberately does not use
 * it — the portfolio and network cards work with no profile at all.
 */
@Component({
  selector: 'app-profile-required-empty-state',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './profile-required-empty-state.component.html',
  styleUrl: './profile-required-empty-state.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProfileRequiredEmptyStateComponent {
  /** What the tab would have shown, e.g. "your parsed details". */
  hint = input.required<string>();

  readonly cvRoute = PROFILE_ROUTES.cv;
}
