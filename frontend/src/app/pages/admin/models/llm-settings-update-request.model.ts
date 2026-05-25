export interface LLMSettingsUpdateRequest {
  provider: string;
  model: string;
  /** Omit / null to leave the stored key unchanged. */
  api_key?: string | null;
  extra_params: Record<string, unknown>;
  skip_test?: boolean;
}
