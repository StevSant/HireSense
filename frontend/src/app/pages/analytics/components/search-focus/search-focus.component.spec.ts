import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { SearchFocusComponent } from './search-focus.component';
import { SearchFocus } from '../../models/search-focus.model';

function focus(over: Partial<SearchFocus> = {}): SearchFocus {
  return {
    insufficient_data: false,
    match_count: 6,
    best_fit_companies: [{ label: 'Acme', count: 3, avg_score: 0.8 }],
    best_fit_roles: [{ label: 'Backend Engineer', count: 4, avg_score: 0.7 }],
    remote_share: 0.5,
    top_locations: [{ label: 'Remote', count: 3, avg_score: 0.7 }],
    fresh_fit_count: 4,
    fresh_days: 7,
    ...over,
  };
}

describe('SearchFocusComponent', () => {
  function mount(f: SearchFocus) {
    TestBed.configureTestingModule({
      imports: [SearchFocusComponent],
      providers: [provideRouter([])],
    });
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

  it('synthesises a top role/company insight', () => {
    const fixture = mount(focus());
    const insight = fixture.nativeElement.querySelector('.focus-insight');
    expect(insight).not.toBeNull();
    expect(insight.textContent).toContain('Backend Engineer');
    expect(insight.textContent).toContain('Acme');
  });

  it('links companies to their page and roles to filtered ingestion', () => {
    const fixture = mount(focus());
    const hrefs = Array.from(
      fixture.nativeElement.querySelectorAll('a') as NodeListOf<HTMLAnchorElement>,
    ).map((a) => a.getAttribute('href'));
    expect(hrefs).toContain('/dashboard/company/Acme');
    expect(
      hrefs.some((h) => h?.startsWith('/dashboard/ingestion') && h.includes('keyword=Backend')),
    ).toBe(true);
  });
});
