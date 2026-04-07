import { BatchResult } from './batch-result.model';

export interface BatchEvaluationResponse {
  total_jobs: number;
  results: BatchResult[];
}
