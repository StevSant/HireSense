import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { ProfileCvTabComponent } from './profile-cv-tab.component';
import { ProfileService } from '../../../../core/services/profile.service';
import { TranslateResponse } from '../../models/translate-response.model';
import { makeProfile } from '../../testing/make-profile';

describe('ProfileCvTabComponent', () => {
  function mount(
    opts: {
      profiles?: Record<string, unknown>;
      uploadFile?: () => unknown;
      loaded?: boolean;
    } = {},
  ) {
    const profileService = {
      profiles: signal<Record<string, unknown>>(opts.profiles ?? {}),
      activeLanguage: signal('en'),
      profile: signal(opts.profiles?.['en'] ?? null),
      loaded: signal(opts.loaded ?? true),
      uploadFile: opts.uploadFile ?? (() => of(makeProfile())),
      uploadCV: () => of(makeProfile()),
      translate: vi.fn(() =>
        of({
          profile: makeProfile({ id: 'p-es', language: 'es', machine_translated: true }),
          pdf_ok: true,
          compile_error: null,
        } as unknown as TranslateResponse),
      ),
      downloadCvPdf: vi.fn(() => of(new Blob(['%PDF'], { type: 'application/pdf' }))),
    };

    TestBed.configureTestingModule({
      imports: [ProfileCvTabComponent],
      providers: [provideRouter([]), { provide: ProfileService, useValue: profileService }],
    });
    const fixture = TestBed.createComponent(ProfileCvTabComponent);
    fixture.detectChanges();
    return { fixture, profileService, cmp: fixture.componentInstance };
  }

  it('derives its spinner from the shared loaded flag', () => {
    const { cmp } = mount({ loaded: false });
    expect(cmp.initialLoading()).toBe(true);
  });

  it('lists the uploaded languages once the profile is loaded (happy path)', () => {
    const { cmp } = mount({ profiles: { en: makeProfile() } });
    expect(cmp.initialLoading()).toBe(false);
    expect(cmp.uploadedLanguages()).toEqual(['en']);
  });

  it('surfaces an upload error and clears loading when uploadFile fails', () => {
    const { cmp } = mount({
      uploadFile: () => throwError(() => ({ error: { detail: 'bad file' } })),
    });

    cmp.selectedFile.set(new File(['x'], 'cv.pdf', { type: 'application/pdf' }));
    cmp.uploadFile();

    expect(cmp.error()).toBe('bad file');
    expect(cmp.loading()).toBe(false);
  });

  it('replaceCv pre-selects the active language and opens the upload form', () => {
    const { cmp } = mount({ profiles: { en: makeProfile() } });

    cmp.replaceCv();

    expect(cmp.showUploadForm()).toBe(true);
    expect(cmp.uploadIntent()).toBe('replace');
    expect(cmp.language()).toBe('en');
    expect(cmp.selectedFile()).toBeNull();
  });

  it('addAnotherLanguage marks the intent as add', () => {
    const { cmp } = mount({ profiles: { en: makeProfile() } });

    cmp.addAnotherLanguage();

    expect(cmp.showUploadForm()).toBe(true);
    expect(cmp.uploadIntent()).toBe('add');
    expect(cmp.language()).toBe('es');
  });

  it('calls translate with the other language', () => {
    const { cmp, profileService } = mount({ profiles: { en: makeProfile() } });

    cmp.translateToOther();

    expect(profileService.translate).toHaveBeenCalledWith('es');
  });

  it('surfaces the compiler error when the translated PDF does not compile', () => {
    const { cmp, profileService } = mount({ profiles: { en: makeProfile() } });
    profileService.translate = vi.fn(() =>
      of({
        profile: makeProfile({ id: 'p-es', language: 'es', machine_translated: true }),
        pdf_ok: false,
        compile_error: 'xelatex exited with code 1\nMissing \\begin{document}.',
      } as unknown as TranslateResponse),
    );

    cmp.translateToOther();

    expect(cmp.translateWarning()).not.toBe('');
    expect(cmp.translateCompileError()).toContain('Missing \\begin{document}');
  });

  it('downloads the PDF blob for a language', () => {
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    const { cmp, profileService } = mount({ profiles: { en: makeProfile() } });

    cmp.downloadPdf('en');

    expect(profileService.downloadCvPdf).toHaveBeenCalledWith('en');
    clickSpy.mockRestore();
  });
});
