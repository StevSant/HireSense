import { ChangeDetectionStrategy, Component } from '@angular/core';
import { NetworkCardComponent } from '../../components/network-card/network-card.component';
import { PortfolioCardComponent } from '../../components/portfolio-card/portfolio-card.component';

/**
 * Profile → Sources: the data that feeds your profile from elsewhere.
 *
 * Deliberately has no profile guard. Both cards drive their own services and
 * are usable before any CV has been uploaded.
 */
@Component({
  selector: 'app-profile-sources-tab',
  standalone: true,
  imports: [NetworkCardComponent, PortfolioCardComponent],
  templateUrl: './profile-sources-tab.component.html',
  styleUrl: './profile-sources-tab.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProfileSourcesTabComponent {}
