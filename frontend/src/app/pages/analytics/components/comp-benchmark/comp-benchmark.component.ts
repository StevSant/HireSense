import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { CompBenchmark } from '../../models/comp-benchmark.model';
import { BarRow } from '../../models/bar-row.model';
import { SalaryBandComponent } from '../salary-band/salary-band.component';
import { BarChartComponent } from '../bar-chart/bar-chart.component';

const PERCENT = 100;

@Component({
  selector: 'app-comp-benchmark',
  standalone: true,
  imports: [SalaryBandComponent, BarChartComponent],
  templateUrl: './comp-benchmark.component.html',
  styleUrl: './comp-benchmark.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CompBenchmarkComponent {
  comp = input.required<CompBenchmark>();

  seniorityRows = computed<BarRow[]>(() => {
    const bands = this.comp().by_seniority;
    const max = Math.max(1, ...bands.map((b) => b.median_annual));
    return bands.map((b) => ({
      label: b.level,
      value: b.median_annual,
      pct: Math.round((b.median_annual / max) * PERCENT),
      note: this.fmt(b.median_annual),
    }));
  });

  // Candidate median relative to the market median: negative = below market.
  pipelineDelta = computed<number | null>(() => {
    const c = this.comp();
    if (c.your_median_annual === null || c.median_annual === null) return null;
    return Math.round(((c.your_median_annual - c.median_annual) / c.median_annual) * PERCENT);
  });

  fmt(v: number | null): string {
    return v === null ? '—' : v.toLocaleString('en-US');
  }
}
