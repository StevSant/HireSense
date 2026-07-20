export interface CompanyResearch {
  id: string | null;
  company_name: string;
  funding_stage: string;
  tech_stack: string;
  culture_summary: string;
  growth_trajectory: string;
  red_flags: string | null;
  pros: string;
  cons: string;
  industry: string | null;
  company_size: string | null;
  headquarters: string | null;
  website: string | null;
  // Source-provided About text (from the job board's company profile). Present
  // independent of LLM availability; may be non-English.
  description: string | null;
  logo_url: string | null;
  created_at: string | null;
  updated_at: string | null;
}
