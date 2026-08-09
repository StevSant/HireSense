import { HttpResponse } from '@angular/common/http';
import { PagedResult } from '../models/paged-result.model';

// Header the backend list endpoints set alongside a bare-array body.
const TOTAL_COUNT_HEADER = 'X-Total-Count';

/**
 * Normalize a bare-array list response into a {@link PagedResult}.
 *
 * Falls back to the returned row count when `X-Total-Count` is absent or
 * unparseable — an endpoint that has not adopted the header yet then behaves
 * exactly as it did before (one page, total = what came back) instead of
 * reporting zero rows and blanking the UI.
 */
export function toPagedResult<T>(response: HttpResponse<T[]>): PagedResult<T> {
  const items = response.body ?? [];
  const raw = response.headers.get(TOTAL_COUNT_HEADER);
  const parsed = raw === null ? Number.NaN : Number(raw);
  const total = Number.isFinite(parsed) && parsed >= 0 ? parsed : items.length;
  return { items, total };
}
