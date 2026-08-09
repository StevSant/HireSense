import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';
import { AnalyticsPortfolioTabComponent } from './analytics-portfolio-tab.component';
import { AnalyticsStore } from '../../analytics.store';
import { AnalyticsService } from '../../../../core/services/analytics.service';
import { PortfolioService } from '../../../../core/services/portfolio.service';
import { makeAnalyticsService, makePortfolioService } from '../../testing/analytics-fakes';

describe('AnalyticsPortfolioTabComponent', () => {
  function mount(
    analyticsService: unknown = makeAnalyticsService(),
    portfolioService: unknown = makePortfolioService(),
  ) {
    TestBed.configureTestingModule({
      imports: [AnalyticsPortfolioTabComponent],
      providers: [
        provideRouter([]),
        AnalyticsStore,
        { provide: AnalyticsService, useValue: analyticsService },
        { provide: PortfolioService, useValue: portfolioService },
      ],
    });
    const fixture = TestBed.createComponent(AnalyticsPortfolioTabComponent);
    fixture.detectChanges();
    return fixture;
  }

  const VISITS = {
    configured: true,
    visits: [
      {
        ref: 'r1',
        application_id: null,
        page_views: 4,
        cv_downloads: 1,
        last_seen: '2026-06-01T00:00:00Z',
        organization: 'Acme',
        country: null,
      },
    ],
  };

  it('renders a row per visit when configured', () => {
    const fixture = mount(
      makeAnalyticsService(),
      makePortfolioService(() => of(VISITS)),
    );
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelectorAll('.engagement-row').length).toBe(1);
    expect(el.textContent).toContain('4 views');
  });

  // The tab is part of the static hub bar, so it always renders; when portfolio
  // tracking is off it explains itself instead of showing an empty card.
  it('explains itself instead of rendering rows when tracking is unconfigured', () => {
    const fixture = mount();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelectorAll('.engagement-row').length).toBe(0);
    expect(el.textContent).toContain("isn't configured");
  });
});
