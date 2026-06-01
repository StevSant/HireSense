import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { TrendPoint } from '../../models/market-intel.model';

const W = 320;
const H = 80;
const PAD = 4;

@Component({
  selector: 'app-trend-line',
  standalone: true,
  templateUrl: './trend-line.component.html',
  styleUrl: './trend-line.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TrendLineComponent {
  points = input.required<TrendPoint[]>();

  readonly viewBox = `0 0 ${W} ${H}`;

  polyline = computed(() => {
    const pts = this.points();
    if (pts.length < 2) return '';
    const max = Math.max(...pts.map((p) => p.count), 1);
    const stepX = (W - 2 * PAD) / (pts.length - 1);
    return pts
      .map((p, i) => {
        const x = PAD + i * stepX;
        const y = H - PAD - (p.count / max) * (H - 2 * PAD);
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(' ');
  });
}
