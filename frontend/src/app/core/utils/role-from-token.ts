/**
 * Returns the `role` claim from a JWT, or `null` when the token is missing,
 * malformed, or has no string `role`. The payload is decoded locally for
 * client-side UI hints only (e.g. showing/hiding admin nav) — the backend
 * remains the authority on the role via the 403-gated admin routes.
 */
export function roleFromToken(token: string | null): string | null {
  if (!token) {
    return null;
  }
  const segments = token.split('.');
  if (segments.length !== 3) {
    return null;
  }
  try {
    const json = atob(segments[1].replace(/-/g, '+').replace(/_/g, '/'));
    const payload = JSON.parse(json) as { role?: unknown };
    return typeof payload.role === 'string' ? payload.role : null;
  } catch {
    return null;
  }
}
