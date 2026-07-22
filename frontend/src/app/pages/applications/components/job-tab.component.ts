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
import { TrackingService } from '../../../core/services/tracking.service';
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
  private trackingService = inject(TrackingService);
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
  title = signal('');
  company = signal('');
  url = signal('');
  notes = signal('');
  location = signal('');
  remoteModality = signal<'remote' | 'hybrid' | 'on_site' | ''>('');
  salaryRange = signal('');
  listingSource = signal('');
  postedDate = signal('');
  detailsSaving = signal(false);
  detailsSaved = signal(false);

  ngOnChanges(): void {
    const snap = this.aggregate().job_snapshot;
    this.description.set(snap?.description ?? '');
    this.skills.set(snap?.required_skills ?? []);
    const aggregate = this.aggregate();
    this.title.set(aggregate.title);
    this.company.set(aggregate.company);
    this.url.set(aggregate.url ?? '');
    this.notes.set(aggregate.notes ?? '');
    this.location.set(aggregate.location ?? '');
    this.remoteModality.set(aggregate.remote_modality ?? '');
    this.salaryRange.set(aggregate.salary_range ?? '');
    this.listingSource.set(aggregate.source ?? '');
    this.postedDate.set(aggregate.posted_date?.slice(0, 10) ?? '');
    this.saved.set(false);
    this.detailsSaved.set(false);
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

  saveDetails(): void {
    const title = this.title().trim();
    const company = this.company().trim();
    if (!title || !company) {
      this.error.set('Title and company are required');
      return;
    }
    this.detailsSaving.set(true);
    this.detailsSaved.set(false);
    this.error.set('');
    this.trackingService
      .update(this.aggregate().id, {
        title,
        company,
        url: this.url().trim() || null,
        notes: this.notes().trim() || null,
        location: this.location().trim() || null,
        remote_modality: this.remoteModality() || null,
        salary_range: this.salaryRange().trim() || null,
        source: this.listingSource().trim() || null,
        posted_date: this.postedDate() ? `${this.postedDate()}T00:00:00Z` : null,
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.detailsSaving.set(false);
          this.detailsSaved.set(true);
          this.changed.emit();
        },
        error: (err) => {
          this.error.set(err?.error?.detail ?? 'Save failed');
          this.detailsSaving.set(false);
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
