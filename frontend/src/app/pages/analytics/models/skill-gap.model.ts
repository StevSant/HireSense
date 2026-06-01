export interface SkillGapItem {
  skill: string;
  count: number;
  pct: number;
}

export interface SkillGap {
  has_profile: boolean;
  missing: SkillGapItem[];
}
