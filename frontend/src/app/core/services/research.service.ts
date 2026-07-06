import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { CompanyResearch } from '../../pages/tracking/models/company-research.model';
import { ResearchRequest } from '../../pages/tracking/models/research-request.model';

@Injectable({ providedIn: 'root' })
export class ResearchService {
  constructor(private http: HttpClient) {}

  research(request: ResearchRequest): Observable<CompanyResearch> {
    return this.http.post<CompanyResearch>(`${environment.apiUrl}/research`, request);
  }

  refresh(request: ResearchRequest): Observable<CompanyResearch> {
    return this.http.post<CompanyResearch>(`${environment.apiUrl}/research/refresh`, request);
  }

  get(companyName: string): Observable<CompanyResearch> {
    return this.http.get<CompanyResearch>(
      `${environment.apiUrl}/research/${encodeURIComponent(companyName)}`,
    );
  }
}
