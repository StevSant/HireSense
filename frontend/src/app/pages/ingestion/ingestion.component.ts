import { Component, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../environments/environment';

interface NormalizedJob {
  id: string;
  title: string;
  company: string;
  description: string;
  skills: string[];
  location: string;
  salary_range: string | null;
  source: string;
  url: string;
  posted_date: string | null;
}

interface FetchResponse {
  count: number;
  jobs: NormalizedJob[];
}

@Component({
  selector: 'app-ingestion',
  standalone: true,
  imports: [],
  templateUrl: './ingestion.component.html',
  styleUrl: './ingestion.component.scss',
})
export class IngestionComponent {
  jobs = signal<NormalizedJob[]>([]);
  loading = signal(false);
  error = signal('');

  constructor(private http: HttpClient) {}

  fetchJobs(): void {
    this.loading.set(true);
    this.error.set('');
    this.http.post<FetchResponse>(`${environment.apiUrl}/ingestion/fetch`, {}).subscribe({
      next: (res) => {
        this.jobs.set(res.jobs);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(err.error?.detail || 'Failed to fetch jobs');
        this.loading.set(false);
      },
    });
  }
}
