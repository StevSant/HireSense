export interface FetchOpportunitiesResponse {
  sources: Record<string, unknown>;
  inserted: number;
  updated: number;
  reopened: number;
  unchanged: number;
  errors: Array<Record<string, unknown>>;
}
