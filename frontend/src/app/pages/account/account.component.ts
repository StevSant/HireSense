import { Component, DestroyRef, OnInit, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AuthService } from '../../core/services/auth.service';

@Component({
  selector: 'app-account',
  standalone: true,
  imports: [],
  templateUrl: './account.component.html',
  styleUrl: './account.component.scss',
})
export class AccountComponent implements OnInit {
  readonly username = signal('');
  readonly role = signal('');
  readonly loading = signal(false);
  readonly error = signal('');

  private auth = inject(AuthService);
  private readonly destroyRef = inject(DestroyRef);

  ngOnInit(): void {
    this.loading.set(true);
    this.error.set('');
    this.auth
      .me()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (me) => {
          this.username.set(me.username);
          this.role.set(me.role);
          this.loading.set(false);
        },
        error: (err) => {
          this.error.set(err.error?.detail ?? 'Failed to load account');
          this.loading.set(false);
        },
      });
  }

  logout(): void {
    this.auth.logout();
  }
}
