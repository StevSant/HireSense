import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, Router, provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { ApplicationsComponent } from './applications.component';
import { ApplicationsService } from '../../core/services/applications.service';
import { ApplicationListItem } from './models/application-list-item.model';

function makeItem(over: Partial<ApplicationListItem> = {}): ApplicationListItem {
  return {
    id: 'app-1',
    title: 'Senior Backend Engineer',
    company: 'Acme Corp',
    status: 'saved',
    url: 'https://example.com/job-1',
    created_at: '2026-01-01T00:00:00Z',
    has_match: true,
    has_optimization: false,
    has_prep: false,
    latest_match_score: 0.82,
    ...over,
  };
}

describe('ApplicationsComponent', () => {
  function mount(
    opts: {
      list?: () => unknown;
      remove?: () => unknown;
    } = {},
  ) {
    const list = vi.fn(opts.list ?? (() => of([makeItem()])));
    const remove = vi.fn(opts.remove ?? (() => of(undefined)));

    TestBed.configureTestingModule({
      imports: [ApplicationsComponent],
      providers: [provideRouter([]), { provide: ApplicationsService, useValue: { list, remove } }],
    });
    const navigate = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    const fixture = TestBed.createComponent(ApplicationsComponent);
    fixture.detectChanges();
    return { fixture, list, remove, navigate };
  }

  it('loads and renders a row per application', () => {
    const { fixture, list } = mount({ list: () => of([makeItem(), makeItem({ id: 'app-2' })]) });
    expect(list).toHaveBeenCalled();
    expect(fixture.componentInstance.applications().length).toBe(2);
    const rows = fixture.nativeElement.querySelectorAll('tr.row');
    expect(rows.length).toBe(2);
  });

  it('renders the empty state when there are no applications', () => {
    const { fixture } = mount({ list: () => of([]) });
    expect(fixture.nativeElement.querySelector('.empty-state')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('table.apps-table')).toBeNull();
  });

  it('shows an error alert when loading fails', () => {
    const { fixture } = mount({
      list: () => throwError(() => ({ error: { detail: 'boom' } })),
    });
    expect(fixture.componentInstance.error()).toBe('boom');
    expect(fixture.componentInstance.loading()).toBe(false);
    const alert = fixture.nativeElement.querySelector('.alert-error');
    expect(alert).not.toBeNull();
    expect(alert.textContent).toContain('boom');
  });

  it('falls back to a default error message when detail is missing', () => {
    const { fixture } = mount({ list: () => throwError(() => ({})) });
    expect(fixture.componentInstance.error()).toBe('Failed to load applications');
  });

  it('navigates to the detail page on open', () => {
    const { fixture, navigate } = mount();
    fixture.componentInstance.open('app-1');
    expect(navigate).toHaveBeenCalledWith(['/dashboard/applications', 'app-1']);
  });

  it('opens the create dialog via openCreate', () => {
    const { fixture } = mount();
    expect(fixture.componentInstance.showCreateDialog()).toBe(false);
    fixture.componentInstance.openCreate();
    expect(fixture.componentInstance.showCreateDialog()).toBe(true);
  });

  it('navigates and closes the dialog when a new application is created', () => {
    const { fixture, navigate } = mount();
    fixture.componentInstance.openCreate();
    fixture.componentInstance.onCreated('app-9');
    expect(fixture.componentInstance.showCreateDialog()).toBe(false);
    expect(navigate).toHaveBeenCalledWith(['/dashboard/applications', 'app-9']);
  });

  it('removes an application from the list on confirmed delete', () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    const item = makeItem();
    const { fixture, remove } = mount({ list: () => of([item]) });
    const event = { stopPropagation: vi.fn() } as unknown as MouseEvent;
    fixture.componentInstance.remove(item, event);
    expect(event.stopPropagation).toHaveBeenCalled();
    expect(remove).toHaveBeenCalledWith('app-1');
    expect(fixture.componentInstance.applications().length).toBe(0);
    expect(fixture.componentInstance.deletingId()).toBeNull();
  });

  it('does not call remove when delete is cancelled', () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false);
    const item = makeItem();
    const { fixture, remove } = mount({ list: () => of([item]) });
    const event = { stopPropagation: vi.fn() } as unknown as MouseEvent;
    fixture.componentInstance.remove(item, event);
    expect(remove).not.toHaveBeenCalled();
    expect(fixture.componentInstance.applications().length).toBe(1);
  });

  it('surfaces an error and keeps the row when delete fails', () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    const item = makeItem();
    const { fixture } = mount({
      list: () => of([item]),
      remove: () => throwError(() => ({ error: { detail: 'nope' } })),
    });
    const event = { stopPropagation: vi.fn() } as unknown as MouseEvent;
    fixture.componentInstance.remove(item, event);
    expect(fixture.componentInstance.error()).toBe('nope');
    expect(fixture.componentInstance.applications().length).toBe(1);
    expect(fixture.componentInstance.deletingId()).toBeNull();
  });

  it('shows a dismissible notice and strips the flag when redirected with notFound', () => {
    const navigate = vi.fn();
    const route = {
      snapshot: { queryParamMap: { has: (k: string) => k === 'notFound' } },
    };
    TestBed.configureTestingModule({
      imports: [ApplicationsComponent],
      providers: [
        { provide: Router, useValue: { navigate } },
        { provide: ActivatedRoute, useValue: route },
        { provide: ApplicationsService, useValue: { list: () => of([]), remove: vi.fn() } },
      ],
    });
    const fixture = TestBed.createComponent(ApplicationsComponent);
    fixture.detectChanges();

    expect(fixture.componentInstance.notice()).toContain('no longer exists');
    expect(fixture.nativeElement.querySelector('.notice-banner')).not.toBeNull();
    // The flag is stripped so a refresh doesn't re-show the notice.
    expect(navigate).toHaveBeenCalledWith(
      [],
      expect.objectContaining({ queryParams: {}, replaceUrl: true }),
    );

    fixture.componentInstance.dismissNotice();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.notice-banner')).toBeNull();
  });
});

