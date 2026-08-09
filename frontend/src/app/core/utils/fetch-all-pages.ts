import { EMPTY, Observable, expand, map, reduce } from 'rxjs';
import { PagedResult } from '../models/paged-result.model';
import { environment } from '../../../environments/environment';

/** A single page request: `(limit, offset) => that page plus the server total`. */
export type PageFetcher<T> = (limit: number, offset: number) => Observable<PagedResult<T>>;

/**
 * Walk a paged endpoint to completion and emit every row once.
 *
 * Screens that sort, filter, or count client-side need the *whole* list — with
 * only the first page they silently drop rows and compute wrong totals. This
 * keeps requesting pages until the server total is covered, then emits a single
 * {@link PagedResult} whose `total` is what the server reported.
 *
 * `total` can exceed `items.length` when the walk stops at `maxItems`; callers
 * should compare the two and surface a truncation notice rather than implying
 * the list is complete.
 *
 * Termination is guarded three ways so a wrong or drifting server total can
 * never spin an infinite request loop: the covered-offset check, an empty page,
 * and the `maxItems` ceiling.
 */
export function fetchAllPages<T>(
  fetchPage: PageFetcher<T>,
  opts: { pageSize?: number; maxItems?: number } = {},
): Observable<PagedResult<T>> {
  const pageSize = opts.pageSize ?? environment.listPageSize;
  const maxItems = opts.maxItems ?? environment.listMaxItems;

  const step = (offset: number) =>
    fetchPage(pageSize, offset).pipe(map((page) => ({ page, offset })));

  return step(0).pipe(
    expand(({ page, offset }) => {
      const loaded = offset + page.items.length;
      const exhausted = page.items.length === 0 || loaded >= page.total;
      return exhausted || loaded >= maxItems ? EMPTY : step(loaded);
    }),
    reduce<{ page: PagedResult<T>; offset: number }, PagedResult<T>>(
      (acc, { page }) => ({
        items: acc.items.concat(page.items),
        total: page.total,
      }),
      { items: [], total: 0 },
    ),
  );
}
