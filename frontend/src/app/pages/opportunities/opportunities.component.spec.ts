import { TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';
import { OpportunitiesComponent } from './opportunities.component';
import { OpportunitiesService } from '../../core/services/opportunities.service';
import { PaginatedOpportunitiesResponse } from '@core/contracts/paginated-opportunities-response.model';
import { FetchOpportunitiesResponse } from '@core/contracts/fetch-opportunities-response.model';

function makeOpportunitiesService(overrides: Partial<OpportunitiesService> = {}) {
  const listResponse: PaginatedOpportunitiesResponse = {
    items: [
      {
        id: '1',
        kind: 'conference',
        title: 'Khipu 2027',
        organization: 'Khipu',
        url: 'https://apply.khipu.ai/Khipu2027',
        apply_url: 'https://apply.khipu.ai/Khipu2027',
        description: 'Funded AI meeting.',
        topics: ['ai', 'latam'],
        country: 'Chile',
        city: 'Santiago',
        start_date: '2027-03-01',
        end_date: '2027-03-07',
        cfp_deadline: null,
        application_deadline: '2026-10-31',
        funding: 'Travel and lodging covered',
        source: 'curated',
        source_id: 'khipu-2027',
        status: 'open',
        source_metadata: {},
        relevance_score: 0.5,
      },
    ],
    total: 1,
    page: 1,
    page_size: 20,
  };
  const fetchResponse: FetchOpportunitiesResponse = {
    sources: {},
    inserted: 1,
    updated: 0,
    reopened: 0,
    unchanged: 0,
    errors: [],
  };
  return {
    list: () => of(listResponse),
    fetch: () => of(fetchResponse),
    ...overrides,
  };
}

describe('OpportunitiesComponent', () => {
  function mount(service: Partial<OpportunitiesService> = makeOpportunitiesService()) {
    TestBed.configureTestingModule({
      imports: [OpportunitiesComponent],
      providers: [{ provide: OpportunitiesService, useValue: service }],
    });
    const fixture = TestBed.createComponent(OpportunitiesComponent);
    fixture.detectChanges();
    return fixture;
  }

  it('renders loaded opportunities in the results table', () => {
    const fixture = mount();
    expect(fixture.nativeElement.textContent).toContain('Khipu 2027');
    expect(fixture.nativeElement.textContent).toContain('Funded');
    expect(fixture.nativeElement.querySelector('table')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('.filters-bar')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('.prefs-bar')).not.toBeNull();
  });

  it('shows an error state when loading fails', () => {
    const fixture = mount({
      list: () => throwError(() => new Error('boom')),
      fetch: () =>
        of({ sources: {}, inserted: 0, updated: 0, reopened: 0, unchanged: 0, errors: [] }),
    });
    expect(fixture.nativeElement.querySelector('.section-error')).not.toBeNull();
  });
});
