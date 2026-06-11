import { ChangeDetectionStrategy, Component, input } from '@angular/core';

/** Matched vs. missing skills for the job scorecard rail. Two stacked tag
 *  groups (matched, then gaps); each hides when its collection is empty. */
@Component({
  selector: 'app-match-skills',
  standalone: true,
  imports: [],
  templateUrl: './match-skills.component.html',
  styleUrl: './match-skills.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class MatchSkillsComponent {
  matched = input.required<string[]>();
  missing = input.required<string[]>();
}
