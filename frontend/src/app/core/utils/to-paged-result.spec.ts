import { HttpHeaders, HttpResponse } from '@angular/common/http';
import { toPagedResult } from './to-paged-result';

function response(body: number[] | null, headers: Record<string, string> = {}) {
  return new HttpResponse<number[]>({ body, headers: new HttpHeaders(headers) });
}

describe('toPagedResult', () => {
  it('reads the total from the X-Total-Count header', () => {
    const result = toPagedResult(response([1, 2], { 'X-Total-Count': '57' }));
    expect(result).toEqual({ items: [1, 2], total: 57 });
  });

  it('falls back to the row count when the header is missing', () => {
    const result = toPagedResult(response([1, 2, 3]));
    expect(result).toEqual({ items: [1, 2, 3], total: 3 });
  });

  it('falls back to the row count when the header is not a number', () => {
    const result = toPagedResult(response([1], { 'X-Total-Count': 'many' }));
    expect(result).toEqual({ items: [1], total: 1 });
  });

  it('treats a null body as an empty page', () => {
    const result = toPagedResult(response(null, { 'X-Total-Count': '0' }));
    expect(result).toEqual({ items: [], total: 0 });
  });

  it('honours a zero total', () => {
    const result = toPagedResult(response([], { 'X-Total-Count': '0' }));
    expect(result).toEqual({ items: [], total: 0 });
  });
});
