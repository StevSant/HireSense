// One scored dimension of a deep match analysis. Distinct from the matching
// page's DimensionResult (which carries a weight) — the deep analyzer reports
// equal-weight, labelled dimensions for display only.
export interface AnalysisDimension {
  dimension: string;
  score: number;
  rationale: string;
}
