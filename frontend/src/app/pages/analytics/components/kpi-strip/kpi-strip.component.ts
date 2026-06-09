import { ChangeDetectionStrategy, Component, input } from '@angular/core';

export interface KpiTile {
  label: string;
  value: string;
  hint?: string;
}

@Component({
  selector: 'app-kpi-strip',
  standalone: true,
  templateUrl: './kpi-strip.component.html',
  styleUrl: './kpi-strip.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KpiStripComponent {
  tiles = input.required<KpiTile[]>();
}
