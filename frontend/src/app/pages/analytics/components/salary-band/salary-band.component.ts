import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { TargetSalary } from '../../models/target-salary.model';

@Component({
  selector: 'app-salary-band',
  standalone: true,
  templateUrl: './salary-band.component.html',
  styleUrl: './salary-band.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SalaryBandComponent {
  target = input.required<TargetSalary>();

  // p25→p75 band positioned within a p25*0.8 .. p75*1.2 visual scale.
  band = computed(() => {
    const t = this.target();
    if (t.insufficient_data || t.p25_annual === null || t.p75_annual === null) return null;
    const lo = t.p25_annual * 0.8;
    const hi = t.p75_annual * 1.2;
    const span = Math.max(1, hi - lo);
    const left = ((t.p25_annual - lo) / span) * 100;
    const width = ((t.p75_annual - t.p25_annual) / span) * 100;
    const median = t.median_annual === null ? null : ((t.median_annual - lo) / span) * 100;
    return { left, width, median };
  });

  fmt(v: number | null): string {
    return v === null ? '—' : v.toLocaleString('en-US');
  }
}
