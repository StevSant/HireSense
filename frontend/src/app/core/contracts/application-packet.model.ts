export type ApplicationPacketState = 'draft' | 'approved' | 'revoked';

export interface ApplicationQualityReport {
  ready: boolean;
  checks: Record<string, boolean>;
  warnings: string[];
  skill_coverage_ratio: number;
  checked_at: string | null;
}

export interface ApplicationPacket {
  id: string;
  application_id: string;
  job_snapshot_hash: string;
  profile_hash: string;
  match_id: string | null;
  optimization_id: string | null;
  cover_letter_id: string | null;
  verified_claim_ids: string[];
  cv_content_hash: string | null;
  cover_letter_content_hash: string | null;
  quality_report: ApplicationQualityReport;
  state: ApplicationPacketState;
  approved_at: string | null;
  revoked_at: string | null;
  created_at: string | null;
}
