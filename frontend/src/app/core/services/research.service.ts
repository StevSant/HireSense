import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { CompanyResearch } from '@core/contracts/company-research.model';
import { ResearchRequest } from '@core/contracts/research-request.model';

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
