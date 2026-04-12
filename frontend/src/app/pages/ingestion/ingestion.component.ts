import { Component, OnInit, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../environments/environment';
import { CreateApplicationRequest } from '../../core/models/create-application-request.model';
import { FetchResponse } from './models/fetch-response.model';
import { NormalizedJob } from './models/normalized-job.model';
import { PortalEntry } from './models/portal-entry.model';
import { ScanPortalsRequest } from './models/scan-portals-request.model';
import { ScanError, ScanResult } from './models/scan-result.model';

@Component({
  selector: 'app-ingestion',
  standalone: true,
  imports: [],
  templateUrl: './ingestion.component.html',
  styleUrl: './ingestion.component.scss',
})
export class IngestionComponent implements OnInit {
  jobs = signal<NormalizedJob[]>([]);
  loading = signal(false);
  error = signal('');
  trackedJobIds = signal<Set<string>>(new Set());

  // Portal scanning state
  portals = signal<PortalEntry[]>([]);
  availableCategories = signal<string[]>([]);
  selectedCategories = signal<string[]>([]);
  selectedCompanies = signal<string[]>([]);
  scanKeyword = signal('');
  scanning = signal(false);
  scanSummary = signal('');
  scanErrors = signal<ScanError[]>([]);
  showFilters = signal(false);

  constructor(private http: HttpClient) {}

  ngOnInit(): void {
    this.loadPortals();
  }

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

  loadPortals(): void {
    this.http.get<PortalEntry[]>(`${environment.apiUrl}/ingestion/portals`).subscribe({
      next: (portals) => {
        this.portals.set(portals);
        const allCategories = portals.flatMap((p) => p.categories);
        const unique = [...new Set(allCategories)].sort();
        this.availableCategories.set(unique);
      },
      error: () => {
        // Non-fatal: portal list is optional
      },
    });
  }

  scanPortals(): void {
    this.scanning.set(true);
    this.scanSummary.set('');
    this.scanErrors.set([]);

    const body: ScanPortalsRequest = {};
    if (this.selectedCategories().length > 0) {
      body.categories = this.selectedCategories();
    }
    if (this.selectedCompanies().length > 0) {
      body.companies = this.selectedCompanies();
    }
    const kw = this.scanKeyword().trim();
    if (kw) {
      body.keyword = kw;
    }

    this.http.post<ScanResult>(`${environment.apiUrl}/ingestion/scan-portals`, body).subscribe({
      next: (res) => {
        // Merge new jobs (deduplicate by id)
        const existing = this.jobs();
        const existingIds = new Set(existing.map((j) => j.id));
        const merged = [...existing, ...res.jobs.filter((j) => !existingIds.has(j.id))];
        this.jobs.set(merged);
        this.scanSummary.set(
          `Scan complete: ${res.total_fetched} fetched, ${res.new} new, ${res.duplicates} duplicates.`,
        );
        this.scanErrors.set(res.errors);
        this.scanning.set(false);
      },
      error: (err) => {
        this.scanSummary.set(err.error?.detail || 'Scan failed.');
        this.scanning.set(false);
      },
    });
  }

  toggleFilters(): void {
    this.showFilters.update((v) => !v);
  }

  onCategoryChange(event: Event): void {
    const select = event.target as HTMLSelectElement;
    const selected = Array.from(select.selectedOptions).map((o) => o.value);
    this.selectedCategories.set(selected);
  }

  onCompanyChange(event: Event): void {
    const select = event.target as HTMLSelectElement;
    const selected = Array.from(select.selectedOptions).map((o) => o.value);
    this.selectedCompanies.set(selected);
  }

  onKeywordInput(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.scanKeyword.set(input.value);
  }

  trackJob(jobId: string): void {
    const body: CreateApplicationRequest = { job_id: jobId };
    this.http.post(`${environment.apiUrl}/tracking`, body).subscribe({
      next: () => {
        this.trackedJobIds.update((ids) => new Set([...ids, jobId]));
      },
      error: (err) => {
        if (err.status === 409) {
          this.trackedJobIds.update((ids) => new Set([...ids, jobId]));
        }
      },
    });
  }

  isTracked(jobId: string): boolean {
    return this.trackedJobIds().has(jobId);
  }
}
