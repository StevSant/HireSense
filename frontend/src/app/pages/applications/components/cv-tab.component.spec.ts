import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { of, throwError } from 'rxjs';
import { CvTabComponent } from './cv-tab.component';
import { ApplicationsService } from '../../../core/services/applications.service';
import { CvOptimizationRunnerService } from '../../../core/services/cv-optimization-runner.service';
import { ApplicationAggregate } from '../models/application-aggregate.model';

function makeAggregate(over: Partial<ApplicationAggregate> = {}): ApplicationAggregate {
  return {
    id: 'app-1',
    job_id: 'job-1',
    title: 'Senior Backend Engineer',
    company: 'Acme Corp',
    url: null,
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

const OPT = {
  id: 'opt-1',
  match_id: null,
  cv_language: 'en',
  original_tex: 'orig',
  optimized_tex: 'optimized tex',
  improvement_summary: 'better',
  changes: [],
  created_at: null,
};

describe('CvTabComponent', () => {
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
      ...service,
    };

    TestBed.configureTestingModule({
      imports: [CvTabComponent],
      providers: [
        { provide: ApplicationsService, useValue: svc },
        { provide: CvOptimizationRunnerService, useValue: runner },
      ],
    });
    const fixture = TestBed.createComponent(CvTabComponent);
    fixture.componentRef.setInput('aggregate', aggregate);
    fixture.detectChanges();
    return { fixture, svc };
  }

  it('delegates run to the optimization runner with the chosen language', () => {
    const { fixture } = mount();
    fixture.componentInstance.onLangChange({ target: { value: 'es' } } as unknown as Event);
    fixture.componentInstance.run();
    expect(runnerRun).toHaveBeenCalledWith('app-1', 'es');
  });

  it('reflects the runner running state and exposes match presence', () => {
    const { fixture } = mount(
      makeAggregate({
        latest_match: {
          id: 'm',
          overall_score: 0.8,
          semantic_score: 0,
          skill_score: 0,
          experience_score: 0,
          language_score: 0,
          matched_skills: [],
          missing_skills: [],
          pros: [],
          cons: [],
          recommendations: [],
          cv_language: 'en',
          created_at: null,
        },
      }),
    );
    expect(fixture.componentInstance.hasMatch()).toBe(true);
    expect(fixture.componentInstance.running()).toBe(false);
    runningId.set('app-1');
    expect(fixture.componentInstance.running()).toBe(true);
  });

  it('toggles the view mode', () => {
    const { fixture } = mount();
    expect(fixture.componentInstance.viewMode()).toBe('changes');
    fixture.componentInstance.setViewMode('full');
    expect(fixture.componentInstance.viewMode()).toBe('full');
  });

  it('copies the optimized tex to the clipboard and flashes', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    const { fixture } = mount(makeAggregate({ latest_optimization: OPT }));
    await fixture.componentInstance.copyTex();
    expect(writeText).toHaveBeenCalledWith('optimized tex');
    expect(fixture.componentInstance.copyFlash()).toBe(true);
  });

  it('surfaces an error when clipboard write is denied', async () => {
    const writeText = vi.fn().mockRejectedValue(new Error('denied'));
    Object.assign(navigator, { clipboard: { writeText } });
    const { fixture } = mount(makeAggregate({ latest_optimization: OPT }));
    await fixture.componentInstance.copyTex();
    expect(fixture.componentInstance.downloadError()).toContain('Clipboard access denied');
  });

  it('downloads the optimized PDF', () => {
    const downloadCvPdf = vi.fn(() => of(new Blob(['pdf'])));
    const { fixture } = mount(makeAggregate({ latest_optimization: OPT }), { downloadCvPdf });
    fixture.componentInstance.downloadPdf();
    expect(downloadCvPdf).toHaveBeenCalledWith('app-1');
    expect(fixture.componentInstance.downloadingPdf()).toBe(false);
  });

  it('surfaces an error when PDF download fails', () => {
    const { fixture } = mount(makeAggregate({ latest_optimization: OPT }), {
      downloadCvPdf: () => throwError(() => ({ error: { detail: 'pdf boom' } })),
    });
    fixture.componentInstance.downloadPdf();
    expect(fixture.componentInstance.downloadError()).toBe('pdf boom');
    expect(fixture.componentInstance.downloadingPdf()).toBe(false);
  });

  it('downloads the original profile PDF with the selected language', () => {
    const downloadOriginalCvPdf = vi.fn(() => of(new Blob(['pdf'])));
    const { fixture } = mount(makeAggregate(), { downloadOriginalCvPdf });
    fixture.componentInstance.onLangChange({ target: { value: 'es' } } as unknown as Event);
    fixture.componentInstance.downloadOriginalPdf();
    expect(downloadOriginalCvPdf).toHaveBeenCalledWith('app-1', 'es');
    expect(fixture.componentInstance.downloadingOriginal()).toBe(false);
  });
});
