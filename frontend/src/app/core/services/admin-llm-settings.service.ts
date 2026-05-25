import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { FeatureOverrideRequest } from '../../pages/admin/models/feature-override-request.model';
import { FeatureView } from '../../pages/admin/models/feature-view.model';
import { LLMSettings } from '../../pages/admin/models/llm-settings.model';
import { LLMSettingsTestRequest } from '../../pages/admin/models/llm-settings-test-request.model';
import { LLMSettingsUpdateRequest } from '../../pages/admin/models/llm-settings-update-request.model';
import { LLMTestResult } from '../../pages/admin/models/llm-test-result.model';

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
