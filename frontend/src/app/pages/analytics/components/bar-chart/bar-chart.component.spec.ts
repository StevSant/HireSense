import { TestBed } from '@angular/core/testing';
import { BarChartComponent } from './bar-chart.component';

describe('BarChartComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [BarChartComponent] }).compileComponents();
  });

  function mount(rows: unknown[]) {
    const fixture = TestBed.createComponent(BarChartComponent);
    fixture.componentRef.setInput('rows', rows);
    fixture.detectChanges();
    return fixture;
  }

  it('renders one bar per row', () => {
    const fixture = mount([
      { label: 'python', value: 3, pct: 75 },
      { label: 'react', value: 1, pct: 25 },
    ]);
    expect(fixture.nativeElement.querySelectorAll('.bar-row').length).toBe(2);
  });

  it('sets bar width from pct', () => {
    const fixture = mount([{ label: 'python', value: 3, pct: 50 }]);
    const fill = fixture.nativeElement.querySelector('.bar-fill') as HTMLElement;
    expect(fill.style.width).toBe('50%');
  });

  it('shows empty state when no rows', () => {
    const fixture = mount([]);
    expect(fixture.nativeElement.querySelector('.bar-empty')).not.toBeNull();
  });
});
