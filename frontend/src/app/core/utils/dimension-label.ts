import { DIMENSION_LABELS } from './dimension-label-map';

// Maps a match-score dimension key to its display label, falling back to a
// de-underscored form for any dimension not in the canonical map.
export function dimensionLabel(dimension: string): string {
  return DIMENSION_LABELS[dimension] ?? dimension.replace(/_/g, ' ');
}
