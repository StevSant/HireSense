import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { FunnelMetrics } from '../../models/funnel-metrics.model';

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
  maxReached = computed(() => Math.max(1, ...this.metrics().stages.map((s) => s.reached)));

  width(reached: number): number {
    return Math.round((reached / this.maxReached()) * 100);
  }

  pct(conversion: number | null): string | null {
    return conversion === null ? null : `${Math.round(conversion * 100)}%`;
  }
}
