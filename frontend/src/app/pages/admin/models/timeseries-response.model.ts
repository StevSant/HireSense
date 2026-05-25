import { UsageBucket } from './usage-bucket.model';

export interface TimeseriesResponse {
  days: number;
  buckets: UsageBucket[];
}
