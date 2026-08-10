import { TestBed } from '@angular/core/testing';
import { Observable, of, throwError } from 'rxjs';
import { AdminLLMSettingsService } from '../../core/services/admin-llm-settings.service';
import { FeatureView } from '@core/contracts/feature-view.model';
import { LLMSettings } from '@core/contracts/llm-settings.model';
import { LLMTestResult } from '@core/contracts/llm-test-result.model';
import { AdminLLMSettingsStore } from './admin-llm-settings.store';

const SETTINGS: LLMSettings = {
  provider: 'openai',
  model: 'gpt-4o-mini',
  api_key_mask: 'sk-***abcd',
  has_stored_key: true,
  extra_params: { temperature: 0.2 },
  updated_by: 'admin',
  updated_at: '2026-06-01T00:00:00Z',
  source: 'database',
};

const OVERRIDDEN_FEATURE: FeatureView = {
  feature_key: 'matching.score',
  feature_name: 'Matching Score',
  feature_description: 'Scores jobs against the profile.',
  provider: 'anthropic',
  model: 'claude-opus-4-7',
  inherits_provider: false,
  inherits_model: false,
  extra_params: { temperature: 0.1 },
  source: 'override',
};

const INHERITED_FEATURE: FeatureView = {
  feature_key: 'cv.generate',
  feature_name: 'CV Generation',
  feature_description: 'Generates tailored CVs.',
  provider: 'openai',
  model: 'gpt-4o-mini',
  inherits_provider: true,
  inherits_model: true,
  extra_params: {},
  source: 'inherited',
};

const TEST_OK: LLMTestResult = {
  success: true,
  latency_ms: 120,
  response_preview: 'pong',
  error: null,
};

interface SetupOptions {
  readonly getSettings?: () => Observable<LLMSettings>;
  readonly updateSettings?: () => Observable<LLMSettings>;
  readonly testSettings?: () => Observable<LLMTestResult>;
  readonly listFeatures?: () => Observable<FeatureView[]>;
  readonly upsertOverride?: () => Observable<FeatureView>;
  readonly clearOverride?: () => Observable<FeatureView>;
  readonly testOverride?: () => Observable<LLMTestResult>;
}

function setup(over: SetupOptions = {}) {
  const getSettings = vi.fn(over.getSettings ?? ((): Observable<LLMSettings> => of(SETTINGS)));
  const updateSettings = vi.fn(
    over.updateSettings ?? ((): Observable<LLMSettings> => of(SETTINGS)),
  );
  const testSettings = vi.fn(over.testSettings ?? ((): Observable<LLMTestResult> => of(TEST_OK)));
  const listFeatures = vi.fn(
    over.listFeatures ??
      ((): Observable<FeatureView[]> => of([OVERRIDDEN_FEATURE, INHERITED_FEATURE])),
  );
  const upsertOverride = vi.fn(
    over.upsertOverride ?? ((): Observable<FeatureView> => of(OVERRIDDEN_FEATURE)),
  );
  const clearOverride = vi.fn(
    over.clearOverride ?? ((): Observable<FeatureView> => of(INHERITED_FEATURE)),
  );
  const testOverride = vi.fn(over.testOverride ?? ((): Observable<LLMTestResult> => of(TEST_OK)));

  TestBed.configureTestingModule({
    providers: [
      AdminLLMSettingsStore,
      {
        provide: AdminLLMSettingsService,
        useValue: {
          getSettings,
          updateSettings,
          testSettings,
          listFeatures,
          upsertOverride,
          clearOverride,
          testOverride,
        },
      },
    ],
  });

  return {
    store: TestBed.inject(AdminLLMSettingsStore),
    getSettings,
    updateSettings,
    testSettings,
    listFeatures,
    upsertOverride,
    clearOverride,
    testOverride,
  };
}

describe('AdminLLMSettingsStore loading', () => {
  afterEach(() => vi.restoreAllMocks());

  it('ignores a second init so the settings are not fetched twice', () => {
    const { store, getSettings } = setup();

    store.init();
    store.init();

    expect(getSettings).toHaveBeenCalledTimes(1);
  });

  it('keeps the loaded global config visible when the feature list fails', () => {
    const { store } = setup({
      listFeatures: () => throwError(() => ({ error: { detail: 'features down' } })),
    });

    store.init();

    expect(store.current()).toEqual(SETTINGS);
    expect(store.formModel()).toBe('gpt-4o-mini');
    expect(store.error()).toBe('features down');
    expect(store.loading()).toBe(false);
  });

  it('clears a previous error when the screen is refreshed', () => {
    const { store, getSettings } = setup({
      getSettings: () => throwError(() => ({ error: { detail: 'boom' } })),
    });
    store.init();
    expect(store.error()).toBe('boom');

    getSettings.mockImplementation(() => of(SETTINGS));
    store.refresh();

    expect(store.error()).toBe('');
    expect(store.current()).toEqual(SETTINGS);
  });

  it('offers the model suggestions of the selected provider', () => {
    const { store } = setup();
    store.init();

    expect(store.modelSuggestions()).toContain('gpt-4o-mini');

    store.onProviderChange('groq');

    expect(store.modelSuggestions()).toContain('llama-3.3-70b-versatile');
  });
});

