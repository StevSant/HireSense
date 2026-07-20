import { HttpErrorResponse } from '@angular/common/http';

/**
 * Central message mapping for failed LLM-backed requests. 503 means the
 * backend has no LLM key configured; 408 is the synthetic status the
 * timeout interceptor emits when the model takes too long. Anything else
 * falls back to the server's `detail` message, or the caller-supplied
 * fallback if the response carries none.
 */
export function mapLlmError(err: HttpErrorResponse, fallback: string): string {
  if (err.status === 503) {
    return "LLM isn't configured — add a key in Admin → LLM settings.";
  }
  if (err.status === 408) {
    return 'The request timed out — the model may be busy. Try again.';
  }
  return err.error?.detail || fallback;
}
