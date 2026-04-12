import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { OptimizationResult } from '../../pages/optimization/models/optimization-result.model';

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
  constructor(private http: HttpClient) {}

  optimize(payload: OptimizeRequest): Observable<OptimizationResult> {
    return this.http.post<OptimizationResult>(`${environment.apiUrl}/optimization/optimize`, payload);
  }
}
