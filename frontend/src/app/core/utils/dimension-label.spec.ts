import { describe, expect, it } from 'vitest';
import { dimensionLabel } from './dimension-label';

describe('dimensionLabel', () => {
  it('returns the canonical label for a known dimension', () => {
    expect(dimensionLabel('seniority_fit')).toBe('Seniority Fit');
    expect(dimensionLabel('interview_readiness')).toBe('Interview Readiness');
  });

  it('leaves a single-word known dimension unchanged', () => {
    expect(dimensionLabel('compensation')).toBe('Compensation');
  });

  it('falls back to a de-underscored label for an unknown dimension', () => {
    expect(dimensionLabel('remote_flexibility')).toBe('remote flexibility');
  });
});
