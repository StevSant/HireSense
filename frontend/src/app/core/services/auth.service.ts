import { Injectable, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { environment } from '../../../environments/environment';
import { Observable, of } from 'rxjs';
import { catchError, finalize, map, shareReplay, switchMap, tap } from 'rxjs/operators';
import { LoginResponse } from '../models/login-response.model';

type SessionStatus = 'unknown' | 'authenticated' | 'anonymous';

interface SessionUser {
  username: string;
  role: string;
}

/**
 * Cookie-based session auth. The JWT lives in an httpOnly cookie the server sets
 * on login, so it is invisible to JavaScript (XSS can't steal it) — there is no
 * token in localStorage. The client derives its session state from `/auth/me`
 * instead of decoding a token it can no longer read.
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly userSignal = signal<SessionUser | null>(null);
  private readonly statusSignal = signal<SessionStatus>('unknown');
  // Caches the in-flight /auth/me probe so concurrent guards share one request.
  private sessionProbe: Observable<SessionUser | null> | null = null;

  readonly isAuthenticated = computed(() => this.statusSignal() === 'authenticated');
  readonly role = computed(() => this.userSignal()?.role ?? null);
  readonly isAdmin = computed(() => this.role() === 'admin');

  constructor(
    private http: HttpClient,
    private router: Router,
  ) {}

  login(username: string, password: string): Observable<SessionUser | null> {
    return this.http
      .post<LoginResponse>(`${environment.apiUrl}/auth/login`, { username, password })
      .pipe(switchMap(() => this.refreshSession()));
  }

  me(): Observable<SessionUser> {
    return this.http.get<SessionUser>(`${environment.apiUrl}/auth/me`);
  }

  /** Re-probe /auth/me and update the cached session state. */
  refreshSession(): Observable<SessionUser | null> {
    this.sessionProbe = null;
    return this.me().pipe(
      tap((user) => this.setSession(user)),
      map((user): SessionUser | null => user),
      catchError(() => {
        this.clearSession();
        return of(null);
      }),
      shareReplay(1),
    );
  }

  /**
   * Resolve session state once, caching the in-flight probe so a burst of guard
   * activations (auth + admin on one navigation) triggers a single /auth/me.
   */
  ensureLoaded(): Observable<boolean> {
    if (this.statusSignal() !== 'unknown') {
      return of(this.isAuthenticated());
    }
    if (!this.sessionProbe) {
      this.sessionProbe = this.refreshSession();
    }
    return this.sessionProbe.pipe(map((user) => user !== null));
  }

  logout(): void {
    this.http
      .post(`${environment.apiUrl}/auth/logout`, {})
      .pipe(
        finalize(() => {
          this.clearSession();
          this.router.navigate(['/login']);
        }),
      )
      .subscribe({ error: () => {} });
  }

  private setSession(user: SessionUser): void {
    this.userSignal.set(user);
    this.statusSignal.set('authenticated');
  }

  private clearSession(): void {
    this.userSignal.set(null);
    this.statusSignal.set('anonymous');
    this.sessionProbe = null;
  }
}
