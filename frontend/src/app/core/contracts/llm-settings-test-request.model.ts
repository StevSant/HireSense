export interface LLMSettingsTestRequest {
  provider: string;
  model: string;
  api_key?: string | null;
  extra_params: Record<string, unknown>;
}
