/**
 * Returns true when a JWT is missing, malformed, has no `exp` claim, or is
 * past its expiry. The payload is decoded locally for client-side auth state
 * only — the backend remains the authority on signature validity. This keeps
 * the auth guard from admitting users on a token the API will reject with 401.
 */
export function isTokenExpired(token: string | null): boolean {
  if (!token) {
    return true;
  }
  const segments = token.split('.');
  if (segments.length !== 3) {
    return true;
  }
  try {
    const json = atob(segments[1].replace(/-/g, '+').replace(/_/g, '/'));
    const payload = JSON.parse(json) as { exp?: number };
    if (typeof payload.exp !== 'number') {
      return true;
    }
    return Date.now() >= payload.exp * 1000;
  } catch {
    return true;
  }
}
