import { Injectable, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { environment } from '../../../environments/environment';
import { Observable } from 'rxjs';
import { LoginResponse } from '../models/login-response.model';
import { isTokenExpired } from '../utils/is-token-expired';
import { roleFromToken } from '../utils/role-from-token';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly tokenSignal = signal<string | null>(this.getStoredToken());
  readonly isAuthenticated = computed(() => !isTokenExpired(this.tokenSignal()));
  readonly role = computed(() => roleFromToken(this.tokenSignal()));
  readonly isAdmin = computed(() => this.role() === 'admin');

  constructor(private http: HttpClient, private router: Router) {}

  login(username: string, password: string) {
    return this.http.post<LoginResponse>(`${environment.apiUrl}/auth/login`, { username, password });
  }

  me(): Observable<{ username: string; role: string }> {
    return this.http.get<{ username: string; role: string }>(`${environment.apiUrl}/auth/me`);
  }

  setToken(token: string): void {
    localStorage.setItem('access_token', token);
    this.tokenSignal.set(token);
  }

  getToken(): string | null {
    return this.tokenSignal();
  }

  logout(): void {
    localStorage.removeItem('access_token');
    this.tokenSignal.set(null);
    this.router.navigate(['/login']);
  }

  private getStoredToken(): string | null {
    if (typeof localStorage !== 'undefined') {
      return localStorage.getItem('access_token');
    }
    return null;
  }
}
