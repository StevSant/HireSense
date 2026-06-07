import { Component, OnInit, input, output } from '@angular/core';
import { JobFilters } from '../../models/job-filters.model';
import { SeniorityLevel } from '../../models/seniority-level.model';
import { detectUserLocation } from '../../../../core/utils/detect-user-location';

const LS_USER_LOCATION = 'hiresense.user_location';
const LS_STRICT_LOCATION = 'hiresense.strict_location_match';

@Component({
  selector: 'app-job-filters',
  standalone: true,
  imports: [],
  templateUrl: './job-filters.component.html',
  styleUrl: './job-filters.component.scss',
})
export class JobFiltersComponent implements OnInit {
  sources = input.required<string[]>();
  filters = input.required<JobFilters>();

  filtersChange = output<JobFilters>();

  private debounceTimer: ReturnType<typeof setTimeout> | null = null;

  ngOnInit(): void {
    let storedLocation = localStorage.getItem(LS_USER_LOCATION);
    if (!storedLocation) {
      const detected = detectUserLocation();
      if (detected) {
        storedLocation = detected;
        localStorage.setItem(LS_USER_LOCATION, detected);
      }
    }
    const storedStrict = localStorage.getItem(LS_STRICT_LOCATION) === 'true';
    if (storedLocation || storedStrict) {
      this.emitFilters({
        user_location: storedLocation || undefined,
        strict_location: storedStrict || undefined,
      });
    }
  }

  useDetectedLocation(): void {
    const detected = detectUserLocation();
    if (!detected) return;
    localStorage.setItem(LS_USER_LOCATION, detected);
    this.emitFilters({ user_location: detected });
  }

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

  onUserLocationInput(event: Event): void {
    const value = (event.target as HTMLInputElement).value.trim();
    if (value) {
      localStorage.setItem(LS_USER_LOCATION, value);
    } else {
      localStorage.removeItem(LS_USER_LOCATION);
    }
    this.debounceEmit({ user_location: value || undefined });
  }

  onStrictLocationChange(event: Event): void {
    const checked = (event.target as HTMLInputElement).checked;
    localStorage.setItem(LS_STRICT_LOCATION, checked ? 'true' : 'false');
    this.emitFilters({ strict_location: checked || undefined });
  }

  onSeniorityToggle(level: SeniorityLevel, event: Event): void {
    const checked = (event.target as HTMLInputElement).checked;
    const current = new Set(this.filters().seniority ?? []);
    if (checked) {
      current.add(level);
    } else {
      current.delete(level);
    }
    const next = current.size ? Array.from(current) : undefined;
    this.emitFilters({ seniority: next });
  }

  onMaxYearsInput(event: Event): void {
    const value = (event.target as HTMLInputElement).value.trim();
    if (!value) {
      this.emitFilters({ max_years_experience: undefined });
      return;
    }
    const parsed = Number.parseInt(value, 10);
    if (Number.isFinite(parsed) && parsed >= 0) {
      this.emitFilters({ max_years_experience: parsed });
    }
  }

  isSenioritySelected(level: SeniorityLevel): boolean {
    return (this.filters().seniority ?? []).includes(level);
  }

  clearAll(): void {
    const userLocation = localStorage.getItem(LS_USER_LOCATION) ?? '';
    const strict = localStorage.getItem(LS_STRICT_LOCATION) === 'true';
    this.filtersChange.emit({
      user_location: userLocation || undefined,
      strict_location: strict || undefined,
    });
  }

  private emitFilters(partial: Partial<JobFilters>): void {
    this.filtersChange.emit({ ...this.filters(), ...partial });
  }

  private debounceEmit(partial: Partial<JobFilters>): void {
    if (this.debounceTimer) clearTimeout(this.debounceTimer);
    this.debounceTimer = setTimeout(() => this.emitFilters(partial), 300);
  }
}
