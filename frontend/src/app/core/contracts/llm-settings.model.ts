export interface LLMSettings {
  provider: string;
  model: string;
  api_key_mask: string;
  has_stored_key: boolean;
  extra_params: Record<string, unknown>;
  updated_by: string | null;
  updated_at: string | null;
  source: string;
}
