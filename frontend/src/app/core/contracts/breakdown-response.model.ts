import { UsageBucket } from '@core/contracts/usage-bucket.model';

export interface BreakdownResponse {
  dimension: 'provider' | 'model' | 'feature';
  days: number | null;
  buckets: UsageBucket[];
}
