import { TestBed } from '@angular/core/testing';
import { FunnelChartComponent } from './funnel-chart.component';

const METRICS = {
  stages: [
    { stage: 'saved', reached: 4, conversion_from_prev: null, median_days_in_stage: 2, current: 1 },
    {
      stage: 'applied',
      reached: 3,
      conversion_from_prev: 0.75,
      median_days_in_stage: 5,
      current: 1,
    },
    {
      stage: 'interviewing',
      reached: 1,
      conversion_from_prev: 0.33,
      median_days_in_stage: null,
      current: 1,
    },
    {
      stage: 'offered',
      reached: 0,
      conversion_from_prev: 0,
      median_days_in_stage: null,
      current: 0,
    },
    {
      stage: 'accepted',
      reached: 0,
      conversion_from_prev: null,
      median_days_in_stage: null,
      current: 0,
    },
  ],
  rejected: 1,
  current_rejected: 1,
  total_applications: 4,
};

describe('FunnelChartComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [FunnelChartComponent] }).compileComponents();
  });

  function mount(metrics: unknown) {
    const fixture = TestBed.createComponent(FunnelChartComponent);
    fixture.componentRef.setInput('metrics', metrics);
    fixture.detectChanges();
    return fixture;
  }

  it('renders a row per stage', () => {
    const fixture = mount(METRICS);
    expect(fixture.nativeElement.querySelectorAll('.funnel-stage').length).toBe(5);
  });

  it('shows conversion % where present', () => {
    const fixture = mount(METRICS);
    expect(fixture.nativeElement.textContent).toContain('75%');
  });

  it('shows rejected count', () => {
    const fixture = mount(METRICS);
    expect(fixture.nativeElement.textContent).toContain('1');
  });

  it('empty state when no applications', () => {
    const fixture = mount({ stages: [], rejected: 0, current_rejected: 0, total_applications: 0 });
    expect(fixture.nativeElement.querySelector('.funnel-empty')).not.toBeNull();
  });

  it('names the steepest drop-off as an insight', () => {
    const fixture = mount(METRICS);
    const insight = fixture.nativeElement.querySelector('.funnel-insight');
    expect(insight).not.toBeNull();
    // Interviewing → Offered has the lowest conversion (0), so it is the drop-off.
    expect(insight.textContent).toContain('Interviewing → Offered');
  });
});
