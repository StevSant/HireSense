import { Component, input, output } from '@angular/core';
import { JobFilters } from '../../../../core/services/ingestion.service';

@Component({
  selector: 'app-job-filters',
  standalone: true,
  imports: [],
  templateUrl: './job-filters.component.html',
  styleUrl: './job-filters.component.scss',
})
export class JobFiltersComponent {
  sources = input.required<string[]>();
  filters = input.required<JobFilters>();

  filtersChange = output<JobFilters>();

  private debounceTimer: ReturnType<typeof setTimeout> | null = null;

  onSourceChange(event: Event): void {
    const select = event.target as HTMLSelectElement;
    const value = select.value;
    this.emitFilters({ source: value || undefined });
  }

  onKeywordInput(event: Event): void {
    const value = (event.target as HTMLInputElement).value.trim();
    this.debounceEmit({ keyword: value || undefined });
  }

  onLocationInput(event: Event): void {
    const value = (event.target as HTMLInputElement).value.trim();
    this.debounceEmit({ location: value || undefined });
  }

  onSkillsInput(event: Event): void {
    const value = (event.target as HTMLInputElement).value.trim();
    this.debounceEmit({ skills: value || undefined });
  }

  onDateFromChange(event: Event): void {
    const value = (event.target as HTMLInputElement).value;
    this.emitFilters({ date_from: value || undefined });
  }

  onDateToChange(event: Event): void {
    const value = (event.target as HTMLInputElement).value;
    this.emitFilters({ date_to: value || undefined });
  }

  clearAll(): void {
    this.filtersChange.emit({});
  }

  private emitFilters(partial: Partial<JobFilters>): void {
    this.filtersChange.emit({ ...this.filters(), ...partial });
  }

  private debounceEmit(partial: Partial<JobFilters>): void {
    if (this.debounceTimer) clearTimeout(this.debounceTimer);
    this.debounceTimer = setTimeout(() => this.emitFilters(partial), 300);
  }
}
