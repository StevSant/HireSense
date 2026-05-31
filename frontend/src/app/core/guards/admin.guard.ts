import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

// TODO(#19): gate on real admin role once the backend exposes one.
// Currently delegates to the same authentication check as authGuard so the
// seam exists and admin routes can be tightened without touching app.routes.ts.
export const adminGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  if (auth.isAuthenticated()) {
    return true;
  }
  return router.createUrlTree(['/login']);
};
