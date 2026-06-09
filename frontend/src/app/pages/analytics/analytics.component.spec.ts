import { TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';
import { AnalyticsComponent } from './analytics.component';
import { AnalyticsService } from '../../core/services/analytics.service';

function makeService(over: Partial<Record<string, unknown>> = {}) {
  return {
    funnel: () => of({ stages: [], rejected: 0, current_rejected: 0, total_applications: 0, by_source: [] }),
    market: () => of({ top_skills: [{ skill: 'python', count: 3, pct: 75 }], remote_mix: { remote: 2 },
      posting_trend: [], salary_distribution: { currency: 'USD', min_annual: 90000, median_annual: 110000,
      max_annual: 130000, parsed_count: 5, unparsed_count: 1, other_currency_count: 0, disclosed_pct: 80 } }),
    skillGap: () => of({ has_profile: true, missing: [{ skill: 'rust', count: 2, pct: 40 }] }),
    targetSalary: () => of({ insufficient_data: true, currency: null, p25_annual: null,
      median_annual: null, p75_annual: null, sample_size: 0 }),
    comp: () => of({ insufficient_data: true, currency: null, p25_annual: null, median_annual: null,
      p75_annual: null, sample_size: 0, by_seniority: [], your_median_annual: null, your_sample_size: 0,
      ask_min_annual: null, ask_max_annual: null }),
    focus: () => of({ insufficient_data: true, match_count: 0, best_fit_companies: [], best_fit_roles: [],
      remote_share: null, top_locations: [], fresh_fit_count: 0 }),
    ...over,
  };
}

describe('AnalyticsComponent', () => {
  function mount(service: unknown) {
    TestBed.configureTestingModule({
      imports: [AnalyticsComponent],
      providers: [{ provide: AnalyticsService, useValue: service }],
    });
    const fixture = TestBed.createComponent(AnalyticsComponent);
    fixture.detectChanges();
    return fixture;
  }

  it('renders the KPI strip and the section cards on success', () => {
    const fixture = mount(makeService());
    expect(fixture.nativeElement.querySelector('app-kpi-strip')).not.toBeNull();
    // 3 main sections (Pay, Focus, Performance) + 2 in the Market-context footer.
    expect(fixture.nativeElement.querySelectorAll('.analytics-card').length).toBe(5);
  });

  it('renders a top skill from market (in the context section)', () => {
    const fixture = mount(makeService());
    expect(fixture.nativeElement.textContent).toContain('python');
  });

  it('shows a section error when an endpoint fails', () => {
    const fixture = mount(makeService({ funnel: () => throwError(() => new Error('boom')) }));
    expect(fixture.nativeElement.querySelector('.section-error')).not.toBeNull();
  });
});
