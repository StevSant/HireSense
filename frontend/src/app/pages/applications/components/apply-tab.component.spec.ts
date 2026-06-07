import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { of, throwError } from 'rxjs';
import { ApplyTabComponent } from './apply-tab.component';
import { ApplicationsService } from '../../../core/services/applications.service';
import { CoverLetterRunnerService } from '../../../core/services/cover-letter-runner.service';
import { ApplicationAggregate } from '../models/application-aggregate.model';

function makeAggregate(over: Partial<ApplicationAggregate> = {}): ApplicationAggregate {
  return {
    id: 'app-1',
    job_id: 'job-1',
    title: 'Senior Backend Engineer',
    company: 'Acme Corp',
    url: 'https://example.com/job-1',
    status: 'saved',
    notes: null,
    applied_at: null,
    created_at: null,
    updated_at: null,
    job_snapshot: null,
    latest_match: null,
    latest_optimization: null,
    latest_interview_prep: null,
    latest_cover_letter: null,
    match_count: 0,
    optimization_count: 0,
    interview_prep_count: 0,
    cover_letter_count: 0,
    ...over,
  };
}

describe('ApplyTabComponent', () => {
  let runnerRun: ReturnType<typeof vi.fn>;
  let runningId: ReturnType<typeof signal<string | null>>;
  let lastError: ReturnType<typeof signal<string>>;

  function mount(aggregate = makeAggregate(), service: Record<string, unknown> = {}) {
    runnerRun = vi.fn();
    runningId = signal<string | null>(null);
    lastError = signal('');
    const runner = {
      run: runnerRun,
      isRunning: (id: string) => runningId() === id,
      lastError,
    };
    const svc = {
      downloadCvPdf: () => of(new Blob(['cv'])),
      downloadOriginalCvPdf: () => of(new Blob(['cv'])),
      downloadCoverLetterPdf: () => of(new Blob(['cl'])),
      downloadBundle: () => of(new Blob(['zip'])),
      markApplied: () => of(aggregate),
      ...service,
    };

    TestBed.configureTestingModule({
      imports: [ApplyTabComponent],
      providers: [
        { provide: ApplicationsService, useValue: svc },
        { provide: CoverLetterRunnerService, useValue: runner },
      ],
    });
    const fixture = TestBed.createComponent(ApplyTabComponent);
    fixture.componentRef.setInput('aggregate', aggregate);
    fixture.detectChanges();
    return { fixture, svc };
  }

  it('delegates generate to the cover-letter runner with current language and tone', () => {
    const { fixture } = mount();
    fixture.componentInstance.onLangChange({ target: { value: 'es' } } as unknown as Event);
    fixture.componentInstance.onToneChange({ target: { value: 'concise' } } as unknown as Event);
    fixture.componentInstance.generate();
    expect(runnerRun).toHaveBeenCalledWith('app-1', 'es', 'concise');
  });

  it('reflects the runner running state', () => {
    const { fixture } = mount();
    expect(fixture.componentInstance.generating()).toBe(false);
    runningId.set('app-1');
    expect(fixture.componentInstance.generating()).toBe(true);
  });

  it('exposes the latest cover letter, cv presence and applied state', () => {
    const { fixture } = mount(
      makeAggregate({
        status: 'applied',
        latest_cover_letter: { id: 'cl', match_id: null, body: 'Dear hiring', tone: 'professional', created_at: null },
        latest_optimization: {
          id: 'opt',
          match_id: null,
          cv_language: 'en',
          original_tex: '',
          optimized_tex: 'x',
          improvement_summary: '',
          changes: [],
          created_at: null,
        },
      }),
    );
    expect(fixture.componentInstance.letter()?.body).toBe('Dear hiring');
    expect(fixture.componentInstance.hasCv()).toBe(true);
    expect(fixture.componentInstance.isApplied()).toBe(true);
  });

  it('downloads the tailored CV when an optimization exists', () => {
    const downloadCvPdf = vi.fn(() => of(new Blob(['cv'])));
    const downloadOriginalCvPdf = vi.fn(() => of(new Blob(['cv'])));
    const { fixture } = mount(
      makeAggregate({
        latest_optimization: {
          id: 'opt',
          match_id: null,
          cv_language: 'en',
          original_tex: '',
          optimized_tex: 'x',
          improvement_summary: '',
          changes: [],
          created_at: null,
        },
      }),
      { downloadCvPdf, downloadOriginalCvPdf },
    );
    fixture.componentInstance.downloadCv();
    expect(downloadCvPdf).toHaveBeenCalledWith('app-1');
    expect(downloadOriginalCvPdf).not.toHaveBeenCalled();
    expect(fixture.componentInstance.downloadingCv()).toBe(false);
  });

  it('downloads the original CV when no optimization exists', () => {
    const downloadCvPdf = vi.fn(() => of(new Blob(['cv'])));
    const downloadOriginalCvPdf = vi.fn(() => of(new Blob(['cv'])));
    const { fixture } = mount(makeAggregate(), { downloadCvPdf, downloadOriginalCvPdf });
    fixture.componentInstance.downloadCv();
    expect(downloadOriginalCvPdf).toHaveBeenCalledWith('app-1', 'en');
    expect(downloadCvPdf).not.toHaveBeenCalled();
  });

  it('surfaces an error when CV download fails', () => {
    const { fixture } = mount(makeAggregate(), {
      downloadOriginalCvPdf: () => throwError(() => ({ error: { detail: 'pdf boom' } })),
    });
    fixture.componentInstance.downloadCv();
    expect(fixture.componentInstance.error()).toBe('pdf boom');
    expect(fixture.componentInstance.downloadingCv()).toBe(false);
  });

  it('marks the application as applied and emits changed', () => {
    const markApplied = vi.fn(() => of(makeAggregate()));
    const { fixture } = mount(makeAggregate(), { markApplied });
    let emitted = false;
    fixture.componentInstance.changed.subscribe(() => (emitted = true));
    fixture.componentInstance.markApplied();
    expect(markApplied).toHaveBeenCalledWith('app-1');
    expect(emitted).toBe(true);
    expect(fixture.componentInstance.marking()).toBe(false);
  });

  it('surfaces an error and does not emit when mark-applied fails', () => {
    const { fixture } = mount(makeAggregate(), {
      markApplied: () => throwError(() => ({ error: { detail: 'mark fail' } })),
    });
    let emitted = false;
    fixture.componentInstance.changed.subscribe(() => (emitted = true));
    fixture.componentInstance.markApplied();
    expect(fixture.componentInstance.error()).toBe('mark fail');
    expect(emitted).toBe(false);
    expect(fixture.componentInstance.marking()).toBe(false);
  });

  it('opens the job url in a new tab then marks applied', () => {
    const open = vi.spyOn(window, 'open').mockReturnValue(null);
    const markApplied = vi.fn(() => of(makeAggregate()));
    const { fixture } = mount(makeAggregate(), { markApplied });
    fixture.componentInstance.openJobAndMarkApplied();
    expect(open).toHaveBeenCalledWith('https://example.com/job-1', '_blank', 'noopener');
    expect(markApplied).toHaveBeenCalledWith('app-1');
  });
});
