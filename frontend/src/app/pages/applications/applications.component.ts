import { Component, OnInit, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { DatePipe, TitleCasePipe } from '@angular/common';
import { ApplicationsService } from '../../core/services/applications.service';
import { ApplicationListItem } from './models/application-list-item.model';
import { ApplicationCreateDialogComponent } from './components/application-create-dialog.component';

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

  applications = signal<ApplicationListItem[]>([]);
  loading = signal(false);
  error = signal('');
  showCreateDialog = signal(false);

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set('');
    this.service.list().subscribe({
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
    if (score === null) return '#9ca3af';
    if (score >= 0.7) return '#16a34a';
    if (score >= 0.4) return '#ca8a04';
    return '#dc2626';
  }

  scorePct(score: number | null): string {
    if (score === null) return '—';
    return (score * 100).toFixed(0) + '%';
  }
}
