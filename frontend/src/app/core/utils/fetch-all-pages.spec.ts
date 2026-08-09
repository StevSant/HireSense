import { of } from 'rxjs';
import { fetchAllPages } from './fetch-all-pages';
import { PagedResult } from '../models/paged-result.model';

// Builds a fetcher over a fixed array, recording the (limit, offset) of each
// call so tests can assert how the walk stepped through the endpoint.
function fetcherOver(rows: number[], total = rows.length) {
  const calls: { limit: number; offset: number }[] = [];
  const fetchPage = (limit: number, offset: number) => {
    calls.push({ limit, offset });
    return of<PagedResult<number>>({ items: rows.slice(offset, offset + limit), total });
  };
  return { fetchPage, calls };
}

function collect(result: PagedResult<number> | null): PagedResult<number> {
  if (!result) throw new Error('expected fetchAllPages to emit');
  return result;
}

describe('fetchAllPages', () => {
  it('issues a single request when the first page covers the total', () => {
    const { fetchPage, calls } = fetcherOver([1, 2, 3]);
    let out: PagedResult<number> | null = null;

    fetchAllPages(fetchPage, { pageSize: 10 }).subscribe((r) => (out = r));

    expect(collect(out).items).toEqual([1, 2, 3]);
    expect(calls).toEqual([{ limit: 10, offset: 0 }]);
  });

  it('walks every page and concatenates the rows in order', () => {
    const rows = Array.from({ length: 25 }, (_, i) => i);
    const { fetchPage, calls } = fetcherOver(rows);
    let out: PagedResult<number> | null = null;

    fetchAllPages(fetchPage, { pageSize: 10 }).subscribe((r) => (out = r));

    expect(collect(out).items).toEqual(rows);
    expect(collect(out).total).toBe(25);
    expect(calls).toEqual([
      { limit: 10, offset: 0 },
      { limit: 10, offset: 10 },
      { limit: 10, offset: 20 },
    ]);
  });

  it('stops at maxItems and still reports the full server total', () => {
    const rows = Array.from({ length: 100 }, (_, i) => i);
    const { fetchPage, calls } = fetcherOver(rows);
    let out: PagedResult<number> | null = null;

    fetchAllPages(fetchPage, { pageSize: 10, maxItems: 30 }).subscribe((r) => (out = r));

    expect(collect(out).items).toHaveLength(30);
    expect(collect(out).total).toBe(100);
    expect(calls).toHaveLength(3);
  });

  it('stops on an empty page even when the server total overstates the rows', () => {
    // A total that never matches reality would loop forever without the
    // empty-page guard.
    const { fetchPage, calls } = fetcherOver([1, 2, 3], 999);
    let out: PagedResult<number> | null = null;

    fetchAllPages(fetchPage, { pageSize: 2 }).subscribe((r) => (out = r));

    expect(collect(out).items).toEqual([1, 2, 3]);
    expect(calls).toEqual([
      { limit: 2, offset: 0 },
      { limit: 2, offset: 2 },
      { limit: 2, offset: 3 },
    ]);
  });

  it('emits an empty result when the endpoint has no rows', () => {
    const { fetchPage, calls } = fetcherOver([]);
    let out: PagedResult<number> | null = null;

    fetchAllPages(fetchPage, { pageSize: 10 }).subscribe((r) => (out = r));

    expect(collect(out).items).toEqual([]);
    expect(collect(out).total).toBe(0);
    expect(calls).toHaveLength(1);
  });
});
