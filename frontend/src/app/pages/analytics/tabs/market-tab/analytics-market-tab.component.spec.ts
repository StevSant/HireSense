import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { throwError } from 'rxjs';
import { AnalyticsMarketTabComponent } from './analytics-market-tab.component';
import { AnalyticsStore } from '../../analytics.store';
import { AnalyticsService } from '../../../../core/services/analytics.service';
import { PortfolioService } from '../../../../core/services/portfolio.service';
import { makeAnalyticsService, makePortfolioService } from '../../testing/analytics-fakes';

describe('AnalyticsMarketTabComponent', () => {
  function mount(
    analyticsService: unknown = makeAnalyticsService(),
    portfolioService: unknown = makePortfolioService(),
  ) {
    TestBed.configureTestingModule({
      imports: [AnalyticsMarketTabComponent],
      providers: [
        provideRouter([]),
        AnalyticsStore,
        { provide: AnalyticsService, useValue: analyticsService },
        { provide: PortfolioService, useValue: portfolioService },
      ],
    });
    const fixture = TestBed.createComponent(AnalyticsMarketTabComponent);
    fixture.detectChanges();
    return fixture;
  }

  it('renders the top skills, no longer buried in a collapsed details block', () => {
    const fixture = mount();
    expect(fixture.nativeElement.textContent).toContain('python');
    expect(fixture.nativeElement.textContent).toContain('Postings per week');
  });

  it('surfaces a section error when market fails', () => {
    const fixture = mount(makeAnalyticsService({ market: () => throwError(() => new Error('x')) }));
    expect(fixture.nativeElement.querySelector('.section-error')).not.toBeNull();
  });
});
