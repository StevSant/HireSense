import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { EvaluateRequest } from '../../pages/matching/models/evaluate-request.model';
import { EvaluationResult } from '../../pages/matching/models/evaluation-result.model';
import { MatchResult } from '../../pages/matching/models/match-result.model';

export interface AnalyzeRequest {
  job_id: string;
  cv_id: string;
  job_description: string;
  job_skills: string[];
  cv_summary: string;
  cv_skills: string[];
}

@Injectable({ providedIn: 'root' })
export class MatchingService {
  constructor(private http: HttpClient) {}

  analyze(payload: AnalyzeRequest): Observable<MatchResult> {
    return this.http.post<MatchResult>(`${environment.apiUrl}/matching/analyze`, payload);
  }

  evaluate(request: EvaluateRequest): Observable<EvaluationResult> {
    return this.http.post<EvaluationResult>(`${environment.apiUrl}/matching/evaluate`, request);
  }
}
