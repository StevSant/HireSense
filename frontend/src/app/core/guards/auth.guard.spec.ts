import { TestBed } from '@angular/core/testing';
import { ActivatedRouteSnapshot, Router, RouterStateSnapshot, UrlTree } from '@angular/router';
import { Observable, of } from 'rxjs';
import { describe, expect, it } from 'vitest';
import { authGuard } from './auth.guard';
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
      authGuard(
        {} as ActivatedRouteSnapshot,
        {} as RouterStateSnapshot,
      ) as Observable<boolean | UrlTree>,
  );
}

describe('authGuard', () => {
  it('admits a resolved authenticated session', () => {
    let result: boolean | UrlTree | undefined;
    run({ ensureLoaded: () => of(true) } as Partial<AuthService>).subscribe((r) => (result = r));
    expect(result).toBe(true);
  });

  it('redirects to /login when the session is anonymous', () => {
    let result: boolean | UrlTree | undefined;
    run({ ensureLoaded: () => of(false) } as Partial<AuthService>).subscribe((r) => (result = r));
    expect(result).toEqual({ __tree: ['/login'] });
  });
});
