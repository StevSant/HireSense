import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { PortfolioProjectsResponse } from '../../pages/profile/models/portfolio-projects-response.model';
import { PortfolioSyncResult } from '../../pages/profile/models/portfolio-sync-result.model';

@Injectable({ providedIn: 'root' })
export class PortfolioService {
  private http = inject(HttpClient);
  private base = `${environment.apiUrl}/portfolio`;

  listProjects(): Observable<PortfolioProjectsResponse> {
    return this.http.get<PortfolioProjectsResponse>(`${this.base}/projects`);
  }

  sync(): Observable<PortfolioSyncResult> {
    return this.http.post<PortfolioSyncResult>(`${this.base}/sync`, {});
  }
}
