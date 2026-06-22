import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { SchedulerService } from '../../../core/services/scheduler.service';
import { ScheduledJob } from '../../../core/models/scheduler.model';

@Component({
  selector: 'app-scheduler',
  standalone: true,
  imports: [DatePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './scheduler.component.html',
  styleUrl: './scheduler.component.scss',
})
export class SchedulerComponent implements OnInit {
  private readonly service = inject(SchedulerService);
  readonly jobs = signal<ScheduledJob[]>([]);
  readonly busy = signal<string | null>(null);

  ngOnInit(): void {
    this.reload();
  }

  reload(): void {
    this.service.listJobs().subscribe((jobs) => this.jobs.set(jobs));
  }

  toggle(job: ScheduledJob): void {
    this.busy.set(job.name);
    this.service.toggle(job.name, !job.enabled).subscribe(() => {
      this.busy.set(null);
      this.reload();
    });
  }

  runNow(job: ScheduledJob): void {
    this.busy.set(job.name);
    this.service.runNow(job.name).subscribe(() => {
      this.busy.set(null);
      this.reload();
    });
  }
}
