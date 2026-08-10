import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

import { FeatureView } from '@core/contracts/feature-view.model';
import { LLMProvider } from '@core/contracts/llm-provider.model';
import { AdminLLMSettingsStore } from './admin-llm-settings.store';
import { LLM_PROVIDERS } from './constants/llm-provider-suggestions';

/**
 * Admin → LLM settings.
 *
 * A view over AdminLLMSettingsStore: every signal below is the store's own
 * signal re-exposed under the name the template already used, and every
 * handler is a straight delegation apart from `onBackdropClick`, which has to
 * inspect the clicked element before it can decide anything.
 */
@Component({
  selector: 'app-admin-llm-settings',
  standalone: true,
  imports: [CommonModule, FormsModule],
  providers: [AdminLLMSettingsStore],
  templateUrl: './admin-llm-settings.component.html',
  styleUrl: './admin-llm-settings.component.scss',
})
export class AdminLLMSettingsComponent implements OnInit {
  private store = inject(AdminLLMSettingsStore);

  readonly providers = LLM_PROVIDERS;

  loading = this.store.loading;
  saving = this.store.saving;
  testing = this.store.testing;
  error = this.store.error;
  successMessage = this.store.successMessage;

  current = this.store.current;
  testResult = this.store.testResult;
  hasTestedSinceEdit = this.store.hasTestedSinceEdit;

  formProvider = this.store.formProvider;
  formModel = this.store.formModel;
  formApiKey = this.store.formApiKey;
  formExtras = this.store.formExtras;

  features = this.store.features;
  editingOverride = this.store.editingOverride;
  overrideTesting = this.store.overrideTesting;
  overrideTestResult = this.store.overrideTestResult;
  overrideError = this.store.overrideError;

  modelSuggestions = this.store.modelSuggestions;

  ngOnInit(): void {
    this.store.init();
  }

  refresh(): void {
    this.store.refresh();
  }

  // ---- Global form ------------------------------------------------

  onProviderChange(provider: LLMProvider): void {
    this.store.onProviderChange(provider);
  }

  onModelChange(model: string): void {
    this.store.onModelChange(model);
  }

  onApiKeyChange(key: string): void {
    this.store.onApiKeyChange(key);
  }

  addExtra(): void {
    this.store.addExtra();
  }

  removeExtra(idx: number): void {
    this.store.removeExtra(idx);
  }

  setExtraKey(idx: number, value: string): void {
    this.store.setExtraKey(idx, value);
  }

  setExtraValue(idx: number, value: string): void {
    this.store.setExtraValue(idx, value);
  }

  test(): void {
    this.store.test();
  }

  save(skipTest = false): void {
    this.store.save(skipTest);
  }

  // ---- Overrides -------------------------------------------------

  startEdit(feature: FeatureView): void {
    this.store.startEdit(feature);
  }

  cancelEdit(): void {
    this.store.cancelEdit();
  }

  /** Close the edit modal only when the backdrop itself (not the dialog) is clicked. */
  onBackdropClick(event: MouseEvent): void {
    if ((event.target as HTMLElement).classList.contains('modal-backdrop')) {
      this.store.cancelEdit();
    }
  }

  setOverrideInheritProvider(inherit: boolean): void {
    this.store.setOverrideInheritProvider(inherit);
  }

  setOverrideInheritModel(inherit: boolean): void {
    this.store.setOverrideInheritModel(inherit);
  }

  setOverrideProvider(provider: string): void {
    this.store.setOverrideProvider(provider);
  }

  setOverrideModel(model: string): void {
    this.store.setOverrideModel(model);
  }

  setOverrideExtraKey(idx: number, value: string): void {
    this.store.setOverrideExtraKey(idx, value);
  }

  setOverrideExtraValue(idx: number, value: string): void {
    this.store.setOverrideExtraValue(idx, value);
  }

  addOverrideExtra(): void {
    this.store.addOverrideExtra();
  }

  removeOverrideExtra(idx: number): void {
    this.store.removeOverrideExtra(idx);
  }

  testOverride(): void {
    this.store.testOverride();
  }

  saveOverride(): void {
    this.store.saveOverride();
  }

  resetOverride(feature: FeatureView): void {
    this.store.resetOverride(feature);
  }
}