describe('AdminLLMSettingsStore test-before-save handshake', () => {
  afterEach(() => vi.restoreAllMocks());

  it('sends a null api key when the field is left blank and trims a filled one', () => {
    const { store, testSettings } = setup();
    store.init();

    store.onApiKeyChange('   ');
    store.test();

    expect(testSettings).toHaveBeenCalledWith({
      provider: 'openai',
      model: 'gpt-4o-mini',
      api_key: null,
      extra_params: { temperature: 0.2 },
    });

    store.onApiKeyChange('  sk-live  ');
    store.test();

    expect(testSettings).toHaveBeenLastCalledWith(expect.objectContaining({ api_key: 'sk-live' }));
  });

  it('coerces the extra params it sends and drops rows without a key', () => {
    const { store, testSettings } = setup();
    store.init();

    store.formExtras.set([
      { key: '  temperature  ', value: '0.7' },
      { key: 'stream', value: 'false' },
      { key: 'label', value: 'fast' },
      { key: 'budget', value: '1e5' },
      { key: 'blank', value: '' },
      { key: '   ', value: 'ignored' },
    ]);
    store.test();

    expect(testSettings).toHaveBeenCalledWith(
      expect.objectContaining({
        extra_params: {
          temperature: 0.7,
          stream: false,
          label: 'fast',
          // Not matched by the numeric pattern, so it stays a string.
          budget: '1e5',
          blank: '',
        },
      }),
    );
  });

  it('leaves the save prompt armed when the test call fails', () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);
    const { store, updateSettings } = setup({
      testSettings: () => throwError(() => ({ error: { detail: 'bad key' } })),
    });
    store.init();

    store.test();

    expect(store.error()).toBe('bad key');
    expect(store.testing()).toBe(false);
    expect(store.testResult()).toBeNull();
    expect(store.hasTestedSinceEdit()).toBe(false);

    store.save();

    expect(confirmSpy).toHaveBeenCalled();
    expect(updateSettings).not.toHaveBeenCalled();
  });

  it('re-arms the prompt after any edit to the tested configuration', () => {
    const { store } = setup();
    store.init();

    store.test();
    expect(store.hasTestedSinceEdit()).toBe(true);

    store.onApiKeyChange('sk-live');
    expect(store.hasTestedSinceEdit()).toBe(false);

    store.test();
    store.setExtraValue(0, '0.9');
    expect(store.hasTestedSinceEdit()).toBe(false);

    store.test();
    store.onProviderChange('groq');
    expect(store.hasTestedSinceEdit()).toBe(false);
  });

  it('saves without prompting when the caller already opted out of the test', () => {
    const confirmSpy = vi.spyOn(window, 'confirm');
    const { store, updateSettings } = setup();
    store.init();

    store.save(true);

    expect(confirmSpy).not.toHaveBeenCalled();
    expect(updateSettings).toHaveBeenCalledWith(expect.objectContaining({ skip_test: true }));
  });

  it('drops the typed api key and re-arms the prompt after a successful save', () => {
    const { store, updateSettings, listFeatures } = setup();
    store.init();
    store.onApiKeyChange('sk-live');
    store.test();

    store.save();

    expect(updateSettings).toHaveBeenCalledWith(
      expect.objectContaining({ api_key: 'sk-live', skip_test: false }),
    );
    expect(store.successMessage()).toBe('Settings saved.');
    expect(store.saving()).toBe(false);
    // The key is never kept around after it has been stored server-side.
    expect(store.formApiKey()).toBe('');
    expect(store.hasTestedSinceEdit()).toBe(false);
    expect(listFeatures).toHaveBeenCalledTimes(2);
  });

  it('keeps the form intact when the save is rejected', () => {
    const { store } = setup({
      updateSettings: () => throwError(() => ({ error: { detail: 'rejected' } })),
    });
    store.init();
    store.onApiKeyChange('sk-live');
    store.test();

    store.save();

    expect(store.error()).toBe('rejected');
    expect(store.saving()).toBe(false);
    expect(store.formApiKey()).toBe('sk-live');
    expect(store.successMessage()).toBe('');
  });
});

