import { describe, expect, it } from 'vitest';
import { roleFromToken } from './role-from-token';

function makeToken(claims: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
  const payload = btoa(JSON.stringify(claims));
  return `${header}.${payload}.signature`;
}

describe('roleFromToken', () => {
  it('returns null for a null token', () => {
    expect(roleFromToken(null)).toBeNull();
  });

  it('returns null for a malformed (non-JWT) token', () => {
    expect(roleFromToken('not-a-jwt')).toBeNull();
  });

  it('returns null when the role claim is missing', () => {
    expect(roleFromToken(makeToken({ sub: 'admin' }))).toBeNull();
  });

  it('returns null when the role claim is not a string', () => {
    expect(roleFromToken(makeToken({ sub: 'admin', role: 123 }))).toBeNull();
  });

  it('decodes the admin role claim', () => {
    expect(roleFromToken(makeToken({ sub: 'admin', role: 'admin' }))).toBe('admin');
  });

  it('decodes a non-admin role claim', () => {
    expect(roleFromToken(makeToken({ sub: 'bob', role: 'member' }))).toBe('member');
  });
});
