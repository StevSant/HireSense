import {
  ChangeDetectionStrategy,
  Component,
  effect,
  inject,
  input,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CandidateProfile } from '../../models/candidate-profile.model';
import {
  ProfileManualFieldsUpdate,
  ProfileService,
} from '../../../../core/services/profile.service';

type FormState = {
  name: string;
  email: string;
  phone: string;
  location: string;
  linkedin_url: string;
  github_url: string;
  portfolio_url: string;
};

const FIELDS: ReadonlyArray<keyof FormState> = [
  'name',
  'email',
  'phone',
  'location',
  'linkedin_url',
  'github_url',
  'portfolio_url',
];

function snapshot(profile: CandidateProfile): FormState {
  return {
    name: profile.name ?? '',
    email: profile.email ?? '',
    phone: profile.phone ?? '',
    location: profile.location ?? '',
    linkedin_url: profile.linkedin_url ?? '',
    github_url: profile.github_url ?? '',
    portfolio_url: profile.portfolio_url ?? '',
  };
}

@Component({
  selector: 'app-manual-fields-form',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './manual-fields-form.component.html',
  styleUrl: './manual-fields-form.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ManualFieldsFormComponent {
  private profileService = inject(ProfileService);

  profile = input.required<CandidateProfile>();

  form = signal<FormState>({
    name: '',
    email: '',
    phone: '',
    location: '',
    linkedin_url: '',
    github_url: '',
    portfolio_url: '',
  });
  baseline = signal<FormState>(this.form());
  saving = signal(false);
  error = signal('');
  savedFlash = signal(false);

  constructor() {
    effect(() => {
      const snap = snapshot(this.profile());
      this.form.set(snap);
      this.baseline.set(snap);
    });
  }

  set<K extends keyof FormState>(key: K, value: string): void {
    this.form.update((current) => ({ ...current, [key]: value }));
  }

  isDirty(): boolean {
    const current = this.form();
    const baseline = this.baseline();
    return FIELDS.some((f) => current[f] !== baseline[f]);
  }

  reset(): void {
    this.form.set(this.baseline());
    this.error.set('');
  }

  save(): void {
    if (!this.isDirty() || this.saving()) return;
    const current = this.form();
    const baseline = this.baseline();
    const update: ProfileManualFieldsUpdate = {};
    for (const field of FIELDS) {
      if (current[field] !== baseline[field]) {
        update[field] = current[field].trim() || null;
      }
    }
    this.saving.set(true);
    this.error.set('');
    this.profileService.updateManualFields(this.profile().id, update).subscribe({
      next: (saved) => {
        this.saving.set(false);
        const snap = snapshot(saved);
        this.form.set(snap);
        this.baseline.set(snap);
        this.savedFlash.set(true);
        setTimeout(() => this.savedFlash.set(false), 2200);
      },
      error: (err) => {
        this.saving.set(false);
        this.error.set(err?.error?.detail ?? 'Failed to save changes');
      },
    });
  }
}
