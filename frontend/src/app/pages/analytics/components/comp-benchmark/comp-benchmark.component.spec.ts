import { TestBed } from '@angular/core/testing';
import { CompBenchmarkComponent } from './comp-benchmark.component';
import { CompBenchmark } from '../../models/comp-benchmark.model';
import { PayPeriod } from '../../../../core/utils/pay-period';

function comp(over: Partial<CompBenchmark> = {}): CompBenchmark {
  return {
    insufficient_data: false,
    currency: 'USD',
    p25_annual: 90000,
    median_annual: 110000,
    p75_annual: 130000,
    sample_size: 12,
    by_seniority: [],
    your_median_annual: null,
    your_sample_size: 0,
    ask_min_annual: 110000,
    ask_max_annual: 130000,
    ...over,
  };
}

describe('CompBenchmarkComponent', () => {
  function mount(c: CompBenchmark, period?: PayPeriod) {
    TestBed.configureTestingModule({ imports: [CompBenchmarkComponent] });
    const fixture = TestBed.createComponent(CompBenchmarkComponent);
    fixture.componentRef.setInput('comp', c);
    if (period) {
      fixture.componentRef.setInput('period', period);
    }
    fixture.detectChanges();
    return fixture;
  }

  it('shows insufficient-data message', () => {
    const fixture = mount(
      comp({ insufficient_data: true, median_annual: null, ask_min_annual: null }),
    );
    expect(fixture.nativeElement.querySelector('.comp-empty')).not.toBeNull();
  });

  it('shows the suggested ask range', () => {
    const fixture = mount(comp());
    expect(fixture.nativeElement.textContent).toContain('110,000');
    expect(fixture.nativeElement.textContent).toContain('130,000');
  });

  it('flags a below-market pipeline', () => {
    const fixture = mount(comp({ your_median_annual: 90000, your_sample_size: 3 }));
    expect(fixture.componentInstance.pipelineDelta()).toBeLessThan(0);
    expect(fixture.nativeElement.querySelector('.comp-insight.below')).not.toBeNull();
    expect(fixture.nativeElement.textContent).toContain('18% below');
  });

  it('shows monthly ask range and /mo unit when monthly', () => {
    const fixture = mount(comp({ ask_min_annual: 31200, ask_max_annual: 39000 }), 'monthly');
    const text = fixture.nativeElement.textContent;
    expect(text).toContain('2,600'); // 31200 / 12 (ask_min)
    expect(text).toContain('/mo');
  });
});
