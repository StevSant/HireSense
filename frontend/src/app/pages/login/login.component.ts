import { Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { finalize } from 'rxjs';
import { AuthService } from '../../core/services/auth.service';
import { mapLoginError } from './login-error.util';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './login.component.html',
  styleUrl: './login.component.scss',
})
export class LoginComponent {
  username = signal('');
  password = signal('');
  error = signal('');
  loading = signal(false);

  private readonly destroyRef = inject(DestroyRef);

  constructor(
    private auth: AuthService,
    private router: Router,
  ) {}

  onSubmit(): void {
    this.loading.set(true);
    this.error.set('');
    this.auth
      .login(this.username(), this.password())
      .pipe(
        finalize(() => this.loading.set(false)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe({
        next: (user) => {
          if (user) {
            this.router.navigate(['/dashboard']);
          } else {
            // A rejected credential arrives on the error path, so reaching here
            // means the credential was accepted but the follow-up /auth/me probe
            // failed — the session cookie never took hold.
            this.error.set(
              'Signed in, but the session was not established — check that cookies are enabled for this site.',
            );
          }
        },
        error: (err: unknown) => {
          this.error.set(mapLoginError(err));
        },
      });
  }
}
