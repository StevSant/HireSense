export type OpportunityKind =
  'conference' | 'cfp' | 'grant' | 'fellowship' | 'summer_school' | 'event';

export interface Opportunity {
  id: string;
  kind: OpportunityKind;
  title: string;
  organization: string;
  url: string;
  apply_url?: string | null;
  description: string;
  topics: string[];
  country?: string | null;
  city?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  cfp_deadline?: string | null;
  application_deadline?: string | null;
  funding?: string | null;
  source: string;
  source_id: string;
  status: string;
  source_metadata: Record<string, unknown>;
  relevance_score?: number | null;
}
