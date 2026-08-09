import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';
import { AnalyticsComponent } from './analytics.component';
import { AnalyticsStore } from './analytics.store';
import { AnalyticsService } from '../../core/services/analytics.service';
import { PortfolioService } from '../../core/services/portfolio.service';
import { makeAnalyticsService, makePortfolioService } from './testing/analytics-fakes';

/**
 * The shell owns the KPI strip and the eager comp/funnel/focus fetches; the
 * cards themselves are routed tabs with their own specs.
 */
describe('AnalyticsComponent (shell)', () => {
  function mount(
    analyticsService: unknown = makeAnalyticsService(),
    portfolioService: unknown = makePortfolioService(),
  ) {
    TestBed.configureTestingModule({
      imports: [AnalyticsComponent],
      providers: [
        provideRouter([]),
        AnalyticsStore,
        { provide: AnalyticsService, useValue: analyticsService },
        { provide: PortfolioService, useValue: portfolioService },
      ],
    });
    const fixture = TestBed.createComponent(AnalyticsComponent);
    fixture.detectChanges();
    return fixture;
  }

  it('renders the KPI strip above a routed tab outlet', () => {
    const fixture = mount();
    expect(fixture.nativeElement.querySelector('app-kpi-strip')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('router-outlet')).not.toBeNull();
  });

  it('fetches comp, funnel and focus eagerly because the KPI tiles need them', () => {
    const comp = vi.fn(makeAnalyticsService().comp);
    const funnel = vi.fn(makeAnalyticsService().funnel);
    const focus = vi.fn(makeAnalyticsService().focus);
    const market = vi.fn(makeAnalyticsService().market);
    mount(makeAnalyticsService({ comp, funnel, focus, market }));

    expect(comp).toHaveBeenCalled();
    expect(funnel).toHaveBeenCalled();
    expect(focus).toHaveBeenCalled();
    // Deferred to the tab that needs it.
    expect(market).not.toHaveBeenCalled();
  });

  it('degrades every KPI tile to an em dash when the data is insufficient', () => {
    const fixture = mount();
    const values = fixture.componentInstance.kpis().map((t) => t.value);
    expect(values).toEqual(['—', '—', '—', '—']);
  });

  it('toggling to monthly re-labels the target-median KPI', () => {
    const fixture = mount(
      makeAnalyticsService({
        comp: () =>
          of({
            insufficient_data: false,
            currency: 'USD',
            p25_annual: 90000,
            median_annual: 120000,
            p75_annual: 130000,
            sample_size: 12,
            by_seniority: [],
            your_median_annual: null,
            your_sample_size: 0,
            ask_min_annual: null,
            ask_max_annual: null,
          }),
      }),
    );
    const store = TestBed.inject(AnalyticsStore);

    expect(fixture.componentInstance.kpis()[0].value).toContain('120,000');

    store.setPayPeriod('monthly');
    fixture.detectChanges();

    expect(fixture.componentInstance.kpis()[0].value).toContain('10,000');
  });
});
