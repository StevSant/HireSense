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
    location: null,
    remote_modality: null,
    salary_range: null,
    source: null,
    posted_date: null,
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

const BLOCKED_READINESS = {
  ready: false,
  supported_changes: [],
  blocked_changes: [
    {
      change: {
        section_name: 'SUMMARY',
        original: 'Built APIs',
        optimized: 'Built Kubernetes APIs',
        reason: 'Match the role',
      },
      reason: 'unsupported_job_skill' as const,
    },
  ],
};

describe('CvTabComponent', () => {
  let runnerRun: ReturnType<typeof vi.fn>;
  let runningId: ReturnType<typeof signal<string | null>>;
  let lastError: ReturnType<typeof signal<string>>;

  function mount(
    aggregate = makeAggregate(),
    service: Record<string, unknown> = {},
    readiness: typeof BLOCKED_READINESS | null = null,
  ) {
    runnerRun = vi.fn();
    runningId = signal<string | null>(null);
    lastError = signal('');
    const runner = {
      run: runnerRun,
      isRunning: (id: string) => runningId() === id,
      lastError,
      lastReadiness: (id: string) => (id === 'app-1' ? readiness : null),
    };
    const svc = {
      downloadCvPdf: () => of(new Blob(['cv'])),
      downloadOriginalCvPdf: () => of(new Blob(['cv'])),
      fetchCvPdf: () => of(new Blob(['pdf'])),
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

  it('explains blocked claims from the latest optimization response', () => {
    const { fixture } = mount(makeAggregate({ latest_optimization: OPT }), {}, BLOCKED_READINESS);

    expect(fixture.nativeElement.textContent).toContain('1 claim needs review');
    expect(fixture.nativeElement.textContent).toContain('Kubernetes APIs');
    expect(fixture.nativeElement.textContent).toContain('not evidenced in your CV');
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

  function showPreview(fixture: ReturnType<typeof TestBed.createComponent<CvTabComponent>>) {
    fixture.componentInstance.togglePreviewVisible();
    fixture.detectChanges();
  }

  it('keeps the preview hidden by default and only compiles once shown', () => {
    const fetchCvPdf = vi.fn(() => of(new Blob(['pdf'])));
    const { fixture } = mount(makeAggregate({ latest_optimization: OPT }), { fetchCvPdf });
    expect(fixture.componentInstance.previewVisible()).toBe(false);
    expect(fetchCvPdf).not.toHaveBeenCalled();
    showPreview(fixture);
    expect(fetchCvPdf).toHaveBeenCalledTimes(1);
  });

  it('defaults the inline preview to the optimized variant when an optimization exists', () => {
    const fetchCvPdf = vi.fn(() => of(new Blob(['pdf'])));
    const { fixture } = mount(makeAggregate({ latest_optimization: OPT }), { fetchCvPdf });
    showPreview(fixture);
    expect(fixture.componentInstance.effectivePreviewSource()).toBe('optimized');
    expect(fetchCvPdf).toHaveBeenCalledWith('app-1', { original: false, language: 'en' });
    expect(fixture.componentInstance.previewUrl()).not.toBeNull();
  });

  it('offers only the Original preview when no optimization exists', () => {
    const fetchCvPdf = vi.fn(() => of(new Blob(['pdf'])));
    const { fixture } = mount(makeAggregate(), { fetchCvPdf });
    showPreview(fixture);
    expect(fixture.componentInstance.optimization()).toBeNull();
    expect(fixture.componentInstance.effectivePreviewSource()).toBe('original');
    // Selecting optimized is inert without an optimization to render.
    fixture.componentInstance.setPreviewSource('optimized');
    expect(fixture.componentInstance.effectivePreviewSource()).toBe('original');
    expect(fetchCvPdf).toHaveBeenCalledWith('app-1', { original: true, language: 'en' });
  });

  it('switches the preview source and fetches the matching PDF variant', () => {
    const fetchCvPdf = vi.fn(() => of(new Blob(['pdf'])));
    const { fixture } = mount(makeAggregate({ latest_optimization: OPT }), { fetchCvPdf });
    showPreview(fixture);
    fetchCvPdf.mockClear();
    fixture.componentInstance.setPreviewSource('original');
    fixture.detectChanges();
    expect(fetchCvPdf).toHaveBeenCalledWith('app-1', { original: true, language: 'en' });
  });

  it('serves already-compiled variants from cache instead of recompiling', () => {
    const fetchCvPdf = vi.fn(() => of(new Blob(['pdf'])));
    const { fixture } = mount(makeAggregate({ latest_optimization: OPT }), { fetchCvPdf });
    showPreview(fixture);
    fixture.componentInstance.setPreviewSource('original');
    fixture.detectChanges();
    expect(fetchCvPdf).toHaveBeenCalledTimes(2);
    // Toggling back to a variant that was already compiled must not refetch.
    fixture.componentInstance.setPreviewSource('optimized');
    fixture.detectChanges();
    fixture.componentInstance.setPreviewSource('original');
    fixture.detectChanges();
    expect(fetchCvPdf).toHaveBeenCalledTimes(2);
    expect(fixture.componentInstance.previewUrl()).not.toBeNull();
  });

  it('reuses the cache when the preview is hidden and shown again', () => {
    const fetchCvPdf = vi.fn(() => of(new Blob(['pdf'])));
    const { fixture } = mount(makeAggregate({ latest_optimization: OPT }), { fetchCvPdf });
    showPreview(fixture);
    expect(fetchCvPdf).toHaveBeenCalledTimes(1);
    fixture.componentInstance.togglePreviewVisible();
    fixture.detectChanges();
    showPreview(fixture);
    expect(fetchCvPdf).toHaveBeenCalledTimes(1);
  });

  it('passes the CV language through to the preview fetch', () => {
    const fetchCvPdf = vi.fn(() => of(new Blob(['pdf'])));
    const { fixture } = mount(makeAggregate(), { fetchCvPdf });
    showPreview(fixture);
    fetchCvPdf.mockClear();
    fixture.componentInstance.onLangChange({ target: { value: 'es' } } as unknown as Event);
    fixture.detectChanges();
    expect(fetchCvPdf).toHaveBeenCalledWith('app-1', { original: true, language: 'es' });
  });

  it('surfaces a compile error in the preview area from a JSON error body', async () => {
    const fetchCvPdf = vi.fn(() =>
      throwError(() => ({ error: { detail: 'LaTeX compile failed: boom' } })),
    );
    const { fixture } = mount(makeAggregate({ latest_optimization: OPT }), { fetchCvPdf });
    showPreview(fixture);
    await fixture.whenStable();
    expect(fixture.componentInstance.previewError()).toContain('LaTeX compile failed');
    expect(fixture.componentInstance.previewUrl()).toBeNull();
  });

  it('surfaces a compile error when the error body is a Blob', async () => {
    const blob = new Blob([JSON.stringify({ detail: 'LaTeX compile failed: blob' })], {
      type: 'application/json',
    });
    const fetchCvPdf = vi.fn(() => throwError(() => ({ error: blob })));
    const { fixture } = mount(makeAggregate({ latest_optimization: OPT }), { fetchCvPdf });
    showPreview(fixture);
    // Reading the Blob body is async; poll until the error surfaces.
    for (let i = 0; i < 20 && !fixture.componentInstance.previewError(); i++) {
      await new Promise((resolve) => setTimeout(resolve));
    }
    expect(fixture.componentInstance.previewError()).toContain('LaTeX compile failed');
  });
});
