import { describe, it, expect } from 'vitest';
import { toPeriod, periodUnit } from './pay-period';

describe('pay-period', () => {
  it('returns the annual value unchanged for annual', () => {
    expect(toPeriod(31200, 'annual')).toBe(31200);
  });

  it('divides by 12 (rounded) for monthly', () => {
    expect(toPeriod(31200, 'monthly')).toBe(2600);
  });

  it('passes null through', () => {
    expect(toPeriod(null, 'monthly')).toBeNull();
  });

  it('labels the unit', () => {
    expect(periodUnit('annual')).toBe('/year');
    expect(periodUnit('monthly')).toBe('/mo');
  });
});
