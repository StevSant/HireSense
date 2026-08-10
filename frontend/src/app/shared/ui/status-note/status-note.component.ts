import { ChangeDetectionStrategy, Component } from '@angular/core';

/**
 * The muted one-liner a section shows in place of its content — "Loading…",
 * "No opportunities match your current filters yet.", "Upload a CV to see your
 * skill gap."
 *
 * Loading and empty are the same treatment on purpose: both are a section
 * saying "nothing to render here yet", and every page that had both styled
 * them with one rule (`.section-loading, .section-empty`).
 *
 * Callers own the box, not the type: set `padding`/`margin` on the
 * `app-status-note` element from the parent stylesheet. That is why the type
 * styles sit on `:host` rather than an inner element — a parent rule for the
 * host wins, so spacing stays local while the muted treatment stays shared.
 */
@Component({
  selector: 'app-status-note',
  standalone: true,
  template: `<ng-content />`,
  styles: `
    :host {
      display: block;
      color: var(--text-muted);
      font-size: 0.85rem;
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class StatusNoteComponent {}
