export interface UpskillingStep {
  skill: string;
  demand_count: number;
  demand_pct: number;
  next_action: string;
}

export interface UpskillingPlan {
  has_profile: boolean;
  steps: UpskillingStep[];
}
