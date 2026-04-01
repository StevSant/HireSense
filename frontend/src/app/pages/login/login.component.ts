import { Component, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';

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

  constructor(private auth: AuthService, private router: Router) {}

  onSubmit(): void {
    this.loading.set(true);
    this.error.set('');
    this.auth.login(this.username(), this.password()).subscribe({
      next: (res) => {
        this.auth.setToken(res.access_token);
        this.router.navigate(['/dashboard']);
      },
      error: () => {
        this.error.set('Invalid credentials');
        this.loading.set(false);
      },
    });
  }
}
