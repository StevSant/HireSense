import { Component, computed, OnInit, signal } from '@angular/core';
import { IngestionService } from '../../core/services/ingestion.service';
import { TrackingService } from '../../core/services/tracking.service';
import { CreateApplicationRequest } from '../../core/models/create-application-request.model';
import { PortalEntry } from './models/portal-entry.model';
import { ScanPortalsRequest } from './models/scan-portals-request.model';
import { ScanError } from './models/scan-result.model';

@Component({
  selector: 'app-ingestion',
  standalone: true,
  imports: [],
  templateUrl: './ingestion.component.html',
  styleUrl: './ingestion.component.scss',
})
export class IngestionComponent implements OnInit {
  /** Read from the singleton service — persists across navigation. */
  jobs = computed(() => this.ingestionService.jobs());
  trackedJobIds = computed(() => this.ingestionService.trackedJobIds());

  loading = signal(false);
  error = signal('');

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

  constructor(
    private ingestionService: IngestionService,
    private trackingService: TrackingService,
  ) {}

  ngOnInit(): void {
    this.loadPortals();
  }

  fetchJobs(): void {
    this.loading.set(true);
    this.error.set('');
    this.ingestionService.fetchJobs().subscribe({
      next: () => {
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(err.error?.detail || 'Failed to fetch jobs');
        this.loading.set(false);
      },
    });
  }

  loadPortals(): void {
    this.ingestionService.loadPortals().subscribe({
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

    this.ingestionService.scanPortals(body).subscribe({
      next: (res) => {
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
    this.trackingService.create(body).subscribe({
      next: () => {
        this.ingestionService.markTracked(jobId);
      },
      error: (err) => {
        if (err.status === 409) {
          this.ingestionService.markTracked(jobId);
        }
      },
    });
  }

  isTracked(jobId: string): boolean {
    return this.trackedJobIds().has(jobId);
  }
}
