import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { ProfileComponent } from './profile.component';
import { ProfileService } from '../../core/services/profile.service';
import { ApplicationsService } from '../../core/services/applications.service';
import { CoverLetterTemplatesService } from '../../core/services/cover-letter-templates.service';
import { AuthService } from '../../core/services/auth.service';

function makeProfile(over: Partial<Record<string, unknown>> = {}) {
  return {
    id: 'p-en',
    name: 'Ada Lovelace',
    email: null,
    phone: null,
    location: null,
    sections: [],
    raw_tex: '',
    language: 'en',
    skills: ['python'],
    linkedin_url: null,
    github_url: null,
    portfolio_url: null,
    ...over,
  };
}

describe('ProfileComponent', () => {
  function mount(opts: {
    profiles?: Record<string, unknown>;
    listProfiles?: () => unknown;
    getCurrentProfile?: () => unknown;
  } = {}) {
    const profiles = signal<Record<string, unknown>>(opts.profiles ?? {});
    const activeLanguage = signal('en');
    const profileService = {
      profiles,
      activeLanguage,
      profile: signal(opts.profiles?.['en'] ?? null),
      listProfiles: opts.listProfiles ?? (() => of(Object.values(opts.profiles ?? {}))),
      getCurrentProfile: opts.getCurrentProfile ?? (() => of(makeProfile())),
      uploadFile: () => of(makeProfile()),
      uploadCV: () => of(makeProfile()),
    };

    TestBed.configureTestingModule({
      imports: [ProfileComponent],
      providers: [
        provideRouter([]),
        { provide: ProfileService, useValue: profileService },
        { provide: ApplicationsService, useValue: { listCoverLetters: () => of([]) } },
        { provide: CoverLetterTemplatesService, useValue: { list: () => of([]) } },
        { provide: AuthService, useValue: { me: () => of({ username: 'ada-user', role: 'admin' }), logout: () => {} } },
      ],
    });
    const fixture = TestBed.createComponent(ProfileComponent);
    fixture.detectChanges();
    return { fixture, profileService };
  }

  it('clears initialLoading after listProfiles succeeds (happy path)', () => {
    const listProfiles = vi.fn(() => of([makeProfile()]));
    const { fixture } = mount({ profiles: { en: makeProfile() }, listProfiles });
    const cmp = fixture.componentInstance;

    expect(listProfiles).toHaveBeenCalled();
    expect(cmp.initialLoading()).toBe(false);
    expect(cmp.uploadedLanguages()).toEqual(['en']);
  });

  it('falls back to getCurrentProfile then clears initialLoading when listProfiles fails', () => {
    const getCurrentProfile = vi.fn(() => of(makeProfile()));
    const { fixture } = mount({
      listProfiles: () => throwError(() => new Error('boom')),
      getCurrentProfile,
    });
    const cmp = fixture.componentInstance;

    expect(getCurrentProfile).toHaveBeenCalled();
    expect(cmp.initialLoading()).toBe(false);
  });

  it('clears initialLoading even when both fetches fail (error state)', () => {
    const { fixture } = mount({
      listProfiles: () => throwError(() => new Error('boom')),
      getCurrentProfile: () => throwError(() => new Error('boom2')),
    });

    expect(fixture.componentInstance.initialLoading()).toBe(false);
  });

  it('surfaces an upload error and clears loading when uploadFile fails', () => {
    const profiles = signal<Record<string, unknown>>({});
    const profileService = {
      profiles,
      activeLanguage: signal('en'),
      profile: signal(null),
      listProfiles: () => of([]),
      getCurrentProfile: () => of(makeProfile()),
      uploadFile: () => throwError(() => ({ error: { detail: 'bad file' } })),
      uploadCV: () => of(makeProfile()),
    };
    TestBed.configureTestingModule({
      imports: [ProfileComponent],
      providers: [
        provideRouter([]),
        { provide: ProfileService, useValue: profileService },
        { provide: ApplicationsService, useValue: { listCoverLetters: () => of([]) } },
        { provide: CoverLetterTemplatesService, useValue: { list: () => of([]) } },
      ],
    });
    const fixture = TestBed.createComponent(ProfileComponent);
    fixture.detectChanges();
    const cmp = fixture.componentInstance;

    cmp.selectedFile.set(new File(['x'], 'cv.pdf', { type: 'application/pdf' }));
    cmp.uploadFile();

    expect(cmp.error()).toBe('bad file');
    expect(cmp.loading()).toBe(false);
  });

  it('shows the Account tab content when the account tab is active', () => {
    const { fixture } = mount({ profiles: { en: makeProfile() } });
    const cmp = fixture.componentInstance;

    cmp.pageTab.set('account');
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('ada-user');
  });

  it('replaceCv pre-selects the active language and opens the upload form', () => {
    const { fixture, profileService } = mount({ profiles: { en: makeProfile() } });
    const cmp = fixture.componentInstance;
    (profileService.activeLanguage as { set: (v: string) => void }).set('en');

    cmp.replaceCv();

    expect(cmp.showUploadForm()).toBe(true);
    expect(cmp.uploadIntent()).toBe('replace');
    expect(cmp.language()).toBe('en');
    expect(cmp.selectedFile()).toBeNull();
  });

  it('addAnotherLanguage marks the intent as add', () => {
    const { fixture } = mount({ profiles: { en: makeProfile() } });
    const cmp = fixture.componentInstance;

    cmp.addAnotherLanguage();

    expect(cmp.showUploadForm()).toBe(true);
    expect(cmp.uploadIntent()).toBe('add');
  });
});
