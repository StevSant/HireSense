import { Component, DestroyRef, OnInit, inject, signal, computed } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

import { AdminLLMSettingsService } from '../../core/services/admin-llm-settings.service';
import {
  LLM_PROVIDERS,
  MODEL_SUGGESTIONS,
} from './constants/llm-provider-suggestions';
import { ExtraParam } from './models/extra-param.model';
import { FeatureView } from './models/feature-view.model';
import { LLMProvider } from './models/llm-provider.model';
import { LLMSettings } from './models/llm-settings.model';
import { LLMTestResult } from './models/llm-test-result.model';
import { OverrideDraft } from './models/override-draft.model';

@Component({
  selector: 'app-admin-llm-settings',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './admin-llm-settings.component.html',
  styleUrl: './admin-llm-settings.component.scss',
})
export class AdminLLMSettingsComponent implements OnInit {
  readonly providers = LLM_PROVIDERS;

  loading = signal(false);
  saving = signal(false);
  testing = signal(false);
  error = signal('');
  successMessage = signal('');

  current = signal<LLMSettings | null>(null);
  testResult = signal<LLMTestResult | null>(null);
  hasTestedSinceEdit = signal(false);

  // Global form state
  formProvider = signal<LLMProvider>('anthropic');
  formModel = signal('');
  formApiKey = signal('');
  formExtras = signal<ExtraParam[]>([]);

  // Override management
  features = signal<FeatureView[]>([]);
  editingOverride = signal<OverrideDraft | null>(null);
  overrideTesting = signal(false);
  overrideTestResult = signal<LLMTestResult | null>(null);
  overrideError = signal('');

  modelSuggestions = computed(() => MODEL_SUGGESTIONS[this.formProvider()] ?? []);

  private readonly destroyRef = inject(DestroyRef);

  constructor(private api: AdminLLMSettingsService) {}

  ngOnInit(): void {
    this.refresh();
  }

