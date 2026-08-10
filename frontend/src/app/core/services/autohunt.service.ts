import { Injectable, inject } from '@angular/core';
import { HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';
import { ApiClient, API_ROUTES } from '@core/api';
import { Digest } from '@core/contracts/digest.model';

@Injectable({ providedIn: 'root' })
export class AutohuntService {
  private api = inject(ApiClient);

  latest(): Observable<Digest | null> {
    // The endpoint returns HTTP 204 with an empty body when no digest exists.
    // Observe the full response so an empty body maps to null instead of
    // throwing a JSON parse error.
    return this.api
      .getResponse<Digest>(API_ROUTES.autohunt.latestDigest())
      .pipe(map((res) => (res.status === 204 || !res.body ? null : res.body)));
  }

  listRecent(limit = 20, sort?: string): Observable<Digest[]> {
    let params = new HttpParams().set('limit', limit);
    if (sort) params = params.set('sort', sort);
    return this.api.get<Digest[]>(API_ROUTES.autohunt.digests(), { params });
  }

  run(): Observable<Digest> {
    return this.api.post<Digest>(API_ROUTES.autohunt.run(), {});
  }
}
