// Formats a 0-1 score as a whole-number percentage. Null renders as an em dash.
// Pass withSign=false to omit the '%' (for templates that append it themselves).
export function formatScorePercent(score: number | null, withSign = true): string {
  if (score === null) return '—';
  const pct = (score * 100).toFixed(0);
  return withSign ? `${pct}%` : pct;
}
