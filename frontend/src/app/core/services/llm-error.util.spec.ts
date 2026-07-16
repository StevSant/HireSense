import { HttpErrorResponse } from '@angular/common/http';
import { describe, expect, it } from 'vitest';
import { mapLlmError } from './llm-error.util';

function makeError(status: number, detail?: string): HttpErrorResponse {
  return new HttpErrorResponse({
    status,
    error: detail !== undefined ? { detail } : null,
  });
}

describe('mapLlmError', () => {
  it('maps 503 to a not-configured message pointing at Admin → LLM settings', () => {
    expect(mapLlmError(makeError(503), 'fallback')).toBe(
      "LLM isn't configured — add a key in Admin → LLM settings.",
    );
  });

  it('maps 408 (timeout interceptor) to a busy-model message', () => {
    expect(mapLlmError(makeError(408), 'fallback')).toBe(
      'The request timed out — the model may be busy. Try again.',
    );
  });

  it('uses the server detail message for any other status', () => {
    expect(mapLlmError(makeError(400, 'Missing job description'), 'fallback')).toBe(
      'Missing job description',
    );
  });

  it('falls back to the caller-supplied message when there is no detail', () => {
    expect(mapLlmError(makeError(500), 'Analysis failed')).toBe('Analysis failed');
  });

  it('falls back to the caller-supplied message when the error body is null', () => {
    const err = new HttpErrorResponse({ status: 0 });
    expect(mapLlmError(err, 'Network error')).toBe('Network error');
  });
});
