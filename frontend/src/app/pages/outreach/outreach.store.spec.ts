import { TestBed } from '@angular/core/testing';
import { ActivatedRoute } from '@angular/router';
import { Observable, Subject, of, throwError } from 'rxjs';
import { ApplicationsService } from '../../core/services/applications.service';
import { NetworkService } from '../../core/services/network.service';
import { OutreachService } from '../../core/services/outreach.service';
import { ApplicationListItem } from '@core/contracts/application-list-item.model';
import { GenerateResponse } from '@core/contracts/generate-response.model';
import { NetworkContact } from '@core/contracts/network-contact.model';
import { NetworkMatchResponse } from '@core/contracts/network-match-response.model';
import { OutreachEvent } from '@core/contracts/outreach-event.model';
import { OutreachNudge } from '@core/contracts/outreach-nudge.model';
import { PagedResult } from '@core/contracts/paged-result.model';
import { OutreachStore } from './outreach.store';
import { environment } from '../../../environments/environment';

function makeApp(over: Partial<ApplicationListItem> = {}): ApplicationListItem {
  return {
    id: 'app-1',
    title: 'Senior Backend Engineer',
    company: 'Acme Corp',
    status: 'saved',
    url: null,
    created_at: null,
    has_match: false,
    has_optimization: false,
    has_prep: false,
    latest_match_score: null,
    job_id: null,
    notes: null,
    applied_at: null,
    location: null,
    remote_modality: null,
    salary_range: null,
    source: null,
    posted_date: null,
    ...over,
  };
}

