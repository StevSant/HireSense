import { ChangeDetectionStrategy, Component, input } from '@angular/core';

export interface BarRow {
  label: string;
  value: number;
  pct: number;
  note?: string;
}

@Component({
  selector: 'app-bar-chart',
  standalone: true,
  templateUrl: './bar-chart.component.html',
  styleUrl: './bar-chart.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class BarChartComponent {
  rows = input.required<BarRow[]>();
  emptyText = input<string>('No data yet.');
}
