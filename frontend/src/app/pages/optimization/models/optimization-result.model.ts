import { SectionChange } from './section-change.model';

export interface OptimizationResult {
  id: string;
  match_id: string;
  changes: SectionChange[];
  original_tex: string;
  optimized_tex: string;
  improvement_summary: string | null;
}
