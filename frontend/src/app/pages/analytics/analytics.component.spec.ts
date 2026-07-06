import { TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';
import { AnalyticsComponent } from './analytics.component';
import { AnalyticsService } from '../../core/services/analytics.service';
import { PortfolioService } from '../../core/services/portfolio.service';
import { PortfolioEngagementResponse } from '../profile/models/portfolio-engagement.model';

function makeAnalyticsService(over: Partial<Record<string, unknown>> = {}) {
  return {
    funnel: () =>
      of({ stages: [], rejected: 0, current_rejected: 0, total_applications: 0, by_source: [] }),
    market: () =>
      of({
        top_skills: [{ skill: 'python', count: 3, pct: 75 }],
        remote_mix: { remote: 2 },
        posting_trend: [],
        salary_distribution: {
          currency: 'USD',
          min_annual: 90000,
          median_annual: 110000,
          max_annual: 130000,
          parsed_count: 5,
          unparsed_count: 1,
          other_currency_count: 0,
          disclosed_pct: 80,
          inferred_count: 0,
        },
      }),
    skillGap: () => of({ has_profile: true, missing: [{ skill: 'rust', count: 2, pct: 40 }] }),
    targetSalary: () =>
      of({
        insufficient_data: true,
        currency: null,
        p25_annual: null,
        median_annual: null,
        p75_annual: null,
        sample_size: 0,
      }),
    comp: () =>
      of({
        insufficient_data: true,
        currency: null,
        p25_annual: null,
        median_annual: null,
        p75_annual: null,
        sample_size: 0,
        by_seniority: [],
        your_median_annual: null,
        your_sample_size: 0,
        ask_min_annual: null,
        ask_max_annual: null,
      }),
    focus: () =>
      of({
        insufficient_data: true,
        match_count: 0,
        best_fit_companies: [],
        best_fit_roles: [],
        remote_share: null,
        top_locations: [],
        fresh_fit_count: 0,
      }),
    ...over,
  };
}

function makePortfolioService(
  engagement: () => unknown = () =>
    of({ configured: false, visits: [] } as PortfolioEngagementResponse),
) {
  return { engagement, listProjects: () => of(null), sync: () => of(null) };
}

describe('AnalyticsComponent', () => {
  function mount(
    analyticsService: unknown = makeAnalyticsService(),
    portfolioService: unknown = makePortfolioService(),
  ) {
    TestBed.configureTestingModule({
      imports: [AnalyticsComponent],
      providers: [
        { provide: AnalyticsService, useValue: analyticsService },
        { provide: PortfolioService, useValue: portfolioService },
      ],
    });
    const fixture = TestBed.createComponent(AnalyticsComponent);
    fixture.detectChanges();
    return fixture;
  }

  it('renders the KPI strip and the section cards on success', () => {
    const fixture = mount();
    expect(fixture.nativeElement.querySelector('app-kpi-strip')).not.toBeNull();
    // 3 main sections (Pay, Focus, Performance) + 2 in the Market-context footer.
    expect(fixture.nativeElement.querySelectorAll('.analytics-card').length).toBe(5);
  });

  it('renders a top skill from market (in the context section)', () => {
    const fixture = mount();
    expect(fixture.nativeElement.textContent).toContain('python');
  });

  it('shows a section error when an endpoint fails', () => {
    const fixture = mount(
      makeAnalyticsService({ funnel: () => throwError(() => new Error('boom')) }),
    );
    expect(fixture.nativeElement.querySelector('.section-error')).not.toBeNull();
  });

  it('renders the portfolio engagement card with visit rows when configured and visits present', () => {
    const visit = {
      ref: 'ref-1',
      application_id: 'app-1',
      first_seen: '2026-06-01T00:00:00Z',
      last_seen: '2026-06-09T00:00:00Z',
      page_views: 5,
      cv_downloads: 2,
      country: 'US',
      organization: 'Acme Corp',
    };
    const portfolioSvc = makePortfolioService(() =>
      of({ configured: true, visits: [visit] } as PortfolioEngagementResponse),
    );
    const fixture = mount(makeAnalyticsService(), portfolioSvc);
    fixture.detectChanges();
    const rows = fixture.nativeElement.querySelectorAll('.engagement-row');
    expect(rows.length).toBe(1);
    expect(fixture.nativeElement.textContent).toContain('5 views');
    expect(fixture.nativeElement.textContent).toContain('Acme Corp');
  });

  it('toggling to monthly re-labels the target-median KPI', () => {
    const fixture = mount(
      makeAnalyticsService({
        comp: () =>
          of({
            insufficient_data: false,
            currency: 'USD',
            p25_annual: 28000,
            median_annual: 31200,
            p75_annual: 34000,
            sample_size: 12,
            by_seniority: [],
            your_median_annual: null,
            your_sample_size: 0,
            ask_min_annual: null,
            ask_max_annual: null,
          }),
      }),
    );
    const component = fixture.componentInstance;
    component.setPayPeriod('monthly');
    fixture.detectChanges();
    const median = component.kpis().find((k) => k.label === 'Target median');
    expect(median?.value).toContain('2,600');
  });

  it('shows the salary-basis footnote when the market has inferred-period salaries', () => {
    const fixture = mount(
      makeAnalyticsService({
        market: () =>
          of({
            top_skills: [],
            remote_mix: {},
            posting_trend: [],
            salary_distribution: {
              currency: 'USD',
              min_annual: 90000,
              median_annual: 110000,
              max_annual: 130000,
              parsed_count: 5,
              unparsed_count: 1,
              other_currency_count: 0,
              disclosed_pct: 80,
              inferred_count: 3,
            },
          }),
      }),
    );
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.salary-basis-note')).not.toBeNull();
  });

  it('hides the salary-basis footnote when no salaries were inferred', () => {
    const fixture = mount();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.salary-basis-note')).toBeNull();
  });

  it('hides the portfolio engagement card when configured is false', () => {
    const portfolioSvc = makePortfolioService(() =>
      of({
        configured: false,
        visits: [
          {
            ref: 'ref-1',
            application_id: 'app-1',
            first_seen: '2026-06-01T00:00:00Z',
            last_seen: '2026-06-09T00:00:00Z',
            page_views: 1,
            cv_downloads: 0,
            country: null,
            organization: null,
          },
        ],
      } as PortfolioEngagementResponse),
    );
    const fixture = mount(makeAnalyticsService(), portfolioSvc);
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.engagement-row')).toBeNull();
  });
});
