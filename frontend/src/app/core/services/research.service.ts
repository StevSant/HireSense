import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiClient, API_ROUTES } from '@core/api';
import { CompanyResearch } from '@core/contracts/company-research.model';
import { ResearchRequest } from '@core/contracts/research-request.model';

@Injectable({ providedIn: 'root' })
export class ResearchService {
  constructor(private api: ApiClient) {}

  research(request: ResearchRequest): Observable<CompanyResearch> {
    return this.api.post<CompanyResearch>(API_ROUTES.research.root(), request);
  }

  refresh(request: ResearchRequest): Observable<CompanyResearch> {
    return this.api.post<CompanyResearch>(API_ROUTES.research.refresh(), request);
  }

  get(companyName: string): Observable<CompanyResearch> {
    // The route encodes `:companyName`, so no escaping is done here.
    return this.api.get<CompanyResearch>(API_ROUTES.research.byCompany({ companyName }));
  }
}
