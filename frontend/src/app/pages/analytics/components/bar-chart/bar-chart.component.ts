import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { BarRow } from '@core/contracts/bar-row.model';
import { StatusNoteComponent } from '@shared/ui';

@Component({
  selector: 'app-bar-chart',
  standalone: true,
  imports: [DecimalPipe, StatusNoteComponent],
  templateUrl: './bar-chart.component.html',
  styleUrl: './bar-chart.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class BarChartComponent {
  rows = input.required<BarRow[]>();
  emptyText = input<string>('No data yet.');
}
