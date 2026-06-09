import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { SearchFocus } from '../../models/search-focus.model';

const PERCENT = 100;

@Component({
  selector: 'app-search-focus',
  standalone: true,
  templateUrl: './search-focus.component.html',
  styleUrl: './search-focus.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SearchFocusComponent {
  focus = input.required<SearchFocus>();

  remotePct = computed<number | null>(() => {
    const r = this.focus().remote_share;
    return r === null ? null : Math.round(r * PERCENT);
  });
}
