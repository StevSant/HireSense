import { TestBed } from '@angular/core/testing';
import { JobFiltersComponent } from './job-filters.component';
import { JobFilters } from '@core/contracts/job-filters.model';

describe('JobFiltersComponent', () => {
  beforeEach(async () => {
    localStorage.clear();
    // detectUserLocation() resolves the host's IANA timezone via Intl, which
    // varies by machine/CI runner. Pin it to an unmapped zone (see
    // timezone-country-map.ts) so detection deterministically yields null —
    // the Angular vitest setup disallows vi.mock on relative imports, so
    // stubbing the global Intl API is the supported way to control this.
    vi.spyOn(Intl, 'DateTimeFormat').mockImplementation(
      () => ({ resolvedOptions: () => ({ timeZone: 'UTC' }) }) as unknown as Intl.DateTimeFormat,
    );
    await TestBed.configureTestingModule({
      imports: [JobFiltersComponent],
    }).compileComponents();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  function mount(filters: JobFilters = {}, sources: string[] = ['remotive', 'jobicy']) {
    const fixture = TestBed.createComponent(JobFiltersComponent);
    fixture.componentRef.setInput('sources', sources);
    fixture.componentRef.setInput('filters', filters);
    fixture.detectChanges();
    return fixture;
  }

  it('emits its initial (empty) filter state exactly once when nothing is stored', () => {
    const fixture = TestBed.createComponent(JobFiltersComponent);
    fixture.componentRef.setInput('sources', ['remotive']);
    fixture.componentRef.setInput('filters', {});
    const emitted: JobFilters[] = [];
    fixture.componentInstance.filtersChange.subscribe((f) => emitted.push(f));

    fixture.detectChanges(); // triggers ngOnInit

    expect(emitted).toEqual([{ user_location: undefined, strict_location: undefined }]);
  });

  it('emits its initial state exactly once with the restored location when one is stored', () => {
    localStorage.setItem('hiresense.user_location', 'Chile');
    localStorage.setItem('hiresense.strict_location_match', 'true');
    const fixture = TestBed.createComponent(JobFiltersComponent);
    fixture.componentRef.setInput('sources', ['remotive']);
    fixture.componentRef.setInput('filters', {});
    const emitted: JobFilters[] = [];
    fixture.componentInstance.filtersChange.subscribe((f) => emitted.push(f));

    fixture.detectChanges(); // triggers ngOnInit

    expect(emitted).toEqual([{ user_location: 'Chile', strict_location: true }]);
  });

  // The source picker is a filtering combobox (app-combobox), not a native
  // select — the list grows with every adapter and ATS portal ingested.
  function openSourceCombobox(fixture: ReturnType<typeof mount>) {
    const input = fixture.nativeElement.querySelector(
      'app-combobox input.combobox-input',
    ) as HTMLInputElement;
    input.dispatchEvent(new Event('focus'));
    fixture.detectChanges();
    return input;
  }

  function sourceOptionEls(fixture: ReturnType<typeof mount>): HTMLElement[] {
    return [...fixture.nativeElement.querySelectorAll('app-combobox .combobox-option')];
  }

  it('renders an option per source plus the "All sources" default', () => {
    const fixture = mount({}, ['remotive', 'jobicy']);
    openSourceCombobox(fixture);
    const options = sourceOptionEls(fixture);
    expect(options.length).toBe(3);
    expect(options[0].textContent?.trim()).toBe('All sources');
  });

  it('emits the source filter on select change', () => {
    const fixture = mount();
    let emitted: JobFilters | null = null;
    fixture.componentInstance.filtersChange.subscribe((f) => (emitted = f));

    openSourceCombobox(fixture);
    sourceOptionEls(fixture)
      .find((o) => o.textContent?.trim() === 'remotive')!
      .click();

    expect(emitted).toEqual({ source: 'remotive' });
  });

  it('merges new partial values onto the existing filters', () => {
    const fixture = mount({ keyword: 'python', source: 'jobicy' });
    let emitted: JobFilters | null = null;
    fixture.componentInstance.filtersChange.subscribe((f) => (emitted = f));

    openSourceCombobox(fixture);
    sourceOptionEls(fixture)
      .find((o) => o.textContent?.trim() === 'remotive')!
      .click();

    expect(emitted).toEqual({ keyword: 'python', source: 'remotive' });
  });

  it('clears the source filter when "All sources" is chosen', () => {
    const fixture = mount({ source: 'remotive' });
    let emitted: JobFilters | null = null;
    fixture.componentInstance.filtersChange.subscribe((f) => (emitted = f));

    openSourceCombobox(fixture);
    sourceOptionEls(fixture)
      .find((o) => o.textContent?.trim() === 'All sources')!
      .click();

    expect(emitted).toEqual({ source: undefined });
  });

  it('debounces keyword input and emits the trimmed value', () => {
    vi.useFakeTimers();
    try {
      const fixture = mount();
      let emitted: JobFilters | null = null;
      fixture.componentInstance.filtersChange.subscribe((f) => (emitted = f));

      const input = fixture.nativeElement.querySelector(
        'input.filter-control[type="text"]',
      ) as HTMLInputElement;
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
