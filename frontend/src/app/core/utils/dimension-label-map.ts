// Human-readable labels for the LLM match-score dimensions. Keys mirror the
// backend dimension keys (matching/domain scorers); any dimension not listed
// here falls back to a de-underscored title in dimensionLabel().
export const DIMENSION_LABELS: Readonly<Record<string, string>> = {
  seniority_fit: 'Seniority Fit',
  compensation: 'Compensation',
  growth_potential: 'Growth Potential',
  culture_fit: 'Culture Fit',
  application_strength: 'Application Strength',
  interview_readiness: 'Interview Readiness',
};
