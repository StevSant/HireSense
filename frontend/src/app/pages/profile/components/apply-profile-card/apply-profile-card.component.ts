import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  effect,
  inject,
  input,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { ApplyProfile } from '../../models/apply-profile.model';
import { CandidateProfile } from '../../models/candidate-profile.model';
import { ScreeningAnswer } from '../../models/screening-answer.model';
import { ProfileService } from '../../../../core/services/profile.service';

type TriState = '' | 'yes' | 'no';

interface ApplyProfileFormState {
  preferred_name: string;
  work_authorization: string;
  requires_visa_sponsorship: TriState;
  desired_salary: string;
  years_of_experience: string;
  willing_to_relocate: TriState;
  start_availability: string;
  screening_answers: ScreeningAnswer[];
}

function triFromBool(value: boolean | null | undefined): TriState {
  if (value === true) return 'yes';
  if (value === false) return 'no';
  return '';
}

function boolFromTri(value: TriState): boolean | null {
  if (value === 'yes') return true;
  if (value === 'no') return false;
  return null;
}

function snapshot(profile: CandidateProfile): ApplyProfileFormState {
  const ap = profile.apply_profile ?? null;
  return {
    preferred_name: ap?.preferred_name ?? '',
    work_authorization: ap?.work_authorization ?? '',
    requires_visa_sponsorship: triFromBool(ap?.requires_visa_sponsorship),
    desired_salary: ap?.desired_salary ?? '',
    years_of_experience: ap?.years_of_experience != null ? String(ap.years_of_experience) : '',
    willing_to_relocate: triFromBool(ap?.willing_to_relocate),
    start_availability: ap?.start_availability ?? '',
    screening_answers: (ap?.screening_answers ?? []).map((a) => ({ ...a })),
  };
}

@Component({
  selector: 'app-apply-profile-card',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './apply-profile-card.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ApplyProfileCardComponent {
  private profileService = inject(ProfileService);
  private readonly destroyRef = inject(DestroyRef);

  profile = input.required<CandidateProfile>();

  form = signal<ApplyProfileFormState>(this.empty());
  baseline = signal<ApplyProfileFormState>(this.empty());
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

  private empty(): ApplyProfileFormState {
    return {
      preferred_name: '',
      work_authorization: '',
      requires_visa_sponsorship: '',
      desired_salary: '',
      years_of_experience: '',
      willing_to_relocate: '',
      start_availability: '',
      screening_answers: [],
    };
  }

  set<K extends keyof ApplyProfileFormState>(key: K, value: ApplyProfileFormState[K]): void {
    this.form.update((current) => ({ ...current, [key]: value }));
  }

  addScreeningAnswer(): void {
    this.form.update((current) => ({
      ...current,
      screening_answers: [...current.screening_answers, { question: '', answer: '' }],
    }));
  }

  updateScreeningAnswer(index: number, field: keyof ScreeningAnswer, value: string): void {
    this.form.update((current) => ({
      ...current,
      screening_answers: current.screening_answers.map((a, i) =>
        i === index ? { ...a, [field]: value } : a,
      ),
    }));
  }

  removeScreeningAnswer(index: number): void {
    this.form.update((current) => ({
      ...current,
      screening_answers: current.screening_answers.filter((_, i) => i !== index),
    }));
  }

  isDirty(): boolean {
    return JSON.stringify(this.form()) !== JSON.stringify(this.baseline());
  }

  private toPayload(state: ApplyProfileFormState): ApplyProfile {
    const years = state.years_of_experience.trim();
    const parsedYears = years ? Number.parseInt(years, 10) : NaN;
    return {
      preferred_name: state.preferred_name.trim() || null,
      work_authorization: state.work_authorization.trim() || null,
      requires_visa_sponsorship: boolFromTri(state.requires_visa_sponsorship),
      desired_salary: state.desired_salary.trim() || null,
      years_of_experience: Number.isNaN(parsedYears) ? null : parsedYears,
      willing_to_relocate: boolFromTri(state.willing_to_relocate),
      start_availability: state.start_availability.trim() || null,
      screening_answers: state.screening_answers
        .map((a) => ({ question: a.question.trim(), answer: a.answer.trim() }))
        .filter((a) => a.question || a.answer),
    };
  }

  save(): void {
    if (!this.isDirty() || this.saving()) return;
    this.saving.set(true);
    this.error.set('');
    this.profileService
      .setApplyProfile(this.toPayload(this.form()))
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
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
          this.error.set(err?.error?.detail ?? 'Failed to save your apply profile');
        },
      });
  }
}
