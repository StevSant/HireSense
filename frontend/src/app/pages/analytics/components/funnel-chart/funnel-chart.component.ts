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

  width(reached: number): number {
    return Math.round((reached / this.maxReached()) * PERCENT_SCALE);
  }

  pct(conversion: number | null): string | null {
    return conversion === null ? null : `${Math.round(conversion * PERCENT_SCALE)}%`;
  }
}
