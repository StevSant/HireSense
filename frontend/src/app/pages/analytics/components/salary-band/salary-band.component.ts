import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { TargetSalary } from '../../models/target-salary.model';
import { PayPeriod, periodUnit, toPeriod } from '../../../../core/utils/pay-period';

/** Left edge of the visual scale, as a fraction of p25 (20% headroom below). */
const SCALE_LOWER_FACTOR = 0.8;
/** Right edge of the visual scale, as a fraction of p75 (20% headroom above). */
const SCALE_UPPER_FACTOR = 1.2;
/** Smallest allowed scale span to avoid divide-by-zero on a degenerate band. */
const MIN_SCALE_SPAN = 1;
/** Track is expressed as a percentage, so positions clamp to [0, 100]. */
const TRACK_MIN_PERCENT = 0;
const TRACK_MAX_PERCENT = 100;

@Component({
  selector: 'app-salary-band',
  standalone: true,
  templateUrl: './salary-band.component.html',
  styleUrl: './salary-band.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SalaryBandComponent {
  target = input.required<TargetSalary>();
  period = input<PayPeriod>('annual');
  unit = computed(() => periodUnit(this.period()));

  // p25→p75 band positioned within a p25*SCALE_LOWER_FACTOR .. p75*SCALE_UPPER_FACTOR visual scale.
  band = computed(() => {
    const t = this.target();
    if (t.insufficient_data || t.p25_annual === null || t.p75_annual === null) return null;
    const lo = t.p25_annual * SCALE_LOWER_FACTOR;
    const hi = t.p75_annual * SCALE_UPPER_FACTOR;
    const span = Math.max(MIN_SCALE_SPAN, hi - lo);
    // Clamp to [0,100] so a marker never renders off-track if the backend ever
    // returns percentiles where median falls outside [p25, p75].
    const clamp = (v: number) => Math.max(TRACK_MIN_PERCENT, Math.min(TRACK_MAX_PERCENT, v));
    const left = clamp(((t.p25_annual - lo) / span) * TRACK_MAX_PERCENT);
    const width = clamp(((t.p75_annual - t.p25_annual) / span) * TRACK_MAX_PERCENT);
    const median =
      t.median_annual === null ? null : clamp(((t.median_annual - lo) / span) * TRACK_MAX_PERCENT);
    return { left, width, median };
  });

  fmt(v: number | null): string {
    const shown = toPeriod(v, this.period());
    return shown === null ? '—' : shown.toLocaleString('en-US');
  }
}
