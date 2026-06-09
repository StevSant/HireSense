export interface FocusItem {
  label: string;
  count: number;
  avg_score: number;
}

export interface SearchFocus {
  insufficient_data: boolean;
  match_count: number;
  best_fit_companies: FocusItem[];
  best_fit_roles: FocusItem[];
  remote_share: number | null;
  top_locations: FocusItem[];
  fresh_fit_count: number;
  fresh_days: number;
}
