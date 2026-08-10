export interface TargetSalary {
  insufficient_data: boolean;
  currency: string | null;
  p25_annual: number | null;
  median_annual: number | null;
  p75_annual: number | null;
  sample_size: number;
}
