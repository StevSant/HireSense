/**
 * One page of a list endpoint plus the server's total row count.
 *
 * Several backend list endpoints return a bare JSON array and carry the count
 * out of band in the `X-Total-Count` response header; this is the shape the
 * frontend normalizes them into so callers never have to touch headers.
 *
 * `total` is the number of rows that match on the server — it is independent of
 * how many are in `items`, which is bounded by the requested page size.
 */
export interface PagedResult<T> {
  readonly items: T[];
  readonly total: number;
}
