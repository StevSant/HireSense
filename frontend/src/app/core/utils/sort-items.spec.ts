import { describe, expect, it } from 'vitest';
import { sortItems } from './sort-items';

interface Row {
  id: string;
  n: number | null;
  s: string | null;
}

describe('sortItems', () => {
  it('sorts numbers ascending and descending', () => {
    const rows: Row[] = [
      { id: 'a', n: 3, s: null },
      { id: 'b', n: 1, s: null },
    ];
    expect(sortItems(rows, (r) => r.n, 'asc').map((r) => r.id)).toEqual(['b', 'a']);
    expect(sortItems(rows, (r) => r.n, 'desc').map((r) => r.id)).toEqual(['a', 'b']);
  });

  it('sorts strings case-insensitively', () => {
    const rows: Row[] = [
      { id: 'z', n: 0, s: 'zeta' },
      { id: 'a', n: 0, s: 'Alpha' },
    ];
    expect(sortItems(rows, (r) => r.s, 'asc').map((r) => r.id)).toEqual(['a', 'z']);
  });

  it('places null/empty values last regardless of direction', () => {
    const rows: Row[] = [
      { id: 'x', n: null, s: null },
      { id: 'y', n: 5, s: 'hi' },
    ];
    expect(sortItems(rows, (r) => r.n, 'asc').map((r) => r.id)).toEqual(['y', 'x']);
    expect(sortItems(rows, (r) => r.n, 'desc').map((r) => r.id)).toEqual(['y', 'x']);
  });

  it('does not mutate the input array', () => {
    const rows: Row[] = [
      { id: 'a', n: 2, s: null },
      { id: 'b', n: 1, s: null },
    ];
    sortItems(rows, (r) => r.n, 'asc');
    expect(rows.map((r) => r.id)).toEqual(['a', 'b']);
  });
});
