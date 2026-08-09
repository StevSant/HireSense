import { ChangeDetectionStrategy, Component } from '@angular/core';
import { CoverLetterLibraryComponent } from '../../components/cover-letter-library/cover-letter-library.component';
import { CoverLetterTemplatesComponent } from '../../components/cover-letter-templates/cover-letter-templates.component';

/** Profile → Cover letters. Pure host for the library and template cards. */
@Component({
  selector: 'app-profile-cover-letters-tab',
  standalone: true,
  imports: [CoverLetterLibraryComponent, CoverLetterTemplatesComponent],
  templateUrl: './profile-cover-letters-tab.component.html',
  styleUrl: './profile-cover-letters-tab.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProfileCoverLettersTabComponent {}
