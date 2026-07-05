import {
  Component,
  DestroyRef,
  OnChanges,
  computed,
  inject,
  input,
  output,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { ApplicationsService } from '../../../core/services/applications.service';
import { ApplicationAggregate } from '../models/application-aggregate.model';
import { SkillChipsComponent } from './skill-chips.component';

@Component({
  selector: 'app-job-tab',
  standalone: true,
  imports: [FormsModule, SkillChipsComponent],
  templateUrl: './job-tab.component.html',
  styleUrl: './job-tab.component.scss',
})
export class JobTabComponent implements OnChanges {
  private service = inject(ApplicationsService);
  private readonly destroyRef = inject(DestroyRef);

  aggregate = input.required<ApplicationAggregate>();
  changed = output<void>();

  description = signal('');
  skills = signal<string[]>([]);
  saving = signal(false);
  // True after a successful save; reset the moment the user edits again, so the
  // "Saved ✓" confirmation can't go stale (the save itself gave no feedback).
  saved = signal(false);
  regenerating = signal(false);
  error = signal('');

  ngOnChanges(): void {
    const snap = this.aggregate().job_snapshot;
    this.description.set(snap?.description ?? '');
    this.skills.set(snap?.required_skills ?? []);
    this.saved.set(false);
  }

  source = computed(() => this.aggregate().job_snapshot?.source ?? 'manual');

  setDescription(value: string): void {
    this.description.set(value);
    this.saved.set(false);
  }

  save(): void {
    this.saving.set(true);
    this.saved.set(false);
    this.error.set('');
    this.service
      .updateSnapshot(this.aggregate().id, {
        description: this.description(),
        required_skills: this.skills(),
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.saving.set(false);
          this.saved.set(true);
          this.changed.emit();
        },
        error: (err) => {
          this.error.set(err?.error?.detail ?? 'Save failed');
          this.saving.set(false);
        },
      });
  }

  regenerate(): void {
    this.regenerating.set(true);
    this.error.set('');
    this.service
      .regenerateSkills(this.aggregate().id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (agg) => {
          this.skills.set(agg.job_snapshot?.required_skills ?? []);
          this.regenerating.set(false);
          this.changed.emit();
        },
        error: (err) => {
          this.error.set(err?.error?.detail ?? 'Regenerate failed');
          this.regenerating.set(false);
        },
      });
  }

  addSkill(skill: string): void {
    this.skills.update((arr) => [...arr, skill]);
    this.saved.set(false);
  }

  removeSkill(skill: string): void {
    this.skills.update((arr) => arr.filter((s) => s !== skill));
    this.saved.set(false);
  }
}
