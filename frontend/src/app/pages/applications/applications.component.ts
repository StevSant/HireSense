import { Component, DestroyRef, OnInit, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Router, RouterLink } from '@angular/router';
import { DatePipe, TitleCasePipe } from '@angular/common';
import { ApplicationsService } from '../../core/services/applications.service';
import { ApplicationListItem } from './models/application-list-item.model';
import { ApplicationCreateDialogComponent } from './components/application-create-dialog.component';
import { scoreColor as toScoreColor } from '../../core/utils/score-color';
import { formatScorePercent } from '../../core/utils/format-score-percent';

@Component({
  selector: 'app-applications',
  standalone: true,
  imports: [DatePipe, TitleCasePipe, RouterLink, ApplicationCreateDialogComponent],
  templateUrl: './applications.component.html',
  styleUrl: './applications.component.scss',
})
export class ApplicationsComponent implements OnInit {
  private service = inject(ApplicationsService);
  private router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);

  applications = signal<ApplicationListItem[]>([]);
  loading = signal(false);
  error = signal('');
  showCreateDialog = signal(false);
  deletingId = signal<string | null>(null);

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set('');
    this.service.list().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (rows) => {
        this.applications.set(rows);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(err?.error?.detail ?? 'Failed to load applications');
        this.loading.set(false);
      },
    });
  }

  open(id: string): void {
    this.router.navigate(['/dashboard/applications', id]);
  }

  openCreate(): void {
    this.showCreateDialog.set(true);
  }

  onCreated(id: string): void {
    this.showCreateDialog.set(false);
    this.router.navigate(['/dashboard/applications', id]);
  }

  scoreColor(score: number | null): string {
    return toScoreColor(score);
  }

  scorePct(score: number | null): string {
    return formatScorePercent(score);
  }

  remove(app: ApplicationListItem, event: MouseEvent): void {
    event.stopPropagation();
    const label = `${app.title} · ${app.company}`;
    if (!confirm(`Delete "${label}"?\n\nThis removes the application and all its matches, optimizations, cover letters and interview prep. The original job in Ingestion is not affected.`)) {
      return;
    }
    this.deletingId.set(app.id);
    this.service.remove(app.id).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: () => {
        this.applications.update((rows) => rows.filter((r) => r.id !== app.id));
        this.deletingId.set(null);
      },
      error: (err) => {
        this.error.set(err?.error?.detail ?? 'Failed to delete application');
        this.deletingId.set(null);
      },
    });
  }
}
