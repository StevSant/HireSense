import { ChangeDetectionStrategy, Component, computed, inject, input, output } from '@angular/core';
import { DatePipe } from '@angular/common';
import { Router } from '@angular/router';
import { NormalizedJob } from '../../models/normalized-job.model';
import { parseJobDescription } from '../../lib/parse-job-description';

@Component({
  selector: 'app-job-detail-panel',
  standalone: true,
  imports: [DatePipe],
  templateUrl: './job-detail-panel.component.html',
  styleUrl: './job-detail-panel.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class JobDetailPanelComponent {
  private router = inject(Router);

  job = input.required<NormalizedJob>();
  tracked = input<boolean>(false);

  close = output<void>();
  track = output<string>();

  parsedDescription = computed(() => parseJobDescription(this.job().description ?? ''));

  hasStructuredSections = computed(() => this.parsedDescription().sections.length > 0);

  /** Pull out the most prominent compensation line for the header strip. */
  compensationHighlight = computed(() => {
    const job = this.job();
    if (job.salary_range && job.salary_range.trim()) return job.salary_range.trim();
    const compSection = this.parsedDescription().sections.find(
      (s) => s.emphasis === 'compensation',
    );
    if (!compSection) return null;
    const firstLine = compSection.body
      .split('\n')
      .map((l) => l.trim())
      .find((l) => l.length > 0);
    return firstLine ?? null;
  });

  onOverlayClick(event: MouseEvent): void {
    if ((event.target as HTMLElement).classList.contains('panel-overlay')) {
      this.close.emit();
    }
  }

  onTrack(): void {
    this.track.emit(this.job().id);
  }

  goToMatching(): void {
    this.router.navigate(['/dashboard/matching'], { queryParams: { job_id: this.job().id } });
    this.close.emit();
  }

  goToOptimization(): void {
    this.router.navigate(['/dashboard/optimization'], { queryParams: { job_id: this.job().id } });
    this.close.emit();
  }

  goToInterview(): void {
    this.router.navigate(['/dashboard/interview'], { queryParams: { job_id: this.job().id } });
    this.close.emit();
  }
}
