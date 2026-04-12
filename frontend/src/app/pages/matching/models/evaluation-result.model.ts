import { DimensionResult } from '../../../core/models/dimension-result.model';

export interface EvaluationResult {
  composite_score: number;
  job_title: string;
  company: string;
  dimensions: DimensionResult[];
}
