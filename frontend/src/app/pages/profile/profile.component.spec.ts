import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { ProfileComponent } from './profile.component';
import { ProfileService } from '../../core/services/profile.service';
import { makeProfile } from './testing/make-profile';

/**
 * The shell only owns the one-time bootstrap; the tabs are routed children and
 * are covered by their own specs.
 */
describe('ProfileComponent (shell)', () => {
  function mount(
    opts: {
      profiles?: Record<string, unknown>;
      listProfiles?: () => unknown;
      getCurrentProfile?: () => unknown;
    } = {},
  ) {
    const profileService = {
      profiles: signal<Record<string, unknown>>(opts.profiles ?? {}),
      activeLanguage: signal('en'),
      profile: signal(opts.profiles?.['en'] ?? null),
      loaded: signal(false),
      listProfiles: opts.listProfiles ?? (() => of(Object.values(opts.profiles ?? {}))),
      getCurrentProfile: opts.getCurrentProfile ?? (() => of(makeProfile())),
    };

    TestBed.configureTestingModule({
      imports: [ProfileComponent],
      providers: [provideRouter([]), { provide: ProfileService, useValue: profileService }],
    });
    const fixture = TestBed.createComponent(ProfileComponent);
    fixture.detectChanges();
    return { fixture, profileService };
  }

  it('marks the profile loaded after listProfiles succeeds (happy path)', () => {
    const listProfiles = vi.fn(() => of([makeProfile()]));
    const { profileService } = mount({ profiles: { en: makeProfile() }, listProfiles });

    expect(listProfiles).toHaveBeenCalled();
    expect(profileService.loaded()).toBe(true);
  });

  it('falls back to getCurrentProfile then marks loaded when listProfiles fails', () => {
    const getCurrentProfile = vi.fn(() => of(makeProfile()));
    const { profileService } = mount({
      listProfiles: () => throwError(() => new Error('boom')),
      getCurrentProfile,
    });

    expect(getCurrentProfile).toHaveBeenCalled();
    expect(profileService.loaded()).toBe(true);
  });

  it('marks loaded even when both fetches fail, so tabs stop spinning (error state)', () => {
    const { profileService } = mount({
      listProfiles: () => throwError(() => new Error('boom')),
      getCurrentProfile: () => throwError(() => new Error('boom2')),
    });

    expect(profileService.loaded()).toBe(true);
  });

  it('renders the routed tab outlet rather than a hand-rolled tab bar', () => {
    const { fixture } = mount({ profiles: { en: makeProfile() } });
    const el = fixture.nativeElement as HTMLElement;

    expect(el.querySelector('router-outlet')).not.toBeNull();
    expect(el.querySelector('.page-tabs')).toBeNull();
  });
});
