import { DimensionResult } from './dimension-result.model';

export interface BatchResult {
  job_title: string;
  company: string;
  source: string;
  source_id: string;
  composite_score: number;
  dimensions: DimensionResult[];
}
