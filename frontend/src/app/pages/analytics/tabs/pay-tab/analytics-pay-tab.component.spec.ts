import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { AnalyticsPayTabComponent } from './analytics-pay-tab.component';
import { AnalyticsStore } from '../../analytics.store';
import { AnalyticsService } from '../../../../core/services/analytics.service';
import { PortfolioService } from '../../../../core/services/portfolio.service';
import { makeAnalyticsService, makePortfolioService } from '../../testing/analytics-fakes';

describe('AnalyticsPayTabComponent', () => {
  function mount(
    analyticsService: unknown = makeAnalyticsService(),
    portfolioService: unknown = makePortfolioService(),
  ) {
    TestBed.configureTestingModule({
      imports: [AnalyticsPayTabComponent],
      providers: [
        provideRouter([]),
        AnalyticsStore,
        { provide: AnalyticsService, useValue: analyticsService },
        { provide: PortfolioService, useValue: portfolioService },
      ],
    });
    const fixture = TestBed.createComponent(AnalyticsPayTabComponent);
    fixture.detectChanges();
    return fixture;
  }

  it('renders the comp benchmark and the market salary band', () => {
    const fixture = mount();
    const text = fixture.nativeElement.textContent;
    expect(text).toContain('Pay');
    expect(text).toContain('Market salary range');
    // Median from the market fixture, now surfaced on Pay rather than buried
    // in the old <details> "Market context" block.
    expect(text).toContain('110,000');
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
              unparsed_count: 0,
              other_currency_count: 0,
              disclosed_pct: 80,
              inferred_count: 3,
            },
          }),
      }),
    );
    expect(fixture.nativeElement.querySelector('.salary-basis-note')).not.toBeNull();
  });

  it('hides the salary-basis footnote when no salaries were inferred', () => {
    const fixture = mount();
    expect(fixture.nativeElement.querySelector('.salary-basis-note')).toBeNull();
  });

  it('surfaces a section error when the market endpoint fails', () => {
    const fixture = mount(makeAnalyticsService({ market: () => throwError(() => new Error('x')) }));
    expect(fixture.nativeElement.querySelector('.section-error')).not.toBeNull();
  });
});
