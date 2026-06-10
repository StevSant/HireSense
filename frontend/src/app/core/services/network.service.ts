import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { NetworkImportResult } from '../../pages/profile/models/network-import-result.model';
import { NetworkMatchResponse } from '../../pages/profile/models/network-match-response.model';

@Injectable({ providedIn: 'root' })
export class NetworkService {
  private http = inject(HttpClient);
  private base = `${environment.apiUrl}/network`;

  import(file: File): Observable<NetworkImportResult> {
    const form = new FormData();
    form.append('file', file);
    return this.http.post<NetworkImportResult>(`${this.base}/import`, form);
  }

  match(company: string): Observable<NetworkMatchResponse> {
    const params = new HttpParams().set('company', company);
    return this.http.get<NetworkMatchResponse>(`${this.base}/match`, { params });
  }
}
