import { UsageTotals } from '@core/contracts/usage-totals.model';

export interface DashboardSummary {
  today: UsageTotals;
  this_month: UsageTotals;
  all_time: UsageTotals;
}
