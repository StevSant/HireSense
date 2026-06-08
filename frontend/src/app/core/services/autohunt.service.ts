import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';
import { environment } from '../../../environments/environment';
import { Digest } from '../../pages/autohunt/models/digest.model';

@Injectable({ providedIn: 'root' })
export class AutohuntService {
  private http = inject(HttpClient);
  private base = `${environment.apiUrl}/autohunt`;

  latest(): Observable<Digest | null> {
    // The endpoint returns HTTP 204 with an empty body when no digest exists.
    // Observe the full response so an empty body maps to null instead of
    // throwing a JSON parse error.
    return this.http
      .get<Digest>(`${this.base}/digests/latest`, { observe: 'response' })
      .pipe(map((res) => (res.status === 204 || !res.body ? null : res.body)));
  }

  listRecent(limit = 20, sort?: string): Observable<Digest[]> {
    let params = new HttpParams().set('limit', limit);
    if (sort) params = params.set('sort', sort);
    return this.http.get<Digest[]>(`${this.base}/digests`, { params });
  }

  run(): Observable<Digest> {
    return this.http.post<Digest>(`${this.base}/run`, {});
  }
}
