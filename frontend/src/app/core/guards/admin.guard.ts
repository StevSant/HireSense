import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { map } from 'rxjs/operators';
import { AuthService } from '../services/auth.service';

// #38: gate on the real admin role. The role comes from /auth/me (server-vouched,
// since JS can't read the httpOnly session cookie); the backend still enforces it
// for real by returning 403 on the admin routes. An authenticated non-admin is
// sent to the dashboard (logged in, just not authorized); anyone unauthenticated
// goes to login. Session state is resolved (and cached) via ensureLoaded first.
export const adminGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  return auth.ensureLoaded().pipe(
    map((ok) => {
      if (!ok) {
        return router.createUrlTree(['/login']);
      }
      if (!auth.isAdmin()) {
        return router.createUrlTree(['/dashboard']);
      }
      return true;
    }),
  );
};
