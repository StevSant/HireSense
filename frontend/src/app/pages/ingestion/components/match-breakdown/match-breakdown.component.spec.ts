import { TestBed } from '@angular/core/testing';
import { MatchBreakdownComponent } from './match-breakdown.component';
import { AnalysisDimension } from '../../models/analysis-dimension.model';

const DIMS: AnalysisDimension[] = [
  { dimension: 'skills_role_fit', score: 0.9, rationale: 'Strong overlap on core stack.' },
  { dimension: 'seniority', score: 0.6, rationale: '' },
];

describe('MatchBreakdownComponent', () => {
  function mount(dimensions: AnalysisDimension[]) {
    TestBed.configureTestingModule({ imports: [MatchBreakdownComponent] });
    const fixture = TestBed.createComponent(MatchBreakdownComponent);
    fixture.componentRef.setInput('dimensions', dimensions);
    fixture.detectChanges();
    return fixture;
  }

  it('renders one row per dimension with a humanized label and score', () => {
    const fixture = mount(DIMS);
    expect(fixture.nativeElement.querySelectorAll('.mb-row').length).toBe(2);
    expect(fixture.nativeElement.querySelector('.mb-name').textContent.trim()).toBe(
      'Skills role fit',
    );
    expect(fixture.nativeElement.textContent).toContain('90%');
  });

  it('only makes rows with a rationale expandable', () => {
    const fixture = mount(DIMS);
    // First dim has a rationale → <details>; second is empty → plain div.
    expect(fixture.nativeElement.querySelectorAll('details.mb-row').length).toBe(1);
    expect(fixture.nativeElement.querySelector('.mb-rationale').textContent.trim()).toBe(
      'Strong overlap on core stack.',
    );
  });

  it('barWidth clamps the score into a 0-100% range', () => {
    const c = mount(DIMS).componentInstance;
    expect(c.barWidth(0.5)).toBe('50%');
    expect(c.barWidth(-1)).toBe('0%');
    expect(c.barWidth(5)).toBe('100%');
  });

  it('humanize replaces underscores and capitalizes', () => {
    expect(mount(DIMS).componentInstance.humanize('skills_role_fit')).toBe('Skills role fit');
  });
});
