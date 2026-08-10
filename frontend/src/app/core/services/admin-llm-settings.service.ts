import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { FeatureOverrideRequest } from '@core/contracts/feature-override-request.model';
import { FeatureView } from '@core/contracts/feature-view.model';
import { LLMSettings } from '@core/contracts/llm-settings.model';
import { LLMSettingsTestRequest } from '@core/contracts/llm-settings-test-request.model';
import { LLMSettingsUpdateRequest } from '@core/contracts/llm-settings-update-request.model';
import { LLMTestResult } from '@core/contracts/llm-test-result.model';

@Injectable({ providedIn: 'root' })
export class AdminLLMSettingsService {
  private readonly base = `${environment.apiUrl}/admin/llm-settings`;

  constructor(private http: HttpClient) {}

  // ---- Global config ----------------------------------------------

  getSettings(): Observable<LLMSettings> {
    return this.http.get<LLMSettings>(this.base);
  }

  updateSettings(body: LLMSettingsUpdateRequest): Observable<LLMSettings> {
    return this.http.put<LLMSettings>(this.base, body);
  }

  testSettings(body: LLMSettingsTestRequest): Observable<LLMTestResult> {
    return this.http.post<LLMTestResult>(`${this.base}/test`, body);
  }

  // ---- Per-feature overrides --------------------------------------

  listFeatures(): Observable<FeatureView[]> {
    return this.http.get<FeatureView[]>(`${this.base}/overrides`);
  }

  upsertOverride(featureKey: string, body: FeatureOverrideRequest): Observable<FeatureView> {
    return this.http.put<FeatureView>(`${this.base}/overrides/${featureKey}`, body);
  }

  clearOverride(featureKey: string): Observable<FeatureView> {
    return this.http.delete<FeatureView>(`${this.base}/overrides/${featureKey}`);
  }

  testOverride(featureKey: string, body: FeatureOverrideRequest): Observable<LLMTestResult> {
    return this.http.post<LLMTestResult>(`${this.base}/overrides/${featureKey}/test`, body);
  }
}
