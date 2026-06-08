import { computed, signal, Signal } from '@angular/core';

export type SortDirection = 'asc' | 'desc';

export interface SortState<F extends string> {
  field: Signal<F>;
  dir: Signal<SortDirection>;
  /** `${field}_${dir}` token shared with the backend sort contract. */
  token: Signal<string>;
  toggle(field: F): void;
  /** Set field + direction directly — for dropdown-driven (non-header) sorting. */
  set(field: F, dir: SortDirection): void;
  isActive(field: F): boolean;
}

// Clicking the active column flips direction; clicking a new column selects it
// with a sensible default — ascending for text columns, descending otherwise.
export function createSortState<F extends string>(
  initialField: F,
  initialDir: SortDirection,
  textFields: readonly F[] = [],
): SortState<F> {
  const field = signal<F>(initialField);
  const dir = signal<SortDirection>(initialDir);
  const textSet = new Set<F>(textFields);

  return {
    field,
    dir,
    token: computed(() => `${field()}_${dir()}`),
    toggle(next: F): void {
      if (field() === next) {
        dir.update((d) => (d === 'asc' ? 'desc' : 'asc'));
      } else {
        field.set(next);
        dir.set(textSet.has(next) ? 'asc' : 'desc');
      }
    },
    set(next: F, nextDir: SortDirection): void {
      field.set(next);
      dir.set(nextDir);
    },
    isActive(candidate: F): boolean {
      return field() === candidate;
    },
  };
}
