import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { throwError } from 'rxjs';
import { AnalyticsPipelineTabComponent } from './analytics-pipeline-tab.component';
import { AnalyticsStore } from '../../analytics.store';
import { AnalyticsService } from '../../../../core/services/analytics.service';
import { PortfolioService } from '../../../../core/services/portfolio.service';
import { makeAnalyticsService, makePortfolioService } from '../../testing/analytics-fakes';

describe('AnalyticsPipelineTabComponent', () => {
  function mount(
    analyticsService: unknown = makeAnalyticsService(),
    portfolioService: unknown = makePortfolioService(),
  ) {
    TestBed.configureTestingModule({
      imports: [AnalyticsPipelineTabComponent],
      providers: [
        provideRouter([]),
        AnalyticsStore,
        { provide: AnalyticsService, useValue: analyticsService },
        { provide: PortfolioService, useValue: portfolioService },
      ],
    });
    const fixture = TestBed.createComponent(AnalyticsPipelineTabComponent);
    fixture.detectChanges();
    return fixture;
  }

  it('renders the funnel and the outcomes-by-source heading', () => {
    const fixture = mount();
    const text = fixture.nativeElement.textContent;
    expect(text).toContain('pipeline');
    expect(text).toContain('Outcomes by source');
  });

  it('surfaces a section error when the funnel endpoint fails', () => {
    const fixture = mount(makeAnalyticsService({ funnel: () => throwError(() => new Error('x')) }));
    expect(fixture.nativeElement.querySelector('.section-error')).not.toBeNull();
  });
});