describe('AdminLLMSettingsStore extra param rows', () => {
  it('appends, edits and removes rows by index', () => {
    const { store } = setup();
    store.init();
    expect(store.formExtras()).toEqual([{ key: 'temperature', value: '0.2' }]);

    store.addExtra();
    store.setExtraKey(1, 'top_p');
    store.setExtraValue(1, '0.9');

    expect(store.formExtras()).toEqual([
      { key: 'temperature', value: '0.2' },
      { key: 'top_p', value: '0.9' },
    ]);

    store.removeExtra(0);

    expect(store.formExtras()).toEqual([{ key: 'top_p', value: '0.9' }]);
  });
});

describe('AdminLLMSettingsStore feature overrides', () => {
  afterEach(() => vi.restoreAllMocks());

  it('discards the previous draft feedback when a different feature is opened', () => {
    const { store } = setup();
    store.init();

    store.startEdit(OVERRIDDEN_FEATURE);
    store.testOverride();
    expect(store.overrideTestResult()).toEqual(TEST_OK);

    store.startEdit(INHERITED_FEATURE);

    expect(store.overrideTestResult()).toBeNull();
    expect(store.overrideError()).toBe('');
    expect(store.editingOverride()?.feature_key).toBe('cv.generate');
  });

  it('closes the draft without saving on cancel', () => {
    const { store, upsertOverride } = setup();
    store.init();

    store.startEdit(OVERRIDDEN_FEATURE);
    store.cancelEdit();

    expect(store.editingOverride()).toBeNull();
    expect(store.overrideTestResult()).toBeNull();
    expect(store.overrideError()).toBe('');
    expect(upsertOverride).not.toHaveBeenCalled();
  });

  it('blanks a field that is switched back to inheriting so no stale value is sent', () => {
    const { store, upsertOverride } = setup();
    store.init();

    store.startEdit(OVERRIDDEN_FEATURE);
    store.setOverrideInheritProvider(true);
    store.setOverrideInheritModel(true);

    expect(store.editingOverride()?.provider).toBe('');
    expect(store.editingOverride()?.model).toBe('');

    store.saveOverride();

    expect(upsertOverride).toHaveBeenCalledWith('matching.score', {
      provider: null,
      model: null,
      extra_params: { temperature: 0.1 },
      skip_test: false,
    });
  });

  it('sends the edited override extras with the same coercion as the global form', () => {
    const { store, upsertOverride } = setup();
    store.init();

    store.startEdit(INHERITED_FEATURE);
    store.setOverrideInheritProvider(false);
    store.setOverrideProvider('groq');
    store.setOverrideModel('llama-3.1-8b-instant');
    store.addOverrideExtra();
    store.setOverrideExtraKey(0, 'temperature');
    store.setOverrideExtraValue(0, '0.4');
    store.addOverrideExtra();
    store.removeOverrideExtra(1);
    store.saveOverride();

    expect(upsertOverride).toHaveBeenCalledWith('cv.generate', {
      provider: 'groq',
      // Still inheriting the model, so the override sends null rather than the
      // inherited value it was seeded from.
      model: null,
      extra_params: { temperature: 0.4 },
      skip_test: false,
    });
    expect(store.editingOverride()).toBeNull();
  });

  it('reports a failed override test and does not let the save skip validation', () => {
    const { store, upsertOverride } = setup({
      testOverride: () => throwError(() => ({ error: { detail: 'override unreachable' } })),
    });
    store.init();

    store.startEdit(OVERRIDDEN_FEATURE);
    store.testOverride();

    expect(store.overrideError()).toBe('override unreachable');
    expect(store.overrideTesting()).toBe(false);
    expect(store.overrideTestResult()).toBeNull();

    store.saveOverride();

    expect(upsertOverride).toHaveBeenCalledWith(
      'matching.score',
      expect.objectContaining({ skip_test: false }),
    );
  });

  it('does nothing when there is no draft open', () => {
    const { store, testOverride, upsertOverride } = setup();
    store.init();

    store.testOverride();
    store.saveOverride();

    expect(testOverride).not.toHaveBeenCalled();
    expect(upsertOverride).not.toHaveBeenCalled();
  });

  it('reloads the feature list after an override is cleared', () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    const { store, clearOverride, listFeatures } = setup();
    store.init();

    store.resetOverride(OVERRIDDEN_FEATURE);

    expect(clearOverride).toHaveBeenCalledWith('matching.score');
    expect(listFeatures).toHaveBeenCalledTimes(2);
  });

  it('reports a failed reset without reloading the feature list', () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    const { store, listFeatures } = setup({
      clearOverride: () => throwError(() => ({ error: { detail: 'reset failed' } })),
    });
    store.init();

    store.resetOverride(OVERRIDDEN_FEATURE);

    expect(store.overrideError()).toBe('reset failed');
    expect(listFeatures).toHaveBeenCalledTimes(1);
  });
});
