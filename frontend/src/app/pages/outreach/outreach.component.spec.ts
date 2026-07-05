import { TestBed } from '@angular/core/testing';
import { ActivatedRoute } from '@angular/router';
import { of, throwError } from 'rxjs';
import { OutreachComponent } from './outreach.component';
import { OutreachService } from '../../core/services/outreach.service';
import { NetworkService } from '../../core/services/network.service';
import { ApplicationsService } from '../../core/services/applications.service';

function makeApp(over: Partial<Record<string, unknown>> = {}) {
  return {
    id: 'app-1',
    title: 'Senior Backend Engineer',
    company: 'Acme Corp',
    status: 'tracked',
    url: null,
    created_at: null,
    has_match: false,
    has_optimization: false,
    has_prep: false,
    latest_match_score: null,
    ...over,
  };
}

function makeEvent(over: Partial<Record<string, unknown>> = {}) {
  return {
    id: 'evt-1',
    application_id: 'app-1',
    kind: 'sent',
    contact_name: null,
    channel: null,
    message: 'Hello there',
    created_at: '2026-06-07T00:00:00Z',
    ...over,
  };
}

function makeNudge(over: Partial<Record<string, unknown>> = {}) {
  return {
    application_id: 'app-1',
    company: 'Acme Corp',
    contact_name: 'Jordan',
    sent_at: '2026-06-01T00:00:00Z',
    days_since: 6,
    ...over,
  };
}

