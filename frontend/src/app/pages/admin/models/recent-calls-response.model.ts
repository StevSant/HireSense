import { UsageCall } from './usage-call.model';

export interface RecentCallsResponse {
  calls: UsageCall[];
  limit: number;
  offset: number;
  /** Rows matching the active filters, ignoring limit/offset. */
  total: number;
}
