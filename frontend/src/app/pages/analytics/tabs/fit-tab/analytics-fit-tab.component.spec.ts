import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';
import { AnalyticsFitTabComponent } from './analytics-fit-tab.component';
import { AnalyticsStore } from '../../analytics.store';
import { AnalyticsService } from '../../../../core/services/analytics.service';
import { PortfolioService } from '../../../../core/services/portfolio.service';
import { makeAnalyticsService, makePortfolioService } from '../../testing/analytics-fakes';

describe('AnalyticsFitTabComponent', () => {
  function mount(
    analyticsService: unknown = makeAnalyticsService(),
    portfolioService: unknown = makePortfolioService(),
  ) {
    TestBed.configureTestingModule({
      imports: [AnalyticsFitTabComponent],
      providers: [
        provideRouter([]),
        AnalyticsStore,
        { provide: AnalyticsService, useValue: analyticsService },
        { provide: PortfolioService, useValue: portfolioService },
      ],
    });
    const fixture = TestBed.createComponent(AnalyticsFitTabComponent);
    fixture.detectChanges();
    return fixture;
  }

  it('renders the search focus and the skill gap side by side', () => {
    const fixture = mount();
    const text = fixture.nativeElement.textContent;
    expect(text).toContain('Focus');
    expect(text).toContain('Skill gap');
    expect(text).toContain('rust');
  });

  it('prompts for a CV when the profile is missing', () => {
    const fixture = mount(
      makeAnalyticsService({ skillGap: () => of({ has_profile: false, missing: [] }) }),
    );
    expect(fixture.nativeElement.textContent).toContain('Upload a CV');
  });
});
