import { BatchResult } from '@core/contracts/batch-result.model';

export interface BatchEvaluationResponse {
  total_jobs: number;
  results: BatchResult[];
}
