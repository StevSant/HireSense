import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiClient, API_ROUTES } from '@core/api';
import { OptimizationResult } from '@core/contracts/optimization-result.model';

export interface OptimizeRequest {
  match_id: string;
  job_id: string;
  cv_id: string;
  original_tex: string;
  job_description: string;
  job_skills: string[];
  missing_skills: string[];
  recommendations: string[];
}

@Injectable({ providedIn: 'root' })
export class OptimizationService {
  constructor(private api: ApiClient) {}

  optimize(payload: OptimizeRequest): Observable<OptimizationResult> {
    return this.api.post<OptimizationResult>(API_ROUTES.optimization.optimize(), payload);
  }
}
