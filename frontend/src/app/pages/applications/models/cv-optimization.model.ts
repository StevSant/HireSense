export type ClaimBlockerReason =
  'missing_exact_anchor' | 'unsupported_job_skill' | 'unsupported_numeric_claim';

export interface ClaimReadiness {
  ready: boolean;
  supported_changes: CvOptimizationChange[];
  blocked_changes: { change: CvOptimizationChange; reason: ClaimBlockerReason }[];
}

export interface CvOptimizationChange {
  section_name?: string;
  section?: string;
  original?: string;
  optimized?: string;
  reason?: string;
  before?: string;
  after?: string;
}

export interface CvOptimization {
  id: string;
  match_id: string | null;
  cv_language: string;
  original_tex: string;
  optimized_tex: string;
  improvement_summary: string;
  changes: CvOptimizationChange[];
  claim_readiness?: ClaimReadiness | null;
  created_at: string | null;
}
