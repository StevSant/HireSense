import { Component, OnInit, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { TitleCasePipe, DatePipe } from '@angular/common';
import { environment } from '../../../environments/environment';
import { TrackedApplication, ApplicationStatus } from '../../core/models/tracked-application.model';
import { CreateApplicationRequest } from '../../core/models/create-application-request.model';
import { UpdateApplicationRequest } from '../../core/models/update-application-request.model';

@Component({
  selector: 'app-tracking',
  standalone: true,
  imports: [FormsModule, TitleCasePipe, DatePipe],
  templateUrl: './tracking.component.html',
  styleUrl: './tracking.component.scss',
})
export class TrackingComponent implements OnInit {
  applications = signal<TrackedApplication[]>([]);
  loading = signal(false);
  error = signal('');
  statusFilter = signal<ApplicationStatus | ''>('');
  showAddForm = signal(false);

  newTitle = signal('');
  newCompany = signal('');
  newUrl = signal('');
  newNotes = signal('');
  adding = signal(false);

  readonly statusOptions: ApplicationStatus[] = [
    'saved',
    'applied',
    'interviewing',
    'offered',
    'accepted',
    'rejected',
  ];

  constructor(private http: HttpClient) {}

  ngOnInit(): void {
    this.loadApplications();
  }

  loadApplications(): void {
    this.loading.set(true);
    this.error.set('');
    const filter = this.statusFilter();
    const url = filter
      ? `${environment.apiUrl}/tracking?status=${filter}`
      : `${environment.apiUrl}/tracking`;
    this.http.get<TrackedApplication[]>(url).subscribe({
      next: (apps) => {
        this.applications.set(apps);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(err.error?.detail || 'Failed to load applications');
        this.loading.set(false);
      },
    });
  }

  onStatusFilterChange(event: Event): void {
    const select = event.target as HTMLSelectElement;
    this.statusFilter.set(select.value as ApplicationStatus | '');
    this.loadApplications();
  }

  toggleAddForm(): void {
    this.showAddForm.update((v) => !v);
    if (!this.showAddForm()) {
      this.resetForm();
    }
  }

  addApplication(): void {
    const title = this.newTitle().trim();
    const company = this.newCompany().trim();
    if (!title && !company) {
      return;
    }
    this.adding.set(true);
    const body: CreateApplicationRequest = {};
    if (title) body.title = title;
    if (company) body.company = company;
    const url = this.newUrl().trim();
    if (url) body.url = url;
    const notes = this.newNotes().trim();
    if (notes) body.notes = notes;

    this.http.post<TrackedApplication>(`${environment.apiUrl}/tracking`, body).subscribe({
      next: (app) => {
        this.applications.update((list) => [app, ...list]);
        this.adding.set(false);
        this.showAddForm.set(false);
        this.resetForm();
      },
      error: (err) => {
        this.error.set(err.error?.detail || 'Failed to add application');
        this.adding.set(false);
      },
    });
  }

  updateStatus(app: TrackedApplication, event: Event): void {
    const select = event.target as HTMLSelectElement;
    const newStatus = select.value as ApplicationStatus;
    const body: UpdateApplicationRequest = { status: newStatus };
    this.http.patch<TrackedApplication>(`${environment.apiUrl}/tracking/${app.id}`, body).subscribe({
      next: (updated) => {
        this.applications.update((list) =>
          list.map((a) => (a.id === updated.id ? updated : a)),
        );
      },
      error: (err) => {
        this.error.set(err.error?.detail || 'Failed to update status');
        select.value = app.status;
      },
    });
  }

  deleteApplication(id: string): void {
    this.http.delete(`${environment.apiUrl}/tracking/${id}`).subscribe({
      next: () => {
        this.applications.update((list) => list.filter((a) => a.id !== id));
      },
      error: (err) => {
        this.error.set(err.error?.detail || 'Failed to delete application');
      },
    });
  }

  private resetForm(): void {
    this.newTitle.set('');
    this.newCompany.set('');
    this.newUrl.set('');
    this.newNotes.set('');
  }

  onNewTitleInput(event: Event): void {
    this.newTitle.set((event.target as HTMLInputElement).value);
  }

  onNewCompanyInput(event: Event): void {
    this.newCompany.set((event.target as HTMLInputElement).value);
  }

  onNewUrlInput(event: Event): void {
    this.newUrl.set((event.target as HTMLInputElement).value);
  }

  onNewNotesInput(event: Event): void {
    this.newNotes.set((event.target as HTMLTextAreaElement).value);
  }
}
