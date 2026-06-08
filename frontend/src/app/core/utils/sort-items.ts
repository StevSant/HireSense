import { SortDirection } from './sort-state';

type Comparable = string | number | Date | null | undefined;

function isMissing(v: Comparable): boolean {
  return v === null || v === undefined || v === '';
}

function normalize(v: Comparable): string | number {
  if (v instanceof Date) return v.getTime();
  if (typeof v === 'string') return v.toLowerCase();
  return v as number;
}

// Pure comparator for fully-loaded client-side lists. Null/empty values sort
// to the bottom regardless of direction; strings compare case-insensitively.
export function sortItems<T>(
  items: readonly T[],
  accessor: (item: T) => Comparable,
  dir: SortDirection,
): T[] {
  const present: T[] = [];
  const missing: T[] = [];
  for (const item of items) {
    (isMissing(accessor(item)) ? missing : present).push(item);
  }
  const factor = dir === 'asc' ? 1 : -1;
  present.sort((a, b) => {
    const av = normalize(accessor(a));
    const bv = normalize(accessor(b));
    if (av < bv) return -1 * factor;
    if (av > bv) return 1 * factor;
    return 0;
  });
  return [...present, ...missing];
}
