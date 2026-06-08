import { SortDirection } from './sort-state';

// Parses a `<field>_<dir>` sort token (e.g. from a sort <select>) into its
// parts, or null when malformed. Splits on the LAST underscore so multi-word
// fields like "total_tokens" survive. Direction must be asc|desc.
export function parseSortToken<F extends string>(
  token: string,
): { field: F; dir: SortDirection } | null {
  const i = token.lastIndexOf('_');
  if (i <= 0) return null;
  const field = token.slice(0, i);
  const dir = token.slice(i + 1);
  if (dir !== 'asc' && dir !== 'desc') return null;
  return { field: field as F, dir };
}
