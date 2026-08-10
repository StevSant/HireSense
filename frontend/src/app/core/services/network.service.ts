import { Injectable, inject } from '@angular/core';
import { HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ApiClient, API_ROUTES } from '@core/api';
import { NetworkImportResult } from '@core/contracts/network-import-result.model';
import { NetworkMatchResponse } from '@core/contracts/network-match-response.model';

@Injectable({ providedIn: 'root' })
export class NetworkService {
  private api = inject(ApiClient);

  import(file: File): Observable<NetworkImportResult> {
    const form = new FormData();
    form.append('file', file);
    return this.api.post<NetworkImportResult>(API_ROUTES.network.import(), form);
  }

  match(company: string): Observable<NetworkMatchResponse> {
    const params = new HttpParams().set('company', company);
    return this.api.get<NetworkMatchResponse>(API_ROUTES.network.match(), { params });
  }
}
