import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AnalyzeRequest } from '@core/contracts/analyze-request.model';
import { EvaluateRequest } from '@core/contracts/evaluate-request.model';
import { EvaluationResult } from '@core/contracts/evaluation-result.model';
import { MatchResult } from '@core/contracts/match-result.model';

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
