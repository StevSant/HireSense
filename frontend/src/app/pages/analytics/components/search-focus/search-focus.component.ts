import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { SearchFocus } from '../../models/search-focus.model';

const PERCENT = 100;

@Component({
  selector: 'app-search-focus',
  standalone: true,
  imports: [RouterLink],
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

  topRole = computed(() => this.focus().best_fit_roles[0] ?? null);
  topCompany = computed(() => this.focus().best_fit_companies[0] ?? null);
}