describe('ApplicationsComponent sorting/filtering', () => {
  function mountWith(rows: ApplicationListItem[]): ApplicationsComponent {
    TestBed.configureTestingModule({
      imports: [ApplicationsComponent],
      providers: [
        provideRouter([]),
        {
          provide: ApplicationsService,
          useValue: { list: () => of(rows), remove: () => of(undefined) },
        },
      ],
    });
    const fixture = TestBed.createComponent(ApplicationsComponent);
    fixture.detectChanges();
    return fixture.componentInstance;
  }

  it('defaults to created descending', () => {
    const comp = mountWith([
      makeItem({ id: 'a', created_at: '2026-01-01T00:00:00Z' }),
      makeItem({ id: 'b', created_at: '2026-05-01T00:00:00Z' }),
      makeItem({ id: 'c', created_at: '2026-03-01T00:00:00Z' }),
    ]);
    expect(comp.visibleApplications().map((a) => a.id)).toEqual(['b', 'c', 'a']);
  });

  it('filters by query across title and company', () => {
    const comp = mountWith([
      makeItem({ id: 'a', title: 'Engineer', company: 'Globex' }),
      makeItem({ id: 'b', title: 'Designer', company: 'Acme' }),
    ]);
    comp.query.set('acme');
    expect(comp.visibleApplications().map((a) => a.id)).toEqual(['b']);
  });

  it('sorts by status ascending when toggled', () => {
    const comp = mountWith([
      makeItem({ id: 'a', status: 'saved' }),
      makeItem({ id: 'b', status: 'applied' }),
    ]);
    comp.sort.toggle('status'); // text field default asc; "applied" < "saved"
    expect(comp.visibleApplications().map((a) => a.id)).toEqual(['b', 'a']);
  });
});
