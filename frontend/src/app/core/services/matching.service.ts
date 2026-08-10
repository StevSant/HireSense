import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiClient, API_ROUTES } from '@core/api';
import { AnalyzeRequest } from '@core/contracts/analyze-request.model';
import { EvaluateRequest } from '@core/contracts/evaluate-request.model';
import { EvaluationResult } from '@core/contracts/evaluation-result.model';
import { MatchResult } from '@core/contracts/match-result.model';

@Injectable({ providedIn: 'root' })
export class MatchingService {
  constructor(private api: ApiClient) {}

  analyze(payload: AnalyzeRequest): Observable<MatchResult> {
    return this.api.post<MatchResult>(API_ROUTES.matching.analyze(), payload);
  }

  evaluate(request: EvaluateRequest): Observable<EvaluationResult> {
    return this.api.post<EvaluationResult>(API_ROUTES.matching.evaluate(), request);
  }
}
