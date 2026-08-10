import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { ApiClient, API_ROUTES } from '@core/api';
import { FeatureOverrideRequest } from '@core/contracts/feature-override-request.model';
import { FeatureView } from '@core/contracts/feature-view.model';
import { LLMSettings } from '@core/contracts/llm-settings.model';
import { LLMSettingsTestRequest } from '@core/contracts/llm-settings-test-request.model';
import { LLMSettingsUpdateRequest } from '@core/contracts/llm-settings-update-request.model';
import { LLMTestResult } from '@core/contracts/llm-test-result.model';

@Injectable({ providedIn: 'root' })
export class AdminLLMSettingsService {
  constructor(private api: ApiClient) {}

  // ---- Global config ----------------------------------------------

  getSettings(): Observable<LLMSettings> {
    return this.api.get<LLMSettings>(API_ROUTES.admin.llmSettings.root());
  }

  updateSettings(body: LLMSettingsUpdateRequest): Observable<LLMSettings> {
    return this.api.put<LLMSettings>(API_ROUTES.admin.llmSettings.root(), body);
  }

  testSettings(body: LLMSettingsTestRequest): Observable<LLMTestResult> {
    return this.api.post<LLMTestResult>(API_ROUTES.admin.llmSettings.test(), body);
  }

  // ---- Per-feature overrides --------------------------------------

  listFeatures(): Observable<FeatureView[]> {
    return this.api.get<FeatureView[]>(API_ROUTES.admin.llmSettings.overrides());
  }

  upsertOverride(featureKey: string, body: FeatureOverrideRequest): Observable<FeatureView> {
    return this.api.put<FeatureView>(API_ROUTES.admin.llmSettings.override({ featureKey }), body);
  }

  clearOverride(featureKey: string): Observable<FeatureView> {
    return this.api.delete<FeatureView>(API_ROUTES.admin.llmSettings.override({ featureKey }));
  }

  testOverride(featureKey: string, body: FeatureOverrideRequest): Observable<LLMTestResult> {
    return this.api.post<LLMTestResult>(
      API_ROUTES.admin.llmSettings.overrideTest({ featureKey }),
      body,
    );
  }
}
