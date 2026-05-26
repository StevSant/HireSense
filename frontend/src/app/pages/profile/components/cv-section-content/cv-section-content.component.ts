import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { parseCvSection } from '../../lib/parse-cv-section';

@Component({
  selector: 'app-cv-section-content',
  standalone: true,
  imports: [],
  templateUrl: './cv-section-content.component.html',
  styleUrl: './cv-section-content.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CvSectionContentComponent {
  content = input.required<string>();

  blocks = computed(() => parseCvSection(this.content()));
}
