import { computed, Directive, input, output } from '@angular/core';
import { SortState } from '../../utils/sort-state';

// Turns a <th> into a clickable, keyboard-operable sort control. The arrow
// indicator is rendered purely from `aria-sort` via global CSS (see
// styles.scss), so the ARIA state is the single source of truth.
@Directive({
  selector: 'th[appSortHeader]',
  standalone: true,
  host: {
    class: 'sortable-header',
    '[attr.aria-sort]': 'ariaSort()',
    '[attr.tabindex]': '0',
    '(click)': 'activate()',
    '(keydown.enter)': 'activate()',
    '(keydown.space)': 'onSpace($event)',
  },
})
export class SortableHeaderDirective {
  // The field key this header sorts by, and the shared sort state instance.
  readonly field = input.required<string>();
  readonly state = input.required<SortState<string>>();
  // Fired after the sort state changes, so the host can react (reload/reset).
  readonly sorted = output<void>();

  protected readonly active = computed(() => this.state().isActive(this.field()));
  protected readonly ariaSort = computed(() =>
    this.active() ? (this.state().dir() === 'asc' ? 'ascending' : 'descending') : 'none',
  );

  protected activate(): void {
    this.state().toggle(this.field());
    this.sorted.emit();
  }

  protected onSpace(event: Event): void {
    // Stop the page from scrolling when toggling via the space bar.
    event.preventDefault();
    this.activate();
  }
}
