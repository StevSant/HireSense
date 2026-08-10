export interface LLMTestResult {
  success: boolean;
  latency_ms: number;
  response_preview: string;
  error: string | null;
}
