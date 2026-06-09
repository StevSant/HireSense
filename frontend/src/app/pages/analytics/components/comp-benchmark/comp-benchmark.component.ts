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
      note: `· ${b.sample_size}`,
    }));
  });

  // Candidate median relative to the market median: negative = below market.
  pipelineDelta = computed<number | null>(() => {
    const c = this.comp();
    if (c.your_median_annual === null || c.median_annual === null) return null;
    return Math.round(((c.your_median_annual - c.median_annual) / c.median_annual) * PERCENT);
  });

  // Plain-language read on the delta: "52% below" / "12% above" / "in line with".
  deltaLabel = computed<string | null>(() => {
    const d = this.pipelineDelta();
    if (d === null) return null;
    if (d === 0) return 'in line with';
    return `${Math.abs(d)}% ${d < 0 ? 'below' : 'above'}`;
  });

  // Honest caveat about how thin the tracked-salary sample is.
  sampleNote = computed<string>(() => {
    const n = this.comp().your_sample_size;
    return n <= 1
      ? 'Based on just 1 tracked job with a listed salary — add more for a stronger read.'
      : `Based on ${n} tracked jobs with listed salaries.`;
  });

  fmt(v: number | null): string {
    return v === null ? '—' : v.toLocaleString('en-US');
  }
}
