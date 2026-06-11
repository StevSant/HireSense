import { ChangeDetectionStrategy, Component, computed, input, signal } from '@angular/core';
import { parseJobDescription } from '../../lib/parse-job-description';
import { JOB_DESCRIPTION_CLAMP_THRESHOLD } from '../../lib/job-description-clamp-threshold';

@Component({
  selector: 'app-job-description',
  standalone: true,
  imports: [],
  templateUrl: './job-description.component.html',
  styleUrl: './job-description.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class JobDescriptionComponent {
  description = input.required<string>();
  /** When set, long descriptions render height-clamped behind a toggle. */
  collapsible = input(false);

  expanded = signal(false);

  parsed = computed(() => parseJobDescription(this.description() ?? ''));
  hasSections = computed(() => this.parsed().sections.length > 0);

  canToggle = computed(
    () => this.collapsible() && (this.description() ?? '').length > JOB_DESCRIPTION_CLAMP_THRESHOLD,
  );
  clamped = computed(() => this.canToggle() && !this.expanded());

  toggle(): void {
    this.expanded.update((v) => !v);
  }
}
