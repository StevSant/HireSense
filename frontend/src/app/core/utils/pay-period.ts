export type PayPeriod = 'annual' | 'monthly';

const MONTHS_PER_YEAR = 12;

/** Convert an annual figure to the chosen display period. Display-only. */
export function toPeriod(annual: number | null, period: PayPeriod): number | null {
  if (annual === null) return null;
  return period === 'monthly' ? Math.round(annual / MONTHS_PER_YEAR) : annual;
}

export function periodUnit(period: PayPeriod): string {
  return period === 'monthly' ? '/mo' : '/year';
}
