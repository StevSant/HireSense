import { ChangeDetectionStrategy, Component } from '@angular/core';

/**
 * The small ring that spins inside a filled button while its action runs.
 *
 * Sized and coloured for `.btn-primary` (white on the accent fill), which is
 * the only place a button spinner appears today.
 *
 * Carries its own `@keyframes` under a namespaced name rather than borrowing
 * the global `spin`: Angular does not scope keyframes, so a primitive that
 * depends on one defined elsewhere breaks silently the moment that stylesheet
 * moves.
 */
@Component({
  selector: 'app-button-spinner',
  standalone: true,
  template: '',
  styles: `
    :host {
      /* Blockified anyway as a flex item of the button; declared so the box
         still has its size if a caller ever drops it outside a flex row. */
      display: inline-block;
      width: 16px;
      height: 16px;
      border: 2px solid rgba(255, 255, 255, 0.3);
      border-top-color: white;
      border-radius: 50%;
      animation: button-spinner-spin 0.7s linear infinite;
    }

    @keyframes button-spinner-spin {
      to {
        transform: rotate(360deg);
      }
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ButtonSpinnerComponent {}
