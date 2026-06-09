import { TestBed } from '@angular/core/testing';
import { KpiStripComponent } from './kpi-strip.component';

describe('KpiStripComponent', () => {
  it('renders a tile per input with value, label and optional hint', () => {
    TestBed.configureTestingModule({ imports: [KpiStripComponent] });
    const fixture = TestBed.createComponent(KpiStripComponent);
    fixture.componentRef.setInput('tiles', [
      { label: 'Target median', value: 'USD 120,000', hint: 'for your profile' },
      { label: 'Apply → interview', value: '—' },
    ]);
    fixture.detectChanges();
    const tiles = fixture.nativeElement.querySelectorAll('.kpi-tile');
    expect(tiles.length).toBe(2);
    expect(fixture.nativeElement.textContent).toContain('USD 120,000');
    expect(fixture.nativeElement.textContent).toContain('for your profile');
  });
});
