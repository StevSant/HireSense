import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

// #38: gate on the real admin role. The role is read from the JWT's `role`
// claim (client-side hint); the backend enforces it for real by returning 403
// on the admin routes. An authenticated non-admin is sent to the dashboard
// (they're logged in, just not authorized); anyone unauthenticated goes to login.
export const adminGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  if (!auth.isAuthenticated()) {
    return router.createUrlTree(['/login']);
  }
  if (!auth.isAdmin()) {
    return router.createUrlTree(['/dashboard']);
  }
  return true;
};
