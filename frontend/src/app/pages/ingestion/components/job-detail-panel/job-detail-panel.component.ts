import { Component, input, output } from '@angular/core';
import { DatePipe } from '@angular/common';
import { NormalizedJob } from '../../models/normalized-job.model';

@Component({
  selector: 'app-job-detail-panel',
  standalone: true,
  imports: [DatePipe],
  templateUrl: './job-detail-panel.component.html',
  styleUrl: './job-detail-panel.component.scss',
})
export class JobDetailPanelComponent {
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
}
