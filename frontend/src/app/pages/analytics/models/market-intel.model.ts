export interface SkillCount {
  skill: string;
  count: number;
  pct: number;
}

export interface TrendPoint {
  week: string;
  count: number;
}

export interface SalaryDistribution {
  currency: string | null;
  min_annual: number | null;
  median_annual: number | null;
  max_annual: number | null;
  parsed_count: number;
  unparsed_count: number;
  other_currency_count: number;
  disclosed_pct: number;
}

export interface MarketIntel {
  top_skills: SkillCount[];
  remote_mix: Record<string, number>;
  posting_trend: TrendPoint[];
  salary_distribution: SalaryDistribution;
}
