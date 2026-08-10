import { ChangeDetectionStrategy, Component, DestroyRef, inject, OnInit } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterOutlet } from '@angular/router';
import { ProfileService } from '../../core/services/profile.service';
import { ProfileSetupCardComponent } from './components/profile-setup-card/profile-setup-card.component';

/**
 * Profile shell.
 *
 * The tabs are child routes rendered through the outlet, so each one is
 * deep-linkable and lazily loaded. This component owns the header, the
 * one-time profile bootstrap that every tab reads via `ProfileService.loaded`,
 * and the setup checklist — which spans all tabs because its steps are
 * completed on different ones, and links to whichever tab owns each step.
 */
@Component({
  selector: 'app-profile',
  standalone: true,
  imports: [RouterOutlet, ProfileSetupCardComponent],
  templateUrl: './profile.component.html',
  styleUrl: './profile.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProfileComponent implements OnInit {
  private profileService = inject(ProfileService);
  private readonly destroyRef = inject(DestroyRef);

  profile = this.profileService.profile;

  ngOnInit(): void {
    this.profileService
      .listProfiles()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => this.profileService.loaded.set(true),
        error: () => {
          // Fallback to single profile fetch
          this.profileService
            .getCurrentProfile()
            .pipe(takeUntilDestroyed(this.destroyRef))
            .subscribe({
              next: () => this.profileService.loaded.set(true),
              error: () => this.profileService.loaded.set(true),
            });
        },
      });
  }
}
