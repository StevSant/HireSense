import { describe, expect, it } from 'vitest';
import { parseSortToken } from './parse-sort-token';

describe('parseSortToken', () => {
  it('parses a valid field_dir token', () => {
    expect(parseSortToken('created_desc')).toEqual({ field: 'created', dir: 'desc' });
    expect(parseSortToken('company_asc')).toEqual({ field: 'company', dir: 'asc' });
  });

  it('uses the last underscore as the separator', () => {
    expect(parseSortToken('total_tokens_desc')).toEqual({ field: 'total_tokens', dir: 'desc' });
  });

  it('returns null for malformed tokens', () => {
    expect(parseSortToken('created')).toBeNull();
    expect(parseSortToken('created_sideways')).toBeNull();
    expect(parseSortToken('')).toBeNull();
  });
});
