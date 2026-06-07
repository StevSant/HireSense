import { Component, DestroyRef, computed, inject, input, output, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ApplicationsService } from '../../../core/services/applications.service';
import { ApplicationAggregate } from '../models/application-aggregate.model';

@Component({
  selector: 'app-interview-tab',
  standalone: true,
  templateUrl: './interview-tab.component.html',
  styleUrl: './interview-tab.component.scss',
})
export class InterviewTabComponent {
  private service = inject(ApplicationsService);
  private readonly destroyRef = inject(DestroyRef);

  aggregate = input.required<ApplicationAggregate>();
  changed = output<void>();

  running = signal(false);
  error = signal('');

  prep = computed(() => this.aggregate().latest_interview_prep);

  run(): void {
    this.running.set(true);
    this.error.set('');
    this.service.generateInterviewPrep(this.aggregate().id).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: () => {
        this.running.set(false);
        this.changed.emit();
      },
      error: (err) => {
        this.error.set(err?.error?.detail ?? 'Prep generation failed');
        this.running.set(false);
      },
    });
  }
}
