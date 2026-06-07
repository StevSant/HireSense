import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { AutohuntComponent } from './autohunt.component';
import { AutohuntService } from '../../core/services/autohunt.service';
import { Digest } from './models/digest.model';

function makeDigest(over: Partial<Digest> = {}): Digest {
  return {
    id: 'dig-1',
    created_at: '2026-06-07T00:00:00Z',
    cutoff_at: '2026-06-06T00:00:00Z',
    job_count: 2,
    entries: [
      { job_id: 'job-1', title: 'Backend Engineer', company: 'Acme', url: 'https://x/1', score: 0.87 },
      { job_id: 'job-2', title: 'Platform Engineer', company: 'Globex', url: null, score: 0.71 },
    ],
    ...over,
  };
}

describe('AutohuntComponent', () => {
  function mount(opts: { autohunt?: Partial<Record<string, unknown>> } = {}) {
    const autohunt = {
      latest: vi.fn(() => of(makeDigest())),
      listRecent: vi.fn(() => of([makeDigest()])),
      run: vi.fn(() => of(makeDigest())),
      ...opts.autohunt,
    };

    TestBed.configureTestingModule({
      imports: [AutohuntComponent],
      providers: [
        provideRouter([]),
        { provide: AutohuntService, useValue: autohunt },
      ],
    });
    const fixture = TestBed.createComponent(AutohuntComponent);
    fixture.detectChanges();
    return { fixture, cmp: fixture.componentInstance, autohunt };
  }

  it('loads the latest digest and renders its entries', () => {
    const { cmp, autohunt } = mount();

    expect(autohunt.latest).toHaveBeenCalled();
    expect(cmp.latestDigest()?.id).toBe('dig-1');
    expect(cmp.latestDigest()?.entries.length).toBe(2);
  });

  it('maps a null latest (204) to the empty state', () => {
    const latest = vi.fn(() => of(null));
    const { cmp } = mount({ autohunt: { latest } });

    expect(cmp.latestDigest()).toBeNull();
    expect(cmp.latestError()).toBe('');
  });

  it('loads history on init', () => {
    const { cmp, autohunt } = mount();

    expect(autohunt.listRecent).toHaveBeenCalled();
    expect(cmp.history().length).toBe(1);
  });

  it('run() success sets the latest digest and refreshes history', () => {
    const run = vi.fn(() => of(makeDigest({ id: 'dig-new', job_count: 5 })));
    const listRecent = vi.fn(() => of([makeDigest({ id: 'dig-new' })]));
    const { cmp, autohunt } = mount({ autohunt: { run, listRecent } });

    const historyCallsBefore = autohunt.listRecent.mock.calls.length;
    cmp.run();

    expect(run).toHaveBeenCalled();
    expect(cmp.latestDigest()?.id).toBe('dig-new');
    expect(cmp.running()).toBe(false);
    expect(autohunt.listRecent.mock.calls.length).toBe(historyCallsBefore + 1);
  });

  it('run() error surfaces an inline message and clears running', () => {
    const run = vi.fn(() => throwError(() => ({ error: { detail: 'boom' } })));
    const { cmp } = mount({ autohunt: { run } });

    cmp.run();

    expect(cmp.runError()).toBe('boom');
    expect(cmp.running()).toBe(false);
  });

  it('latest error surfaces an inline message', () => {
    const latest = vi.fn(() => throwError(() => ({ error: { detail: 'nope' } })));
    const { cmp } = mount({ autohunt: { latest } });

    expect(cmp.latestError()).toBe('nope');
  });

  it('toggleExpanded expands and collapses a history row', () => {
    const { cmp } = mount();

    expect(cmp.expandedId()).toBeNull();
    cmp.toggleExpanded('dig-1');
    expect(cmp.expandedId()).toBe('dig-1');
    cmp.toggleExpanded('dig-1');
    expect(cmp.expandedId()).toBeNull();
  });

  it('scorePercent renders a 0..1 score as a percentage', () => {
    const { cmp } = mount();

    expect(cmp.scorePercent(0.87)).toBe(87);
    expect(cmp.scorePercent(1)).toBe(100);
  });
});
