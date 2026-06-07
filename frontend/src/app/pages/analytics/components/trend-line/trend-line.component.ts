import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { TrendPoint } from '../../models/market-intel.model';

/** SVG viewBox width in user units. */
const VIEWBOX_WIDTH = 320;
/** SVG viewBox height in user units. */
const VIEWBOX_HEIGHT = 80;
/** Inner padding so the polyline never touches the viewBox edges. */
const VIEWBOX_PADDING = 4;
/** Minimum points required to draw a line (a single point has no segment). */
const MIN_POINTS_FOR_LINE = 2;
/** Floor for the max value so a flat all-zero series doesn't divide by zero. */
const MIN_MAX_COUNT = 1;
/** Decimal places kept when emitting polyline coordinates. */
const COORD_PRECISION = 1;

@Component({
  selector: 'app-trend-line',
  standalone: true,
  templateUrl: './trend-line.component.html',
  styleUrl: './trend-line.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TrendLineComponent {
  points = input.required<TrendPoint[]>();

  readonly viewBox = `0 0 ${VIEWBOX_WIDTH} ${VIEWBOX_HEIGHT}`;

  polyline = computed(() => {
    const pts = this.points();
    if (pts.length < MIN_POINTS_FOR_LINE) return '';
    const max = Math.max(...pts.map((p) => p.count), MIN_MAX_COUNT);
    const stepX = (VIEWBOX_WIDTH - 2 * VIEWBOX_PADDING) / (pts.length - 1);
    return pts
      .map((p, i) => {
        const x = VIEWBOX_PADDING + i * stepX;
        const y =
          VIEWBOX_HEIGHT -
          VIEWBOX_PADDING -
          (p.count / max) * (VIEWBOX_HEIGHT - 2 * VIEWBOX_PADDING);
        return `${x.toFixed(COORD_PRECISION)},${y.toFixed(COORD_PRECISION)}`;
      })
      .join(' ');
  });
}
