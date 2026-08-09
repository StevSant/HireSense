import { ChangeDetectionStrategy, Component, DestroyRef, inject, OnInit } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterOutlet } from '@angular/router';
import { ProfileService } from '../../core/services/profile.service';

/**
 * Profile shell.
 *
 * The tabs (CV / Personal details / Cover letters) are child routes rendered
 * through the outlet, so each one is deep-linkable and lazily loaded. This
 * component only owns the header and the one-time profile bootstrap that every
 * tab reads via `ProfileService.loaded`.
 */
@Component({
  selector: 'app-profile',
  standalone: true,
  imports: [RouterOutlet],
  templateUrl: './profile.component.html',
  styleUrl: './profile.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProfileComponent implements OnInit {
  private profileService = inject(ProfileService);
  private readonly destroyRef = inject(DestroyRef);

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
