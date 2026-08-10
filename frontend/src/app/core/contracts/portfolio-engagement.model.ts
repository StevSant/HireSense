export interface PortfolioVisit {
  ref: string;
  application_id: string | null;
  first_seen: string;
  last_seen: string;
  page_views: number;
  cv_downloads: number;
  country: string | null;
  organization: string | null;
}

export interface PortfolioEngagementResponse {
  configured: boolean;
  visits: PortfolioVisit[];
}
