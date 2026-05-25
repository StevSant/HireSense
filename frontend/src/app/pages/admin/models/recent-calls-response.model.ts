import { UsageCall } from './usage-call.model';

export interface RecentCallsResponse {
  calls: UsageCall[];
  limit: number;
  offset: number;
}
