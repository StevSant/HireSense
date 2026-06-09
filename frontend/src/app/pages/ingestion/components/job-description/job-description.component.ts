import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { parseJobDescription } from '../../lib/parse-job-description';

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

  parsed = computed(() => parseJobDescription(this.description() ?? ''));
  hasSections = computed(() => this.parsed().sections.length > 0);
}
