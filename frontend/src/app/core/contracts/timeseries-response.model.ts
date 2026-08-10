import { UsageBucket } from '@core/contracts/usage-bucket.model';

export interface TimeseriesResponse {
  days: number;
  buckets: UsageBucket[];
}