describe('OutreachComponent', () => {
  function mount(
    opts: {
      appId?: string | null;
      outreach?: Partial<Record<string, unknown>>;
      applications?: Partial<Record<string, unknown>>;
      network?: Partial<Record<string, unknown>>;
    } = {},
  ) {
    const route = {
      snapshot: {
        queryParamMap: {
          get: (key: string) => (key === 'application_id' ? (opts.appId ?? null) : null),
        },
      },
    };
    const outreach = {
      generate: vi.fn(() => of({ message: 'Generated message' })),
      record: vi.fn(() => of(makeEvent())),
      listEvents: vi.fn(() => of([makeEvent()])),
      dueFollowups: vi.fn(() => of([])),
      ...opts.outreach,
    };
    const applications = {
      list: vi.fn(() => of([makeApp()])),
      ...opts.applications,
    };
    const network = {
      match: vi.fn(() => of({ company_normalized: 'acme corp', contacts: [] })),
      import: vi.fn(() => of({ contacts: 0, imported_at: null })),
      ...opts.network,
    };

    TestBed.configureTestingModule({
      imports: [OutreachComponent],
      providers: [
        { provide: ActivatedRoute, useValue: route },
        { provide: OutreachService, useValue: outreach },
        { provide: ApplicationsService, useValue: applications },
        { provide: NetworkService, useValue: network },
      ],
    });
    const fixture = TestBed.createComponent(OutreachComponent);
    fixture.detectChanges();
    return { fixture, cmp: fixture.componentInstance, outreach, applications, network };
  }

  it('loads applications and preselects from the application_id query param', () => {
    const { cmp, outreach } = mount({ appId: 'app-1' });

    expect(cmp.applications().length).toBe(1);
    expect(cmp.selectedApplicationId()).toBe('app-1');
    expect(outreach.listEvents).toHaveBeenCalledWith('app-1');
  });

  it('generate happy path fills the message signal', () => {
    const { cmp, outreach } = mount({ appId: 'app-1' });

    cmp.generate();

    expect(outreach.generate).toHaveBeenCalled();
    expect(cmp.message()).toBe('Generated message');
    expect(cmp.composeNotice()).toBe('');
  });

  it('generate 503 sets the unavailable notice', () => {
    const generate = vi.fn(() => throwError(() => ({ status: 503 })));
    const { cmp } = mount({ appId: 'app-1', outreach: { generate } });

    cmp.generate();

    expect(cmp.message()).toBe('');
    expect(cmp.composeNotice()).toBe('Message generation is unavailable — check the LLM settings.');
  });

  it("record 'sent' triggers a timeline refresh", () => {
    const record = vi.fn(() => of(makeEvent()));
    const listEvents = vi.fn(() => of([makeEvent()]));
    const { cmp, outreach } = mount({ appId: 'app-1', outreach: { record, listEvents } });

    // one listEvents call already happened from preselect on init
    const callsBefore = outreach.listEvents.mock.calls.length;
    cmp.message.set('Hi there');
    cmp.record('sent');

    expect(record).toHaveBeenCalledWith(
      expect.objectContaining({ application_id: 'app-1', kind: 'sent', message: 'Hi there' }),
    );
    expect(outreach.listEvents.mock.calls.length).toBe(callsBefore + 1);
  });

  it('renders the timeline newest-first by default', () => {
    const listEvents = vi.fn(() =>
      of([
        makeEvent({ id: 'old', created_at: '2026-06-01T00:00:00Z' }),
        makeEvent({ id: 'new', created_at: '2026-06-07T00:00:00Z' }),
      ]),
    );
    const { cmp } = mount({ appId: 'app-1', outreach: { listEvents } });

    // Events are stored in natural order; visibleEvents applies the sort.
    expect(cmp.visibleEvents().map((e) => e.id)).toEqual(['new', 'old']);
  });

  it('can sort the timeline oldest-first and filter by kind', () => {
    const listEvents = vi.fn(() =>
      of([
        makeEvent({ id: 'a', kind: 'sent', created_at: '2026-06-01T00:00:00Z' }),
        makeEvent({ id: 'b', kind: 'replied', created_at: '2026-06-07T00:00:00Z' }),
      ]),
    );
    const { cmp } = mount({ appId: 'app-1', outreach: { listEvents } });

    cmp.eventSort.set('created', 'asc');
    expect(cmp.visibleEvents().map((e) => e.id)).toEqual(['a', 'b']);

    cmp.kindFilter.set('replied');
    expect(cmp.visibleEvents().map((e) => e.id)).toEqual(['b']);
  });

  it('loads nudges and "mark followed up" removes the row', () => {
    const dueFollowups = vi.fn(() => of([makeNudge({ application_id: 'app-2' })]));
    const record = vi.fn(() => of(makeEvent({ application_id: 'app-2' })));
    const { cmp, outreach } = mount({ outreach: { dueFollowups, record } });

    expect(cmp.nudges().length).toBe(1);

    cmp.markFollowedUp(cmp.nudges()[0]);

    expect(outreach.record).toHaveBeenCalledWith(
      expect.objectContaining({ application_id: 'app-2', kind: 'followed_up' }),
    );
    expect(cmp.nudges().length).toBe(0);
  });

  it('surfaces a nudges error state', () => {
    const dueFollowups = vi.fn(() => throwError(() => ({ error: { detail: 'boom' } })));
    const { cmp } = mount({ outreach: { dueFollowups } });

    expect(cmp.nudgesError()).toBe('boom');
  });

  it('selecting an application with a company triggers network.match', () => {
    const matchContacts = [
      {
        first_name: 'Jane',
        last_name: 'Doe',
        company: 'Acme Corp',
        position: 'Engineer',
        linkedin_url: 'https://linkedin.com/in/janedoe',
        email: null,
        connected_on: null,
        company_normalized: 'acme corp',
      },
    ];
    const match = vi.fn(() => of({ company_normalized: 'acme corp', contacts: matchContacts }));
    const { cmp, network } = mount({ network: { match } });

    // No selection yet
    cmp.selectApplication('app-1');

    expect(network.match).toHaveBeenCalledWith('Acme Corp');
    expect(cmp.suggestions()).toEqual(matchContacts);
  });

  it('clicking a contact chip fills the contactName signal', () => {
    const matchContacts = [
      {
        first_name: 'Jane',
        last_name: 'Doe',
        company: 'Acme Corp',
        position: 'Engineer',
        linkedin_url: null,
        email: null,
        connected_on: null,
        company_normalized: 'acme corp',
      },
    ];
    const match = vi.fn(() => of({ company_normalized: 'acme corp', contacts: matchContacts }));
    const { cmp, fixture } = mount({ appId: 'app-1', network: { match } });

    // Trigger suggestions render
    fixture.detectChanges();

    const chip = (fixture.nativeElement as HTMLElement).querySelector(
      '.chip',
    ) as HTMLButtonElement | null;
    expect(chip).toBeTruthy();
    chip!.click();

    expect(cmp.contactName()).toBe('Jane Doe');
  });

  it('clears suggestions when the selection changes', () => {
    const matchContacts = [
      {
        first_name: 'Jane',
        last_name: 'Doe',
        company: 'Acme Corp',
        position: 'Engineer',
        linkedin_url: null,
        email: null,
        connected_on: null,
        company_normalized: 'acme corp',
      },
    ];
    const match = vi.fn(() => of({ company_normalized: 'acme corp', contacts: matchContacts }));
    const { cmp } = mount({ appId: 'app-1', network: { match } });

    expect(cmp.suggestions().length).toBe(1);

    cmp.selectApplication('');

    expect(cmp.suggestions().length).toBe(0);
  });
});
