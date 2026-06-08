import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';
import { SortState } from '../../utils/sort-state';

@Component({
  selector: 'th[appSortHeader]',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <button type="button" class="sort-header" (click)="onClick()">
      <ng-content />
      <span class="sort-arrow" aria-hidden="true">{{ arrow() }}</span>
    </button>
  `,
  styles: [`
    .sort-header {
      display: inline-flex; align-items: center; gap: 0.25rem;
      background: none; border: none; padding: 0; cursor: pointer;
      font: inherit; color: inherit;
    }
    .sort-arrow { font-size: 0.7em; opacity: 0.8; min-width: 0.7em; }
  `],
  host: { '[attr.aria-sort]': 'ariaSort()' },
})
export class SortableHeaderComponent {
  // The field key this header sorts by, and the shared sort state instance.
  readonly field = input.required<string>();
  readonly state = input.required<SortState<string>>();
  // Fired after the sort state is toggled, so the host can react (reload/reset).
  readonly sorted = output<void>();

  protected readonly active = computed(() => this.state().isActive(this.field()));
  protected readonly arrow = computed(() =>
    this.active() ? (this.state().dir() === 'asc' ? '▲' : '▼') : '',
  );
  protected readonly ariaSort = computed(() =>
    this.active() ? (this.state().dir() === 'asc' ? 'ascending' : 'descending') : 'none',
  );

  protected onClick(): void {
    this.state().toggle(this.field());
    this.sorted.emit();
  }
}
