import { HttpClient, HttpParams, HttpResponse } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '@env/environment';
import { ApiPath } from './api-route.model';

/** Query parameters, in either of the two shapes `HttpClient` already accepts. */
export type ApiQueryParams =
  HttpParams | Record<string, string | number | boolean | readonly (string | number | boolean)[]>;

export interface ApiRequestOptions {
  readonly params?: ApiQueryParams;
}

/**
 * The one place `environment.apiUrl` is joined to a path.
 *
 * Deliberately thin: it prefixes the URL and types the response, nothing more.
 * Caching, retries, auth and error handling belong to the interceptor chain,
 * which sees these requests exactly like any other.
 */
@Injectable({ providedIn: 'root' })
export class ApiClient {
  private readonly http = inject(HttpClient);

  /** The request URL for `path` — for callers that need an href, not a request. */
  url(path: ApiPath): string {
    return `${environment.apiUrl}${path}`;
  }

  get<T>(path: ApiPath, options: ApiRequestOptions = {}): Observable<T> {
    return this.http.get<T>(this.url(path), { params: options.params });
  }

  /** For callers that need the status line or headers, not just the body. */
  getResponse<T>(path: ApiPath, options: ApiRequestOptions = {}): Observable<HttpResponse<T>> {
    return this.http.get<T>(this.url(path), { params: options.params, observe: 'response' });
  }

  getBlob(path: ApiPath, options: ApiRequestOptions = {}): Observable<Blob> {
    return this.http.get(this.url(path), { params: options.params, responseType: 'blob' });
  }

  post<T>(path: ApiPath, body: unknown, options: ApiRequestOptions = {}): Observable<T> {
    return this.http.post<T>(this.url(path), body, { params: options.params });
  }

  put<T>(path: ApiPath, body: unknown, options: ApiRequestOptions = {}): Observable<T> {
    return this.http.put<T>(this.url(path), body, { params: options.params });
  }

  patch<T>(path: ApiPath, body: unknown, options: ApiRequestOptions = {}): Observable<T> {
    return this.http.patch<T>(this.url(path), body, { params: options.params });
  }

  delete<T>(path: ApiPath, options: ApiRequestOptions = {}): Observable<T> {
    return this.http.delete<T>(this.url(path), { params: options.params });
  }
}
