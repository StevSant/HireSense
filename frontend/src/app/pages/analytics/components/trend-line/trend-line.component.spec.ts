import { TestBed } from '@angular/core/testing';
import { TrendLineComponent } from './trend-line.component';

describe('TrendLineComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [TrendLineComponent] }).compileComponents();
  });

  function mount(points: unknown[]) {
    const fixture = TestBed.createComponent(TrendLineComponent);
    fixture.componentRef.setInput('points', points);
    fixture.detectChanges();
    return fixture;
  }

  it('renders a polyline when 2+ points', () => {
    const fixture = mount([
      { week: '2026-W18', count: 2 },
      { week: '2026-W19', count: 5 },
    ]);
    expect(fixture.nativeElement.querySelector('polyline')).not.toBeNull();
  });

  it('shows empty state with no points', () => {
    const fixture = mount([]);
    expect(fixture.nativeElement.querySelector('.trend-empty')).not.toBeNull();
  });
});
