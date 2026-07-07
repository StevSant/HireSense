import { TestBed } from '@angular/core/testing';
import { ActivatedRouteSnapshot, Router, RouterStateSnapshot, UrlTree } from '@angular/router';
import { Observable, of } from 'rxjs';
import { describe, expect, it } from 'vitest';
import { adminGuard } from './admin.guard';
import { AuthService } from '../services/auth.service';

function run(auth: Partial<AuthService>): Observable<boolean | UrlTree> {
  const router = {
    createUrlTree: (commands: unknown[]) => ({ __tree: commands }) as unknown as UrlTree,
  };
  TestBed.configureTestingModule({
    providers: [
      { provide: AuthService, useValue: auth },
      { provide: Router, useValue: router },
    ],
  });
  return TestBed.runInInjectionContext(
    () =>
      adminGuard({} as ActivatedRouteSnapshot, {} as RouterStateSnapshot) as Observable<
        boolean | UrlTree
      >,
  );
}

describe('adminGuard', () => {
  it('admits an authenticated admin', () => {
    let result: boolean | UrlTree | undefined;
    run({
      ensureLoaded: () => of(true),
      isAdmin: () => true,
    } as Partial<AuthService>).subscribe((r) => (result = r));
    expect(result).toBe(true);
  });

  it('redirects an authenticated non-admin to /dashboard', () => {
    let result: boolean | UrlTree | undefined;
    run({
      ensureLoaded: () => of(true),
      isAdmin: () => false,
    } as Partial<AuthService>).subscribe((r) => (result = r));
    expect(result).toEqual({ __tree: ['/dashboard'] });
  });

  it('redirects an unauthenticated user to /login', () => {
    let result: boolean | UrlTree | undefined;
    run({
      ensureLoaded: () => of(false),
      isAdmin: () => false,
    } as Partial<AuthService>).subscribe((r) => (result = r));
    expect(result).toEqual({ __tree: ['/login'] });
  });
});
