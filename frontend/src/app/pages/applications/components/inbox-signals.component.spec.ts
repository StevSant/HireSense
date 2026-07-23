import { TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';
import { InboxSignalsComponent } from './inbox-signals.component';
import { InboxSignalsService } from '../../../core/services/inbox-signals.service';

describe('InboxSignalsComponent', () => {
  function mount(service: Partial<InboxSignalsService> = {}) {
    const inbox = {
      listPending: vi.fn(() => of([makeSignal()])),
      confirm: vi.fn(() => of({ ...makeSignal(), state: 'applied' as const })),
      dismiss: vi.fn(() => of({ ...makeSignal(), state: 'dismissed' as const })),
      ...service,
    };
    TestBed.configureTestingModule({
      imports: [InboxSignalsComponent],
      providers: [{ provide: InboxSignalsService, useValue: inbox }],
    });
    const fixture = TestBed.createComponent(InboxSignalsComponent);
    fixture.detectChanges();
    return { fixture, inbox };
  }

  it('loads only pending status signals for human review', () => {
    const { fixture, inbox } = mount();

    expect(inbox.listPending).toHaveBeenCalledOnce();
    expect(fixture.componentInstance.signals()).toHaveLength(1);
    expect(fixture.nativeElement.textContent).toContain('Interview invitation');
  });

  it('confirms a proposed application status and removes the reviewed signal', () => {
    const { fixture, inbox } = mount();

    fixture.componentInstance.confirm('signal-1');

    expect(inbox.confirm).toHaveBeenCalledWith('signal-1');
    expect(fixture.componentInstance.signals()).toEqual([]);
  });

  it('keeps a failed confirmation available for review', () => {
    const { fixture } = mount({
      confirm: () => throwError(() => ({ error: { detail: 'The application was already rejected.' } })),
    });

    fixture.componentInstance.confirm('signal-1');

    expect(fixture.componentInstance.signals()).toHaveLength(1);
    expect(fixture.componentInstance.error()).toContain('already rejected');
  });
});

function makeSignal() {
  return {
    id: 'signal-1',
    message_id: 'message-1',
    from_address: 'jobs@acme.test',
    subject: 'Interview invitation',
    received_at: '2026-07-22T12:00:00Z',
    kind: 'interview',
    company: 'Acme',
    role: 'Engineer',
    confidence: 0.93,
    matched_application_id: 'app-1',
    proposed_status: 'interviewing',
    state: 'pending' as const,
    created_at: '2026-07-22T12:00:00Z',
  };
}
