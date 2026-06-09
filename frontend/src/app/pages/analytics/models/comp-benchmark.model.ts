export interface SeniorityBand {
  level: string;
  median_annual: number;
  sample_size: number;
}

export interface CompBenchmark {
  insufficient_data: boolean;
  currency: string | null;
  p25_annual: number | null;
  median_annual: number | null;
  p75_annual: number | null;
  sample_size: number;
  by_seniority: SeniorityBand[];
  your_median_annual: number | null;
  your_sample_size: number;
  ask_min_annual: number | null;
  ask_max_annual: number | null;
}
