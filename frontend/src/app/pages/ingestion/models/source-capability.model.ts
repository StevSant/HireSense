export type SourceType = 'api' | 'rss' | 'scraper' | 'manual';
export type ClosureStrategy = 'snapshot' | 'url_probe' | 'expiry' | 'none';
export type IntegrationMethod =
  | 'official_api'
  | 'official_rss'
  | 'public_structured'
  | 'public_html'
  | 'import_fallback'
  | 'manual';

export interface SourceCapabilities {
  source: string;
  display_name: string;
  source_type: SourceType;
  integration: IntegrationMethod;
  enabled_by_default: boolean;
  requires_credentials: boolean;
  supports_keyword_search: boolean;
  supports_location_search: boolean;
  supports_remote_filter: boolean;
  supports_pagination: boolean;
  provides_salary: boolean;
  provides_equity: boolean;
  provides_company_metadata: boolean;
  provides_technology_tags: boolean;
  snapshot_source: boolean;
  reliable_closure_detection: boolean;
  closure_strategy: ClosureStrategy;
  limitations: string;
}

export interface SourceInfo {
  capabilities: SourceCapabilities;
  enabled: boolean;
  wired: boolean;
}

export interface SourcesResponse {
  sources: SourceInfo[];
}

export type SourceHealthStatus =
  | 'healthy'
  | 'degraded'
  | 'failing'
  | 'disabled'
  | 'not_configured';

export interface SourceHealth {
  source: string;
  status: SourceHealthStatus;
  last_attempt_at: string | null;
  last_success_at: string | null;
  duration_ms: number | null;
  pages_fetched: number;
  jobs_discovered: number;
  jobs_created: number;
  jobs_updated: number;
  jobs_deduplicated: number;
  jobs_rejected_malformed: number;
  rate_limited_count: number;
  parse_failures: number;
  last_error: string | null;
}

export interface SourcesHealthResponse {
  sources: SourceHealth[];
}
