export interface UsageCall {
  id: string;
  created_at: string;
  feature_key: string;
  provider: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cost_usd: number;
  latency_ms: number;
  success: boolean;
  error: string | null;
}
