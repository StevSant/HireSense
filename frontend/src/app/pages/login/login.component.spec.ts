import { TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { Subject, of, throwError } from 'rxjs';
import { describe, expect, it, vi } from 'vitest';
import { LoginComponent } from './login.component';
import { AuthService } from '../../core/services/auth.service';

interface SessionUser {
  username: string;
  role: string;
}

function makeAuth(over: Partial<Record<string, unknown>> = {}) {
  return {
    login: () => of<SessionUser | null>({ username: 'admin', role: 'admin' }),
    ...over,
  };
}

describe('LoginComponent', () => {
  function mount(auth: unknown, router: unknown = { navigate: () => {} }) {
    TestBed.configureTestingModule({
      imports: [LoginComponent],
      providers: [
        { provide: AuthService, useValue: auth },
        { provide: Router, useValue: router },
      ],
    });
    const fixture = TestBed.createComponent(LoginComponent);
    fixture.detectChanges();
    return fixture;
  }

  it('navigates to the dashboard on a successful login', () => {
    const navigate = vi.fn();
    const fixture = mount(makeAuth(), { navigate });
    const cmp = fixture.componentInstance;

    cmp.onSubmit();

    expect(navigate).toHaveBeenCalledWith(['/dashboard']);
    expect(cmp.loading()).toBe(false);
  });

  it('surfaces an error when login resolves without a session', () => {
    const navigate = vi.fn();
    const fixture = mount(makeAuth({ login: () => of<SessionUser | null>(null) }), { navigate });
    const cmp = fixture.componentInstance;

    cmp.onSubmit();

    expect(navigate).not.toHaveBeenCalled();
    expect(cmp.error()).toBe('Invalid credentials');
    expect(cmp.loading()).toBe(false);
  });

  it('clears the loading signal on a failed login and surfaces an error', () => {
    const fixture = mount(makeAuth({ login: () => throwError(() => new Error('nope')) }));
    const cmp = fixture.componentInstance;

    cmp.onSubmit();

    expect(cmp.loading()).toBe(false);
    expect(cmp.error()).toBe('Invalid credentials');
  });

  it('keeps loading true while the login request is in flight', () => {
    const pending = new Subject<SessionUser | null>();
    const fixture = mount(makeAuth({ login: () => pending.asObservable() }));
    const cmp = fixture.componentInstance;

    cmp.onSubmit();
    expect(cmp.loading()).toBe(true);

    pending.next({ username: 'admin', role: 'admin' });
    pending.complete();
    expect(cmp.loading()).toBe(false);
  });
});
