import { TestBed } from '@angular/core/testing';
import { JobFiltersComponent } from './job-filters.component';
import { JobFilters } from '../../models/job-filters.model';

describe('JobFiltersComponent', () => {
  beforeEach(async () => {
    localStorage.clear();
    await TestBed.configureTestingModule({
      imports: [JobFiltersComponent],
    }).compileComponents();
  });

  function mount(filters: JobFilters = {}, sources: string[] = ['remotive', 'jobicy']) {
    const fixture = TestBed.createComponent(JobFiltersComponent);
    fixture.componentRef.setInput('sources', sources);
    fixture.componentRef.setInput('filters', filters);
    fixture.detectChanges();
    return fixture;
  }

  it('renders an option per source plus the "All sources" default', () => {
    const fixture = mount({}, ['remotive', 'jobicy']);
    const options = fixture.nativeElement.querySelectorAll('select.filter-control option');
    expect(options.length).toBe(3);
    expect((options[0] as HTMLOptionElement).textContent?.trim()).toBe('All sources');
  });

  it('emits the source filter on select change', () => {
    const fixture = mount();
    let emitted: JobFilters | null = null;
    fixture.componentInstance.filtersChange.subscribe((f) => (emitted = f));

    const select = fixture.nativeElement.querySelector('select.filter-control') as HTMLSelectElement;
    select.value = 'remotive';
    select.dispatchEvent(new Event('change'));

    expect(emitted).toEqual({ source: 'remotive' });
  });

  it('merges new partial values onto the existing filters', () => {
    const fixture = mount({ keyword: 'python', source: 'jobicy' });
    let emitted: JobFilters | null = null;
    fixture.componentInstance.filtersChange.subscribe((f) => (emitted = f));

    const select = fixture.nativeElement.querySelector('select.filter-control') as HTMLSelectElement;
    select.value = 'remotive';
    select.dispatchEvent(new Event('change'));

    expect(emitted).toEqual({ keyword: 'python', source: 'remotive' });
  });

  it('clears the source filter when "All sources" is chosen', () => {
    const fixture = mount({ source: 'remotive' });
    let emitted: JobFilters | null = null;
    fixture.componentInstance.filtersChange.subscribe((f) => (emitted = f));

    const select = fixture.nativeElement.querySelector('select.filter-control') as HTMLSelectElement;
    select.value = '';
    select.dispatchEvent(new Event('change'));

    expect(emitted).toEqual({ source: undefined });
  });

  it('debounces keyword input and emits the trimmed value', () => {
    vi.useFakeTimers();
    try {
      const fixture = mount();
      let emitted: JobFilters | null = null;
      fixture.componentInstance.filtersChange.subscribe((f) => (emitted = f));

      const input = fixture.nativeElement.querySelectorAll('input[type="text"]')[0] as HTMLInputElement;
      input.value = '  react  ';
      input.dispatchEvent(new Event('input'));

      // Nothing emitted before the debounce window elapses.
      expect(emitted).toBeNull();
      vi.advanceTimersByTime(300);
      expect(emitted).toEqual({ keyword: 'react' });
    } finally {
      vi.useRealTimers();
    }
  });

  it('toggles a seniority level into the array on check', () => {
    const fixture = mount({ seniority: ['junior'] });
    const emitted: JobFilters[] = [];
    fixture.componentInstance.filtersChange.subscribe((f) => emitted.push(f));

    fixture.componentInstance.onSeniorityToggle('senior', {
      target: { checked: true },
    } as unknown as Event);

    expect(emitted[0].seniority).toEqual(['junior', 'senior']);
  });

  it('removes a seniority level on uncheck and clears the array when empty', () => {
    const fixture = mount({ seniority: ['junior'] });
    const emitted: JobFilters[] = [];
    fixture.componentInstance.filtersChange.subscribe((f) => emitted.push(f));

    fixture.componentInstance.onSeniorityToggle('junior', {
      target: { checked: false },
    } as unknown as Event);

    expect(emitted[0].seniority).toBeUndefined();
  });

  it('emits a parsed max-years value and undefined when blank', () => {
    const fixture = mount();
    const emitted: JobFilters[] = [];
    fixture.componentInstance.filtersChange.subscribe((f) => emitted.push(f));

    fixture.componentInstance.onMaxYearsInput({ target: { value: '3' } } as unknown as Event);
    expect(emitted[0].max_years_experience).toBe(3);

    fixture.componentInstance.onMaxYearsInput({ target: { value: '' } } as unknown as Event);
    expect(emitted[1].max_years_experience).toBeUndefined();
  });

  it('clearAll resets filters but preserves stored location preferences', () => {
    localStorage.setItem('hiresense.user_location', 'Chile');
    localStorage.setItem('hiresense.strict_location_match', 'true');
    const fixture = mount({ keyword: 'python', source: 'remotive' });
    let emitted: JobFilters | null = null;
    fixture.componentInstance.filtersChange.subscribe((f) => (emitted = f));

    fixture.componentInstance.clearAll();

    expect(emitted).toEqual({ user_location: 'Chile', strict_location: true });
  });
});