function makeEvent(over: Partial<OutreachEvent> = {}): OutreachEvent {
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

function makeNudge(over: Partial<OutreachNudge> = {}): OutreachNudge {
  return {
    application_id: 'app-1',
    company: 'Acme Corp',
    contact_name: 'Jordan',
    sent_at: '2026-06-01T00:00:00Z',
    days_since: 6,
    ...over,
  };
}

function makeContact(over: Partial<NetworkContact> = {}): NetworkContact {
  return {
    first_name: 'Jane',
    last_name: 'Doe',
    company: 'Acme Corp',
    position: 'Engineer',
    linkedin_url: null,
    email: null,
    connected_on: null,
    company_normalized: 'acme corp',
    ...over,
  };
}

interface SetupOptions {
  readonly listAll?: () => Observable<PagedResult<ApplicationListItem>>;
  readonly generate?: () => Observable<GenerateResponse>;
  readonly record?: () => Observable<OutreachEvent>;
  readonly listEvents?: (applicationId: string) => Observable<OutreachEvent[]>;
  readonly dueFollowups?: () => Observable<OutreachNudge[]>;
  readonly match?: () => Observable<NetworkMatchResponse>;
  readonly applicationId?: string;
}

function setup(over: SetupOptions = {}) {
  const listAll = vi.fn(
    over.listAll ??
      ((): Observable<PagedResult<ApplicationListItem>> => of({ items: [makeApp()], total: 1 })),
  );
  const generate = vi.fn(
    over.generate ?? ((): Observable<GenerateResponse> => of({ message: 'Generated message' })),
  );
  const record = vi.fn(over.record ?? (() => of(makeEvent())));
  const listEvents = vi.fn(
    over.listEvents ??
      ((applicationId: string) => of([makeEvent({ application_id: applicationId })])),
  );
  const dueFollowups = vi.fn(over.dueFollowups ?? (() => of<OutreachNudge[]>([])));
  const match = vi.fn(
    over.match ??
      ((): Observable<NetworkMatchResponse> =>
        of({ company_normalized: 'acme corp', contacts: [] })),
  );

  const applicationId = over.applicationId ?? null;
  const route = {
    snapshot: {
      queryParamMap: {
        get: (key: string) => (key === 'application_id' ? applicationId : null),
      },
    },
  };

  TestBed.configureTestingModule({
    providers: [
      OutreachStore,
      { provide: ActivatedRoute, useValue: route },
      { provide: OutreachService, useValue: { generate, record, listEvents, dueFollowups } },
      { provide: ApplicationsService, useValue: { listAll } },
      { provide: NetworkService, useValue: { match } },
    ],
  });

  return {
    store: TestBed.inject(OutreachStore),
    listAll,
    generate,
    record,
    listEvents,
    dueFollowups,
    match,
  };
}

describe('OutreachStore bootstrap', () => {
  it('loads the applications and nudges without selecting anything', () => {
    const { store, listAll, dueFollowups, listEvents } = setup({
      dueFollowups: () => of([makeNudge()]),
    });

    store.init();

    expect(listAll).toHaveBeenCalledTimes(1);
    expect(dueFollowups).toHaveBeenCalledTimes(1);
    expect(store.applications().length).toBe(1);
    expect(store.nudges().length).toBe(1);
    expect(store.nudgesLoading()).toBe(false);
    expect(store.selectedApplicationId()).toBe('');
    expect(listEvents).not.toHaveBeenCalled();
  });

  it('ignores a second init so the bootstrap requests are not duplicated', () => {
    const { store, listAll, dueFollowups } = setup();

    store.init();
    store.init();

    expect(listAll).toHaveBeenCalledTimes(1);
    expect(dueFollowups).toHaveBeenCalledTimes(1);
  });

  it('preselects the application named by the query param and loads its timeline', () => {
    const { store, listEvents, match } = setup({ applicationId: 'app-1' });

    store.init();

    expect(store.selectedApplicationId()).toBe('app-1');
    expect(listEvents).toHaveBeenCalledWith('app-1');
    expect(match).toHaveBeenCalledWith('Acme Corp');
  });

  it('ignores a query param naming an application the user does not have', () => {
    const { store, listEvents } = setup({ applicationId: 'app-missing' });

    store.init();

    expect(store.selectedApplicationId()).toBe('');
    expect(listEvents).not.toHaveBeenCalled();
  });

  it('reports why the application list is empty when it fails to load', () => {
    const { store } = setup({ listAll: () => throwError(() => ({ error: { detail: 'nope' } })) });

    store.init();

    expect(store.applications()).toEqual([]);
    expect(store.applicationsError()).toBe('nope');
  });

  it('falls back to a generic message when the list failure carries no detail', () => {
    const { store } = setup({ listAll: () => throwError(() => new Error('offline')) });

    store.init();

    expect(store.applicationsError()).toBe('Could not load your applications.');
  });

  it('labels each picker option with its title and company', () => {
    const { store } = setup({
      listAll: () =>
        of({
          items: [makeApp(), makeApp({ id: 'app-2', title: 'Designer', company: 'Globex' })],
          total: 2,
        }),
    });

    store.init();

    expect(store.applicationOptions()).toEqual([
      { value: 'app-1', label: 'Senior Backend Engineer @ Acme Corp' },
      { value: 'app-2', label: 'Designer @ Globex' },
    ]);
  });

  it('does not treat a blank selection as a selection', () => {
    const { store } = setup();
    store.init();

    expect(store.hasSelection()).toBe(false);

    store.selectApplication('   ');
    expect(store.hasSelection()).toBe(false);

    store.selectApplication('app-1');
    expect(store.hasSelection()).toBe(true);
  });
});

describe('OutreachStore generate', () => {
  it('refuses to generate before an application is picked', () => {
    const { store, generate } = setup();
    store.init();

    store.generate();

    expect(generate).not.toHaveBeenCalled();
    expect(store.composeNotice()).toBe('Pick an application first.');
  });

  it('seeds the editable message from the generated draft', () => {
    const { store, generate } = setup({ applicationId: 'app-1' });
    store.init();

    store.generate();

    expect(generate).toHaveBeenCalledWith({ application_id: 'app-1' });
    expect(store.message()).toBe('Generated message');
    expect(store.composeNotice()).toBe('');
    expect(store.generating()).toBe(false);
  });

  it('sends the trimmed contact and channel when they are filled in', () => {
    const { store, generate } = setup({ applicationId: 'app-1' });
    store.init();
    store.contactName.set('  Jane Doe  ');
    store.channel.set('  linkedin  ');

    store.generate();

    expect(generate).toHaveBeenCalledWith({
      application_id: 'app-1',
      contact_name: 'Jane Doe',
      channel: 'linkedin',
    });
  });

  it('explains a 503 as an LLM configuration problem', () => {
    const { store } = setup({
      applicationId: 'app-1',
      generate: () => throwError(() => ({ status: 503 })),
    });
    store.init();

    store.generate();

    expect(store.message()).toBe('');
    expect(store.composeNotice()).toBe(
      'Message generation is unavailable — check the LLM settings.',
    );
  });

  it('explains a 404 as a missing application', () => {
    const { store } = setup({
      applicationId: 'app-1',
      generate: () => throwError(() => ({ status: 404 })),
    });
    store.init();

    store.generate();

    expect(store.composeNotice()).toBe('That application could not be found.');
  });

  it('falls back to a generic message for an unexpected generate failure', () => {
    const { store } = setup({
      applicationId: 'app-1',
      generate: () => throwError(() => ({ status: 500 })),
    });
    store.init();

    store.generate();

    expect(store.composeNotice()).toBe('Could not generate a message.');
  });

  it('does not start a second request while one is already generating', () => {
    let subscriptions = 0;
    const pending = new Observable<GenerateResponse>(() => {
      subscriptions += 1;
    });
    const { store } = setup({ applicationId: 'app-1', generate: () => pending });
    store.init();

    store.generate();
    store.generate();

    expect(subscriptions).toBe(1);
    expect(store.generating()).toBe(true);
  });

  it('leaves a drafted message untouched when selecting an application with nothing cached', () => {
    const { store } = setup({
      listAll: () => of({ items: [makeApp(), makeApp({ id: 'app-2' })], total: 2 }),
    });
    store.init();
    store.message.set('Half-written note');

    store.selectApplication('app-2');

    expect(store.message()).toBe('Half-written note');
  });
});

describe('OutreachStore copy', () => {
  let originalClipboard: PropertyDescriptor | undefined;
  const writeText = vi.fn();

  beforeEach(() => {
    vi.useFakeTimers();
    writeText.mockClear();
    originalClipboard = Object.getOwnPropertyDescriptor(navigator, 'clipboard');
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
  });

  afterEach(() => {
    vi.useRealTimers();
    if (originalClipboard) {
      Object.defineProperty(navigator, 'clipboard', originalClipboard);
    } else {
      Reflect.deleteProperty(navigator, 'clipboard');
    }
  });

  it('copies the message and shows the confirmation for the transient window', () => {
    const { store } = setup();
    store.message.set('Hello there');

    store.copyMessage();

    expect(writeText).toHaveBeenCalledWith('Hello there');
    expect(store.copied()).toBe(true);

    vi.advanceTimersByTime(environment.transientFeedbackMs);

    expect(store.copied()).toBe(false);
  });

  it('does nothing when there is no message to copy', () => {
    const { store } = setup();

    store.copyMessage();

    expect(writeText).not.toHaveBeenCalled();
    expect(store.copied()).toBe(false);
  });
});

describe('OutreachStore record', () => {
  it('refuses to record before an application is picked', () => {
    const { store, record } = setup();
    store.init();

    store.record('sent');

    expect(record).not.toHaveBeenCalled();
    expect(store.recordError()).toBe('Pick an application first.');
  });

  it('omits the optional fields that are blank and trims the rest', () => {
    const { store, record } = setup({ applicationId: 'app-1' });
    store.init();
    store.contactName.set('  Jane Doe  ');
    store.channel.set('   ');
    store.message.set('  Hi there  ');

    store.record('sent');

    expect(record).toHaveBeenCalledWith({
      application_id: 'app-1',
      kind: 'sent',
      message: 'Hi there',
      contact_name: 'Jane Doe',
    });
  });

  it('refreshes the timeline after a recorded event', () => {
    const { store, listEvents } = setup({ applicationId: 'app-1' });
    store.init();
    const before = listEvents.mock.calls.length;

    store.record('replied');

    expect(store.recording()).toBe(false);
    expect(store.recordError()).toBe('');
    expect(listEvents.mock.calls.length).toBe(before + 1);
  });

  it('clears the spinner and reports a failed record', () => {
    const { store, listEvents } = setup({
      applicationId: 'app-1',
      record: () => throwError(() => ({ error: { detail: 'could not save' } })),
    });
    store.init();
    const before = listEvents.mock.calls.length;

    store.record('sent');

    expect(store.recording()).toBe(false);
    expect(store.recordError()).toBe('could not save');
    expect(listEvents.mock.calls.length).toBe(before);
  });
});

describe('OutreachStore timeline', () => {
  it('sorts undated events to the bottom in both directions', () => {
    const { store } = setup({
      applicationId: 'app-1',
      listEvents: () =>
        of([
          makeEvent({ id: 'undated', created_at: null }),
          makeEvent({ id: 'old', created_at: '2026-06-01T00:00:00Z' }),
          makeEvent({ id: 'new', created_at: '2026-06-07T00:00:00Z' }),
        ]),
    });
    store.init();

    expect(store.visibleEvents().map((e) => e.id)).toEqual(['new', 'old', 'undated']);

    store.setEventSort('created', 'asc');

    expect(store.visibleEvents().map((e) => e.id)).toEqual(['old', 'new', 'undated']);
  });

  it('narrows the timeline to one kind without discarding the loaded events', () => {
    const { store } = setup({
      applicationId: 'app-1',
      listEvents: () =>
        of([
          makeEvent({ id: 'a', kind: 'sent' }),
          makeEvent({ id: 'b', kind: 'replied', created_at: '2026-06-08T00:00:00Z' }),
        ]),
    });
    store.init();

    store.setKindFilter('replied');
    expect(store.visibleEvents().map((e) => e.id)).toEqual(['b']);

    store.setKindFilter('');
    expect(store.visibleEvents().length).toBe(2);
  });

  it('ignores a timeline response that lands after the user switched applications', () => {
    const pending: Subject<OutreachEvent[]>[] = [];
    const { store } = setup({
      listAll: () =>
        of({ items: [makeApp(), makeApp({ id: 'app-2', company: 'Globex' })], total: 2 }),
      listEvents: () => {
        const subject = new Subject<OutreachEvent[]>();
        pending.push(subject);
        return subject.asObservable();
      },
    });
    store.init();

    store.selectApplication('app-1');
    store.selectApplication('app-2');
    expect(pending.length).toBe(2);

    pending[0].next([makeEvent({ id: 'stale', application_id: 'app-1' })]);

    expect(store.events()).toEqual([]);
    expect(store.timelineLoading()).toBe(true);

    pending[1].next([makeEvent({ id: 'current', application_id: 'app-2' })]);

    expect(store.events().map((e) => e.id)).toEqual(['current']);
    expect(store.timelineLoading()).toBe(false);
  });

  it('clears the spinner and reports a failed timeline load', () => {
    const { store } = setup({
      applicationId: 'app-1',
      listEvents: () => throwError(() => ({ error: { detail: 'timeline down' } })),
    });

    store.init();

    expect(store.timelineLoading()).toBe(false);
    expect(store.timelineError()).toBe('timeline down');
    expect(store.events()).toEqual([]);
  });

  it('empties the timeline when the selection is cleared', () => {
    const { store } = setup({ applicationId: 'app-1' });
    store.init();
    expect(store.events().length).toBe(1);

    store.selectApplication('');

    expect(store.events()).toEqual([]);
  });
});

describe('OutreachStore contact suggestions', () => {
  it('shows at most five suggested contacts', () => {
    const contacts = Array.from({ length: 7 }, (_, i) =>
      makeContact({ first_name: `Contact${i}` }),
    );
    const { store } = setup({
      applicationId: 'app-1',
      match: () => of({ company_normalized: 'acme corp', contacts }),
    });

    store.init();

    expect(store.suggestions().length).toBe(5);
    expect(store.suggestions()[0].first_name).toBe('Contact0');
  });

  it('skips the lookup for an application with no company', () => {
    const { store, match } = setup({
      applicationId: 'app-1',
      listAll: () => of({ items: [makeApp({ company: '' })], total: 1 }),
    });

    store.init();

    expect(match).not.toHaveBeenCalled();
    expect(store.suggestions()).toEqual([]);
  });

  it('ignores suggestions that land after the user switched applications', () => {
    const pending: Subject<NetworkMatchResponse>[] = [];
    const { store } = setup({
      listAll: () =>
        of({ items: [makeApp(), makeApp({ id: 'app-2', company: 'Globex' })], total: 2 }),
      match: () => {
        const subject = new Subject<NetworkMatchResponse>();
        pending.push(subject);
        return subject.asObservable();
      },
    });
    store.init();

    store.selectApplication('app-1');
    store.selectApplication('app-2');

    pending[0].next({ company_normalized: 'acme corp', contacts: [makeContact()] });

    expect(store.suggestions()).toEqual([]);
  });

  it('fills the contact field from a suggestion chip', () => {
    const { store } = setup();

    store.useContact(makeContact({ first_name: 'Ada', last_name: 'Lovelace' }));

    expect(store.contactName()).toBe('Ada Lovelace');
  });
});

describe('OutreachStore nudges', () => {
  it('drops the nudge and refreshes the timeline when it is the open application', () => {
    const { store, listEvents } = setup({
      applicationId: 'app-1',
      dueFollowups: () => of([makeNudge()]),
    });
    store.init();
    const before = listEvents.mock.calls.length;

    store.markFollowedUp(store.nudges()[0]);

    expect(store.nudges()).toEqual([]);
    expect(listEvents.mock.calls.length).toBe(before + 1);
  });

  it('drops the nudge without refetching a timeline the user is not looking at', () => {
    const { store, listEvents, record } = setup({
      applicationId: 'app-1',
      dueFollowups: () => of([makeNudge({ application_id: 'app-2' })]),
    });
    store.init();
    const before = listEvents.mock.calls.length;

    store.markFollowedUp(store.nudges()[0]);

    expect(record).toHaveBeenCalledWith({ application_id: 'app-2', kind: 'followed_up' });
    expect(store.nudges()).toEqual([]);
    expect(listEvents.mock.calls.length).toBe(before);
  });

  it('keeps the nudge and reports the error when recording the follow-up fails', () => {
    const { store } = setup({
      dueFollowups: () => of([makeNudge()]),
      record: () => throwError(() => ({ error: { detail: 'save failed' } })),
    });
    store.init();

    store.markFollowedUp(store.nudges()[0]);

    expect(store.nudgesError()).toBe('save failed');
    expect(store.nudges().length).toBe(1);
  });

  it('clears the spinner and reports a failed nudge load', () => {
    const { store } = setup({ dueFollowups: () => throwError(() => new Error('offline')) });

    store.init();

    expect(store.nudgesLoading()).toBe(false);
    expect(store.nudgesError()).toBe('Could not load follow-up nudges.');
  });

  it('selects the nudge’s application when the row is opened', () => {
    const { store, listEvents } = setup({
      listAll: () =>
        of({ items: [makeApp(), makeApp({ id: 'app-2', company: 'Globex' })], total: 2 }),
      dueFollowups: () => of([makeNudge({ application_id: 'app-2' })]),
    });
    store.init();

    store.selectNudge(store.nudges()[0]);

    expect(store.selectedApplicationId()).toBe('app-2');
    expect(listEvents).toHaveBeenCalledWith('app-2');
  });
});
