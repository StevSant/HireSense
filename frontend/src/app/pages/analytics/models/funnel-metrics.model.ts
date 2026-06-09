import { SourceOutcome } from './source-outcome.model';

export interface FunnelStage {
  stage: string;
  reached: number;
  conversion_from_prev: number | null;
  median_days_in_stage: number | null;
  current: number;
}

export interface FunnelMetrics {
  stages: FunnelStage[];
  rejected: number;
  current_rejected: number;
  total_applications: number;
  by_source: SourceOutcome[];
}
