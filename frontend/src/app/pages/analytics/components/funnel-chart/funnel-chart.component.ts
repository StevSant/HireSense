import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { FunnelMetrics } from '../../models/funnel-metrics.model';

/** Floor for the widest stage so an all-empty funnel doesn't divide by zero. */
const MIN_REACHED = 1;
/** Bar width and conversion rate are rendered as percentages. */
const PERCENT_SCALE = 100;

@Component({
  selector: 'app-funnel-chart',
  standalone: true,
  templateUrl: './funnel-chart.component.html',
  styleUrl: './funnel-chart.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FunnelChartComponent {
  metrics = input.required<FunnelMetrics>();

  // Bar width relative to the first stage's reached count (the widest).
  maxReached = computed(() => Math.max(MIN_REACHED, ...this.metrics().stages.map((s) => s.reached)));

  // Names the steepest consecutive drop-off — the stage where the pipeline leaks most.
  insight = computed<string | null>(() => {
    const m = this.metrics();
    if (m.total_applications === 0 || m.stages.length < 2) return null;
    let worst: { from: string; to: string; reached: number; prev: number; conv: number } | null = null;
    for (let i = 1; i < m.stages.length; i++) {
      const s = m.stages[i];
      const prev = m.stages[i - 1];
      if (prev.reached > 0 && s.conversion_from_prev !== null) {
        if (worst === null || s.conversion_from_prev < worst.conv) {
          worst = { from: prev.stage, to: s.stage, reached: s.reached, prev: prev.reached, conv: s.conversion_from_prev };
        }
      }
    }
    if (worst === null) return null;
    if (worst.conv >= 1) return 'No leaks — every application is advancing through your pipeline.';
    const cap = (x: string) => x.charAt(0).toUpperCase() + x.slice(1);
    return `Biggest drop-off: ${cap(worst.from)} → ${cap(worst.to)} — ${worst.reached} of ${worst.prev} advanced.`;
  });

  width(reached: number): number {
    return Math.round((reached / this.maxReached()) * PERCENT_SCALE);
  }

  pct(conversion: number | null): string | null {
    return conversion === null ? null : `${Math.round(conversion * PERCENT_SCALE)}%`;
  }
}
