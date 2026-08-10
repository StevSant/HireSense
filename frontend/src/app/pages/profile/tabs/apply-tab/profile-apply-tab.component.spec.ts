import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';
import { ProfileApplyTabComponent } from './profile-apply-tab.component';
import { ProfileService } from '../../../../core/services/profile.service';
import { makeProfile } from '../../testing/make-profile';

describe('ProfileApplyTabComponent', () => {
  function mount(opts: { profiles?: Record<string, unknown> } = {}) {
    const profileService = {
      profiles: signal<Record<string, unknown>>(opts.profiles ?? {}),
      activeLanguage: signal('en'),
      profile: signal(opts.profiles?.['en'] ?? null),
      loaded: signal(true),
      getApplyProfile: () => of(null),
      setApplyProfile: () => of(makeProfile()),
    };

    TestBed.configureTestingModule({
      imports: [ProfileApplyTabComponent],
      providers: [provideRouter([]), { provide: ProfileService, useValue: profileService }],
    });
    const fixture = TestBed.createComponent(ProfileApplyTabComponent);
    fixture.detectChanges();
    return { fixture };
  }

  it('renders the apply-profile form when a profile exists', () => {
    const { fixture } = mount({ profiles: { en: makeProfile() } });
    const el = fixture.nativeElement as HTMLElement;

    expect(el.querySelector('app-apply-profile-card')).not.toBeNull();
    expect(el.querySelector('app-profile-required-empty-state')).toBeNull();
  });

  it('falls back to the empty state when no CV has been parsed', () => {
    const { fixture } = mount();
    const el = fixture.nativeElement as HTMLElement;

    expect(el.querySelector('app-apply-profile-card')).toBeNull();
    expect(el.querySelector('app-profile-required-empty-state')).not.toBeNull();
  });
});
