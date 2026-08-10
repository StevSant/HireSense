export interface PortfolioSyncResult {
  counts_by_source: Record<string, number>;
  errors: Record<string, string>;
  synced_at: string;
}
