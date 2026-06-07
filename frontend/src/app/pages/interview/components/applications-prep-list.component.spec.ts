import { TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { Subject, of, throwError } from 'rxjs';
import { ApplicationsPrepListComponent } from './applications-prep-list.component';
import { ApplicationsService } from '../../../core/services/applications.service';

function makeApp(over: Partial<Record<string, unknown>> = {}) {
  return {
    id: 'app-1',
    title: 'Backend Engineer',
    company: 'Acme Corp',
    status: 'applied',
    url: null,
    created_at: null,
    has_match: false,
    has_optimization: false,
    has_prep: true,
    latest_match_score: null,
    ...over,
  };
}

describe('ApplicationsPrepListComponent', () => {
  function mount(opts: { list?: () => unknown; router?: unknown } = {}) {
    const service = { list: opts.list ?? (() => of([makeApp()])) };
    TestBed.configureTestingModule({
      imports: [ApplicationsPrepListComponent],
      providers: [
        { provide: ApplicationsService, useValue: service },
        { provide: Router, useValue: opts.router ?? { navigate: () => {} } },
      ],
    });
    const fixture = TestBed.createComponent(ApplicationsPrepListComponent);
    fixture.detectChanges();
    return fixture;
  }

  it('populates applications and clears loading on success (happy path)', () => {
    const fixture = mount({ list: () => of([makeApp(), makeApp({ id: 'app-2' })]) });
    const cmp = fixture.componentInstance;

    expect(cmp.applications().length).toBe(2);
    expect(cmp.loading()).toBe(false);
  });

  it('keeps loading true while the request is in flight (loading state)', () => {
    const pending = new Subject<unknown[]>();
    const fixture = mount({ list: () => pending.asObservable() });
    const cmp = fixture.componentInstance;

    expect(cmp.loading()).toBe(true);

    pending.next([makeApp()]);
    pending.complete();
    expect(cmp.loading()).toBe(false);
  });

  it('clears loading without crashing when the list fetch fails (error state)', () => {
    const fixture = mount({ list: () => throwError(() => new Error('boom')) });
    const cmp = fixture.componentInstance;

    expect(cmp.loading()).toBe(false);
    expect(cmp.applications()).toEqual([]);
  });

  it('navigates to the application interview tab on openPrep', () => {
    const navigate = vi.fn();
    const fixture = mount({ router: { navigate } });

    fixture.componentInstance.openPrep('app-1');

    expect(navigate).toHaveBeenCalledWith(['/dashboard/applications', 'app-1'], {
      queryParams: { tab: 'interview' },
    });
  });
});
