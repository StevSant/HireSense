import { TestBed } from '@angular/core/testing';
import { ActivatedRouteSnapshot, Router, RouterStateSnapshot, UrlTree } from '@angular/router';
import { describe, expect, it } from 'vitest';
import { adminGuard } from './admin.guard';
import { AuthService } from '../services/auth.service';

function run(auth: Partial<AuthService>) {
  const router = {
    createUrlTree: (commands: unknown[]) => ({ __tree: commands }) as unknown as UrlTree,
  };
  TestBed.configureTestingModule({
    providers: [
      { provide: AuthService, useValue: auth },
      { provide: Router, useValue: router },
    ],
  });
  return TestBed.runInInjectionContext(() =>
    adminGuard({} as ActivatedRouteSnapshot, {} as RouterStateSnapshot),
  );
}

describe('adminGuard', () => {
  it('admits an authenticated admin', () => {
    const result = run({
      isAuthenticated: () => true,
      isAdmin: () => true,
    } as Partial<AuthService>);
    expect(result).toBe(true);
  });

  it('redirects an authenticated non-admin to /dashboard', () => {
    const result = run({
      isAuthenticated: () => true,
      isAdmin: () => false,
    } as Partial<AuthService>);
    expect(result).toEqual({ __tree: ['/dashboard'] });
  });

  it('redirects an unauthenticated user to /login', () => {
    const result = run({
      isAuthenticated: () => false,
      isAdmin: () => false,
    } as Partial<AuthService>);
    expect(result).toEqual({ __tree: ['/login'] });
  });
});
