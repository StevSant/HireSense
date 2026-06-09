import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { BarRow } from '../../models/bar-row.model';

@Component({
  selector: 'app-bar-chart',
  standalone: true,
  imports: [DecimalPipe],
  templateUrl: './bar-chart.component.html',
  styleUrl: './bar-chart.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class BarChartComponent {
  rows = input.required<BarRow[]>();
  emptyText = input<string>('No data yet.');
}
