import { TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';
import { describe, expect, it, vi } from 'vitest';
import { AccountComponent } from './account.component';
import { AuthService } from '../../core/services/auth.service';

describe('AccountComponent', () => {
  function mount(auth: Partial<AuthService>) {
    TestBed.configureTestingModule({
      imports: [AccountComponent],
      providers: [{ provide: AuthService, useValue: auth }],
    });
    const fixture = TestBed.createComponent(AccountComponent);
    fixture.detectChanges();
    return fixture;
  }

  it('renders username and role from me() on init', () => {
    const fixture = mount({
      me: () => of({ username: 'admin', role: 'admin' }),
    } as Partial<AuthService>);
    const cmp = fixture.componentInstance;

    expect(cmp.username()).toBe('admin');
    expect(cmp.role()).toBe('admin');
    expect(cmp.loading()).toBe(false);
    expect(cmp.error()).toBe('');
  });

  it('surfaces an error and clears loading when me() fails', () => {
    const fixture = mount({
      me: () => throwError(() => ({ error: { detail: 'nope' } })),
    } as Partial<AuthService>);
    const cmp = fixture.componentInstance;

    expect(cmp.error()).toBe('nope');
    expect(cmp.loading()).toBe(false);
    expect(cmp.username()).toBe('');
  });

  it('delegates logout to AuthService', () => {
    const logout = vi.fn();
    const fixture = mount({
      me: () => of({ username: 'admin', role: 'admin' }),
      logout,
    } as Partial<AuthService>);
    fixture.componentInstance.logout();
    expect(logout).toHaveBeenCalled();
  });
});
