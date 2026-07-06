import { TestBed } from '@angular/core/testing';
import { SalaryBandComponent } from './salary-band.component';

describe('SalaryBandComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [SalaryBandComponent] }).compileComponents();
  });

  function mount(target: unknown) {
    const fixture = TestBed.createComponent(SalaryBandComponent);
    fixture.componentRef.setInput('target', target);
    fixture.detectChanges();
    return fixture;
  }

  it('shows insufficient-data state', () => {
    const fixture = mount({
      insufficient_data: true,
      currency: null,
      p25_annual: null,
      median_annual: null,
      p75_annual: null,
      sample_size: 0,
    });
    expect(fixture.nativeElement.querySelector('.band-insufficient')).not.toBeNull();
  });

  it('renders the band with median when sufficient', () => {
    const fixture = mount({
      insufficient_data: false,
      currency: 'USD',
      p25_annual: 90000,
      median_annual: 110000,
      p75_annual: 130000,
      sample_size: 12,
    });
    expect(fixture.nativeElement.querySelector('.band-fill')).not.toBeNull();
    expect(fixture.nativeElement.textContent).toContain('110,000');
  });

  it('shows monthly figures when period is monthly', () => {
    const fixture = mount({
      insufficient_data: false,
      currency: 'USD',
      p25_annual: 27600,
      median_annual: 31200,
      p75_annual: 39000,
      sample_size: 21,
    });
    fixture.componentRef.setInput('period', 'monthly');
    fixture.detectChanges();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('2,600'); // 31200 / 12
    expect(text).not.toContain('31,200');
  });
});
