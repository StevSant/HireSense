import { Component, inject, input, output } from '@angular/core';
import { DatePipe } from '@angular/common';
import { Router } from '@angular/router';
import { NormalizedJob } from '../../models/normalized-job.model';

@Component({
  selector: 'app-job-detail-panel',
  standalone: true,
  imports: [DatePipe],
  templateUrl: './job-detail-panel.component.html',
  styleUrl: './job-detail-panel.component.scss',
})
export class JobDetailPanelComponent {
  private router = inject(Router);

  job = input.required<NormalizedJob>();
  tracked = input<boolean>(false);

  close = output<void>();
  track = output<string>();

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
