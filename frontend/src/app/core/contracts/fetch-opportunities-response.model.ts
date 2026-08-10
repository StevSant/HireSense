export interface FetchOpportunitiesResponse {
  sources: Record<string, unknown>;
  inserted: number;
  updated: number;
  reopened: number;
  unchanged: number;
  errors: Record<string, unknown>[];
}
