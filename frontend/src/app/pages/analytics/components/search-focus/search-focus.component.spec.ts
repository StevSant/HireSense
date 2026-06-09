import { TestBed } from '@angular/core/testing';
import { SearchFocusComponent } from './search-focus.component';
import { SearchFocus } from '../../models/search-focus.model';

function focus(over: Partial<SearchFocus> = {}): SearchFocus {
  return {
    insufficient_data: false, match_count: 6,
    best_fit_companies: [{ label: 'Acme', count: 3, avg_score: 0.8 }],
    best_fit_roles: [{ label: 'Backend Engineer', count: 4, avg_score: 0.7 }],
    remote_share: 0.5, top_locations: [{ label: 'Remote', count: 3, avg_score: 0.7 }],
    fresh_fit_count: 4, ...over,
  };
}

describe('SearchFocusComponent', () => {
  function mount(f: SearchFocus) {
    TestBed.configureTestingModule({ imports: [SearchFocusComponent] });
    const fixture = TestBed.createComponent(SearchFocusComponent);
    fixture.componentRef.setInput('focus', f);
    fixture.detectChanges();
    return fixture;
  }

  it('shows insufficient-data message', () => {
    const fixture = mount(focus({ insufficient_data: true }));
    expect(fixture.nativeElement.querySelector('.focus-empty')).not.toBeNull();
  });

  it('renders companies, roles and remote share', () => {
    const fixture = mount(focus());
    expect(fixture.nativeElement.textContent).toContain('Acme');
    expect(fixture.nativeElement.textContent).toContain('Backend Engineer');
    expect(fixture.componentInstance.remotePct()).toBe(50);
  });
});
