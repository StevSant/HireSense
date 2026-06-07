import { Component, DestroyRef, OnInit, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { ApplicationsService } from '../../core/services/applications.service';
import { IngestionService } from '../../core/services/ingestion.service';

@Component({
  selector: 'app-optimization',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './optimization.component.html',
  styleUrl: './optimization.component.scss',
})
export class OptimizationComponent implements OnInit {
  private service = inject(ApplicationsService);
  private ingestionService = inject(IngestionService);
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);

  title = signal('');
  company = signal('');
  description = signal('');
  saving = signal(false);
  error = signal('');

  // Set once a job_id query param has been resolved into a pre-filled job, so
  // the template can render the job-context header and adjusted intro copy.
  prefilledFromJob = signal(false);
  // Surfaced when a job_id was supplied but the fetch failed — the form still
  // works as a manual-entry fallback, we just warn the user it didn't load.
  prefillNotice = signal('');

  ngOnInit(): void {
    this.applyJobIdFromQuery();
  }

  private applyJobIdFromQuery(): void {
    const jobId = this.route.snapshot.queryParamMap.get('job_id');
    if (!jobId) return;
    this.ingestionService
      .getJob(jobId)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (job) => {
          this.title.set(job.title);
          this.company.set(job.company);
          this.description.set(job.description);
          this.prefilledFromJob.set(true);
        },
        error: () => {
          this.prefillNotice.set(
            "We couldn't load that job automatically. Fill in the details below to continue.",
          );
        },
      });
  }

  submit(): void {
    const t = this.title().trim();
    const c = this.company().trim();
    const d = this.description().trim();
    if (!t || !c || !d) {
      this.error.set('Title, company, and description are required');
      return;
    }
    this.saving.set(true);
    this.error.set('');
    this.service
      .createManual({ title: t, company: c, description: d })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (agg) => {
          this.router.navigate(['/dashboard/applications', agg.id], {
            queryParams: { tab: 'cv' },
          });
        },
        error: (err) => {
          this.error.set(err?.error?.detail ?? 'Create failed');
          this.saving.set(false);
        },
      });
  }
}