  refresh(): void {
    this.loading.set(true);
    this.error.set('');
    this.api.getSettings().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (settings) => {
        this.current.set(settings);
        this.formProvider.set((LLM_PROVIDERS as readonly string[]).includes(settings.provider)
          ? (settings.provider as LLMProvider)
          : 'anthropic');
        this.formModel.set(settings.model);
        this.formApiKey.set('');
        this.formExtras.set(toExtraList(settings.extra_params));
        this.testResult.set(null);
        this.hasTestedSinceEdit.set(false);
        this.loadFeatures();
      },
      error: (err) => {
        this.error.set(err?.error?.detail ?? 'Failed to load settings');
        this.loading.set(false);
      },
    });
  }

  private loadFeatures(): void {
    this.api.listFeatures().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (features) => {
        this.features.set(features);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(err?.error?.detail ?? 'Failed to load features');
        this.loading.set(false);
      },
    });
  }

  // ---- Global form ------------------------------------------------

  onProviderChange(provider: LLMProvider): void {
    this.formProvider.set(provider);
    this.hasTestedSinceEdit.set(false);
  }

  onModelChange(model: string): void {
    this.formModel.set(model);
    this.hasTestedSinceEdit.set(false);
  }

  onApiKeyChange(key: string): void {
    this.formApiKey.set(key);
    this.hasTestedSinceEdit.set(false);
  }

  addExtra(): void {
    this.formExtras.update((xs) => [...xs, { key: '', value: '' }]);
  }

  removeExtra(idx: number): void {
    this.formExtras.update((xs) => xs.filter((_, i) => i !== idx));
    this.hasTestedSinceEdit.set(false);
  }

  setExtraKey(idx: number, value: string): void {
    this.formExtras.update((xs) => xs.map((x, i) => (i === idx ? { ...x, key: value } : x)));
    this.hasTestedSinceEdit.set(false);
  }

  setExtraValue(idx: number, value: string): void {
    this.formExtras.update((xs) => xs.map((x, i) => (i === idx ? { ...x, value } : x)));
    this.hasTestedSinceEdit.set(false);
  }

  test(): void {
    this.testing.set(true);
    this.testResult.set(null);
    this.error.set('');
    const apiKey = this.formApiKey().trim();
    this.api
      .testSettings({
        provider: this.formProvider(),
        model: this.formModel(),
        api_key: apiKey ? apiKey : null,
        extra_params: extrasToObject(this.formExtras()),
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (result) => {
          this.testResult.set(result);
          this.hasTestedSinceEdit.set(true);
          this.testing.set(false);
        },
        error: (err) => {
          this.error.set(err?.error?.detail ?? 'Test failed');
          this.testing.set(false);
        },
      });
  }

  save(skipTest = false): void {
    if (!skipTest && !this.hasTestedSinceEdit()) {
      const confirmed = window.confirm(
        'Save without running a test call first? An invalid config will be rejected anyway, but skipping the test means the rejection happens during save instead of upfront.',
      );
      if (!confirmed) {
        return;
      }
      skipTest = true;
    }
    this.saving.set(true);
    this.error.set('');
    this.successMessage.set('');
    const apiKey = this.formApiKey().trim();
    this.api
      .updateSettings({
        provider: this.formProvider(),
        model: this.formModel(),
        api_key: apiKey ? apiKey : null,
        extra_params: extrasToObject(this.formExtras()),
        skip_test: skipTest,
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (settings) => {
          this.current.set(settings);
          this.formApiKey.set('');
          this.saving.set(false);
          this.successMessage.set('Settings saved.');
          this.hasTestedSinceEdit.set(false);
          this.loadFeatures();
        },
        error: (err) => {
          this.error.set(err?.error?.detail ?? 'Save failed');
          this.saving.set(false);
        },
      });
  }

  // ---- Overrides -------------------------------------------------

  startEdit(feature: FeatureView): void {
    this.overrideTestResult.set(null);
    this.overrideError.set('');
    this.editingOverride.set({
      feature_key: feature.feature_key,
      provider: feature.inherits_provider ? '' : feature.provider,
      model: feature.inherits_model ? '' : feature.model,
      inherit_provider: feature.inherits_provider,
      inherit_model: feature.inherits_model,
      extra: toExtraList(feature.extra_params),
    });
  }

  cancelEdit(): void {
    this.editingOverride.set(null);
    this.overrideTestResult.set(null);
    this.overrideError.set('');
  }

  /** Close the edit modal only when the backdrop itself (not the dialog) is clicked. */
  onBackdropClick(event: MouseEvent): void {
    if ((event.target as HTMLElement).classList.contains('modal-backdrop')) {
      this.cancelEdit();
    }
  }

  setOverrideInheritProvider(inherit: boolean): void {
    this.editingOverride.update((d) =>
      d ? { ...d, inherit_provider: inherit, provider: inherit ? '' : d.provider } : d,
    );
  }

  setOverrideInheritModel(inherit: boolean): void {
    this.editingOverride.update((d) =>
      d ? { ...d, inherit_model: inherit, model: inherit ? '' : d.model } : d,
    );
  }

  setOverrideProvider(provider: string): void {
    this.editingOverride.update((d) => (d ? { ...d, provider } : d));
  }

  setOverrideModel(model: string): void {
    this.editingOverride.update((d) => (d ? { ...d, model } : d));
  }

  setOverrideExtraKey(idx: number, value: string): void {
    this.editingOverride.update((d) => {
      if (!d) return d;
      const extra = d.extra.map((x, i) => (i === idx ? { ...x, key: value } : x));
      return { ...d, extra };
    });
  }

  setOverrideExtraValue(idx: number, value: string): void {
    this.editingOverride.update((d) => {
      if (!d) return d;
      const extra = d.extra.map((x, i) => (i === idx ? { ...x, value } : x));
      return { ...d, extra };
    });
  }

  addOverrideExtra(): void {
    this.editingOverride.update((d) => (d ? { ...d, extra: [...d.extra, { key: '', value: '' }] } : d));
  }

  removeOverrideExtra(idx: number): void {
    this.editingOverride.update((d) =>
      d ? { ...d, extra: d.extra.filter((_, i) => i !== idx) } : d,
    );
  }

  testOverride(): void {
    const draft = this.editingOverride();
    if (!draft) return;
    this.overrideTesting.set(true);
    this.overrideTestResult.set(null);
    this.overrideError.set('');
    this.api
      .testOverride(draft.feature_key, {
        provider: draft.inherit_provider ? null : draft.provider,
        model: draft.inherit_model ? null : draft.model,
        extra_params: extrasToObject(draft.extra),
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (result) => {
          this.overrideTestResult.set(result);
          this.overrideTesting.set(false);
        },
        error: (err) => {
          this.overrideError.set(err?.error?.detail ?? 'Test failed');
          this.overrideTesting.set(false);
        },
      });
  }

  saveOverride(): void {
    const draft = this.editingOverride();
    if (!draft) return;
    this.api
      .upsertOverride(draft.feature_key, {
        provider: draft.inherit_provider ? null : draft.provider,
        model: draft.inherit_model ? null : draft.model,
        extra_params: extrasToObject(draft.extra),
        skip_test: this.overrideTestResult()?.success === true,
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.editingOverride.set(null);
          this.overrideTestResult.set(null);
          this.loadFeatures();
        },
        error: (err) => {
          this.overrideError.set(err?.error?.detail ?? 'Save failed');
        },
      });
  }

  resetOverride(feature: FeatureView): void {
    if (feature.source !== 'override') return;
    const ok = window.confirm(
      `Reset ${feature.feature_name} to global config? The next call will use the global provider/model.`,
    );
    if (!ok) return;
    this.api.clearOverride(feature.feature_key).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: () => this.loadFeatures(),
      error: (err) => this.overrideError.set(err?.error?.detail ?? 'Reset failed'),
    });
  }
}

function toExtraList(obj: Record<string, unknown> | null | undefined): ExtraParam[] {
  if (!obj) return [];
  return Object.entries(obj).map(([key, value]) => ({ key, value: String(value ?? '') }));
}

function extrasToObject(extras: ExtraParam[]): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const { key, value } of extras) {
    const trimmed = key.trim();
    if (!trimmed) continue;
    const parsedNum = Number(value);
    if (value !== '' && !Number.isNaN(parsedNum) && /^-?\d+(\.\d+)?$/.test(value.trim())) {
      out[trimmed] = parsedNum;
    } else if (value === 'true' || value === 'false') {
      out[trimmed] = value === 'true';
    } else {
      out[trimmed] = value;
    }
  }
  return out;
}
