import { describe, expect, it } from 'vitest';
import { isTokenExpired } from './is-token-expired';

function makeToken(exp: number | undefined): string {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
  const claims = exp === undefined ? { sub: 'admin' } : { sub: 'admin', exp };
  const payload = btoa(JSON.stringify(claims));
  return `${header}.${payload}.signature`;
}

describe('isTokenExpired', () => {
  it('treats a null token as expired', () => {
    expect(isTokenExpired(null)).toBe(true);
  });

  it('treats a malformed (non-JWT) token as expired', () => {
    expect(isTokenExpired('not-a-jwt')).toBe(true);
  });

  it('treats a token without an exp claim as expired', () => {
    expect(isTokenExpired(makeToken(undefined))).toBe(true);
  });

  it('treats a token whose exp is in the past as expired', () => {
    const past = Math.floor(Date.now() / 1000) - 60;
    expect(isTokenExpired(makeToken(past))).toBe(true);
  });

  it('treats a token whose exp is in the future as valid', () => {
    const future = Math.floor(Date.now() / 1000) + 3600;
    expect(isTokenExpired(makeToken(future))).toBe(false);
  });
});
