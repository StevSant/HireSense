import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { map } from 'rxjs/operators';
import { AuthService } from '../services/auth.service';

// Cookie auth: JS can't read the httpOnly session cookie, so the guard resolves
// session state from /auth/me (cached after the first probe) before deciding.
export const authGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  return auth.ensureLoaded().pipe(map((ok) => (ok ? true : router.createUrlTree(['/login']))));
};
