import { TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';

import { AdminLLMSettingsComponent } from './admin-llm-settings.component';
import { AdminLLMSettingsService } from '../../core/services/admin-llm-settings.service';
import { FeatureView } from './models/feature-view.model';
import { LLMSettings } from './models/llm-settings.model';
import { LLMTestResult } from './models/llm-test-result.model';

const SETTINGS: LLMSettings = {
  provider: 'openai',
  model: 'gpt-4o-mini',
  api_key_mask: 'sk-***abcd',
  has_stored_key: true,
  extra_params: { temperature: 0.2, stream: true },
  updated_by: 'admin',
  updated_at: '2026-06-01T00:00:00Z',
  source: 'database',
};

const FEATURES: FeatureView[] = [
  {
    feature_key: 'matching.score',
    feature_name: 'Matching Score',
    feature_description: 'Scores jobs against the profile.',
    provider: 'anthropic',
    model: 'claude-opus-4-7',
    inherits_provider: false,
    inherits_model: false,
    extra_params: { temperature: 0.1 },
    source: 'override',
  },
  {
    feature_key: 'cv.generate',
    feature_name: 'CV Generation',
    feature_description: 'Generates tailored CVs.',
    provider: 'openai',
    model: 'gpt-4o-mini',
    inherits_provider: true,
    inherits_model: true,
    extra_params: {},
    source: 'inherited',
  },
];

const TEST_OK: LLMTestResult = {
  success: true,
  latency_ms: 120,
  response_preview: 'pong',
  error: null,
};

describe('AdminLLMSettingsComponent', () => {
  let getSettings: ReturnType<typeof vi.fn>;
  let updateSettings: ReturnType<typeof vi.fn>;
  let testSettings: ReturnType<typeof vi.fn>;
  let listFeatures: ReturnType<typeof vi.fn>;
  let upsertOverride: ReturnType<typeof vi.fn>;
  let clearOverride: ReturnType<typeof vi.fn>;
  let testOverride: ReturnType<typeof vi.fn>;

  beforeEach(async () => {
    getSettings = vi.fn().mockReturnValue(of(SETTINGS));
    updateSettings = vi.fn().mockReturnValue(of(SETTINGS));
    testSettings = vi.fn().mockReturnValue(of(TEST_OK));
    listFeatures = vi.fn().mockReturnValue(of(FEATURES));
    upsertOverride = vi.fn().mockReturnValue(of(FEATURES[0]));
    clearOverride = vi.fn().mockReturnValue(of(FEATURES[1]));
    testOverride = vi.fn().mockReturnValue(of(TEST_OK));

    await TestBed.configureTestingModule({
      imports: [AdminLLMSettingsComponent],
      providers: [
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
    }).compileComponents();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  function mount() {
    const fixture = TestBed.createComponent(AdminLLMSettingsComponent);
    fixture.detectChanges();
    return fixture;
  }

  describe('initial load', () => {
    it('populates the global form and features from the service', () => {
      const fixture = mount();
      const c = fixture.componentInstance;

      expect(getSettings).toHaveBeenCalled();
      expect(listFeatures).toHaveBeenCalled();
      expect(c.current()).toEqual(SETTINGS);
      expect(c.formProvider()).toBe('openai');
      expect(c.formModel()).toBe('gpt-4o-mini');
      // api key is never hydrated from the server
      expect(c.formApiKey()).toBe('');
      // extra_params are flattened to the editable key/value list
      expect(c.formExtras()).toEqual([
        { key: 'temperature', value: '0.2' },
        { key: 'stream', value: 'true' },
      ]);
      expect(c.features().length).toBe(2);
      expect(c.loading()).toBe(false);
      expect(c.error()).toBe('');
    });

    it('falls back to anthropic when the stored provider is unknown', () => {
      getSettings.mockReturnValue(of({ ...SETTINGS, provider: 'mystery' }));
      const fixture = mount();
      expect(fixture.componentInstance.formProvider()).toBe('anthropic');
    });

    it('renders model suggestions for the active provider', () => {
      const fixture = mount();
      // openai suggestions from the constants module
      expect(fixture.componentInstance.modelSuggestions()).toContain('gpt-4o-mini');
    });
  });

  describe('load error', () => {
    it('sets the error message and clears loading when getSettings fails', () => {
      getSettings.mockReturnValue(
        throwError(() => ({ error: { detail: 'boom' } })),
      );
      const fixture = mount();
      const c = fixture.componentInstance;
      expect(c.error()).toBe('boom');
      expect(c.loading()).toBe(false);
      // features load is never attempted on a settings failure
      expect(listFeatures).not.toHaveBeenCalled();
    });

    it('uses a default message when listFeatures fails without a detail', () => {
      listFeatures.mockReturnValue(throwError(() => new Error('nope')));
      const fixture = mount();
      expect(fixture.componentInstance.error()).toBe('Failed to load features');
      expect(fixture.componentInstance.loading()).toBe(false);
    });
  });

  describe('global save flow', () => {
    it('prompts before saving when no test was run since the last edit', () => {
      const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);
      const fixture = mount();
      const c = fixture.componentInstance;

      c.onModelChange('gpt-4o'); // invalidates hasTestedSinceEdit
      c.save();

      expect(confirmSpy).toHaveBeenCalled();
      expect(updateSettings).not.toHaveBeenCalled();
    });

    it('saves with skip_test when the user confirms the un-tested save', () => {
      vi.spyOn(window, 'confirm').mockReturnValue(true);
      const fixture = mount();
      const c = fixture.componentInstance;

      c.onModelChange('gpt-4o');
      c.save();

      expect(updateSettings).toHaveBeenCalledTimes(1);
      const body = updateSettings.mock.calls[0][0];
      expect(body.skip_test).toBe(true);
      expect(body.model).toBe('gpt-4o');
      expect(c.successMessage()).toBe('Settings saved.');
      expect(c.saving()).toBe(false);
      // features are reloaded after a successful save
      expect(listFeatures).toHaveBeenCalledTimes(2);
    });

    it('saves without prompting after a successful test call', () => {
      const confirmSpy = vi.spyOn(window, 'confirm');
      const fixture = mount();
      const c = fixture.componentInstance;

      c.test();
      expect(testSettings).toHaveBeenCalled();
      expect(c.hasTestedSinceEdit()).toBe(true);
      expect(c.testResult()).toEqual(TEST_OK);

      c.save();
      expect(confirmSpy).not.toHaveBeenCalled();
      expect(updateSettings).toHaveBeenCalledTimes(1);
      expect(updateSettings.mock.calls[0][0].skip_test).toBe(false);
    });

    it('serializes extra params with type coercion in the save body', () => {
      vi.spyOn(window, 'confirm').mockReturnValue(true);
      const fixture = mount();
      const c = fixture.componentInstance;

      c.formExtras.set([
        { key: 'temperature', value: '0.7' },
        { key: 'stream', value: 'false' },
        { key: 'label', value: 'fast' },
        { key: '', value: 'ignored' },
      ]);
      c.save();

      const body = updateSettings.mock.calls[0][0];
      expect(body.extra_params).toEqual({
        temperature: 0.7,
        stream: false,
        label: 'fast',
      });
    });

    it('reports a save error from the service detail', () => {
      vi.spyOn(window, 'confirm').mockReturnValue(true);
      updateSettings.mockReturnValue(
        throwError(() => ({ error: { detail: 'rejected' } })),
      );
      const fixture = mount();
      const c = fixture.componentInstance;
      c.onModelChange('gpt-4o');
      c.save();
      expect(c.error()).toBe('rejected');
      expect(c.saving()).toBe(false);
    });
  });

  describe('override editing + save', () => {
    it('startEdit seeds the draft from the feature view', () => {
      const fixture = mount();
      const c = fixture.componentInstance;

      c.startEdit(FEATURES[0]);
      const draft = c.editingOverride();
      expect(draft?.feature_key).toBe('matching.score');
      expect(draft?.provider).toBe('anthropic');
      expect(draft?.model).toBe('claude-opus-4-7');
      expect(draft?.inherit_provider).toBe(false);
      expect(draft?.extra).toEqual([{ key: 'temperature', value: '0.1' }]);
    });

    it('startEdit blanks provider/model when the feature inherits them', () => {
      const fixture = mount();
      const c = fixture.componentInstance;
      c.startEdit(FEATURES[1]);
      const draft = c.editingOverride();
      expect(draft?.inherit_provider).toBe(true);
      expect(draft?.provider).toBe('');
      expect(draft?.model).toBe('');
    });

    it('saveOverride sends nulls for inherited fields and reloads features', () => {
      const fixture = mount();
      const c = fixture.componentInstance;

      c.startEdit(FEATURES[1]); // both inherited
      c.setOverrideInheritProvider(false);
      c.setOverrideProvider('groq');
      c.setOverrideModel('llama-3.1-8b-instant');
      c.saveOverride();

      expect(upsertOverride).toHaveBeenCalledTimes(1);
      const [key, body] = upsertOverride.mock.calls[0];
      expect(key).toBe('cv.generate');
      expect(body.provider).toBe('groq');
      // model is still inherited → null
      expect(body.model).toBeNull();
      // no successful override test → skip_test stays false
      expect(body.skip_test).toBe(false);
      expect(c.editingOverride()).toBeNull();
      expect(listFeatures).toHaveBeenCalledTimes(2);
    });

    it('skips the override test on save after a successful override test', () => {
      const fixture = mount();
      const c = fixture.componentInstance;

      c.startEdit(FEATURES[0]);
      c.testOverride();
      expect(testOverride).toHaveBeenCalled();
      expect(c.overrideTestResult()).toEqual(TEST_OK);

      c.saveOverride();
      expect(upsertOverride.mock.calls[0][1].skip_test).toBe(true);
    });

    it('surfaces an override save error and keeps the draft open', () => {
      upsertOverride.mockReturnValue(
        throwError(() => ({ error: { detail: 'bad override' } })),
      );
      const fixture = mount();
      const c = fixture.componentInstance;

      c.startEdit(FEATURES[0]);
      c.saveOverride();

      expect(c.overrideError()).toBe('bad override');
      expect(c.editingOverride()).not.toBeNull();
    });

    it('resetOverride clears an override after confirmation', () => {
      vi.spyOn(window, 'confirm').mockReturnValue(true);
      const fixture = mount();
      const c = fixture.componentInstance;

      c.resetOverride(FEATURES[0]);
      expect(clearOverride).toHaveBeenCalledWith('matching.score');
      expect(listFeatures).toHaveBeenCalledTimes(2);
    });

    it('resetOverride does nothing when cancelled', () => {
      vi.spyOn(window, 'confirm').mockReturnValue(false);
      const fixture = mount();
      fixture.componentInstance.resetOverride(FEATURES[0]);
      expect(clearOverride).not.toHaveBeenCalled();
    });

    it('resetOverride ignores features that are merely inherited', () => {
      const confirmSpy = vi.spyOn(window, 'confirm');
      const fixture = mount();
      fixture.componentInstance.resetOverride(FEATURES[1]);
      expect(confirmSpy).not.toHaveBeenCalled();
      expect(clearOverride).not.toHaveBeenCalled();
    });
  });
});
