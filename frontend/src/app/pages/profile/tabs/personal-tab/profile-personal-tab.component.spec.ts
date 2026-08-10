import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';
import { ProfilePersonalTabComponent } from './profile-personal-tab.component';
import { ProfileService } from '../../../../core/services/profile.service';
import { makeProfile } from '../../testing/make-profile';

describe('ProfilePersonalTabComponent', () => {
  function mount(opts: { profiles?: Record<string, unknown> } = {}) {
    const profileService = {
      profiles: signal<Record<string, unknown>>(opts.profiles ?? {}),
      activeLanguage: signal('en'),
      profile: signal(opts.profiles?.['en'] ?? null),
      loaded: signal(true),
      getApplyProfile: () => of(null),
      updateManualFields: () => of(makeProfile()),
    };

    TestBed.configureTestingModule({
      imports: [ProfilePersonalTabComponent],
      providers: [provideRouter([]), { provide: ProfileService, useValue: profileService }],
    });
    const fixture = TestBed.createComponent(ProfilePersonalTabComponent);
    fixture.detectChanges();
    return { fixture, cmp: fixture.componentInstance };
  }

  it('hides the personal-details form until Edit is clicked, then swaps back on save/cancel', () => {
    const { fixture, cmp } = mount({ profiles: { en: makeProfile() } });
    const el = fixture.nativeElement as HTMLElement;

    // read-only card visible, form hidden by default
    expect(cmp.editingPersonal()).toBe(false);
    expect(el.querySelector('.details-grid')).not.toBeNull();
    expect(el.querySelector('app-manual-fields-form')).toBeNull();

    // clicking Edit reveals the form and hides the read-only grid
    const editBtn = [...el.querySelectorAll('button')].find(
      (b) => b.textContent?.trim() === 'Edit',
    )!;
    editBtn.click();
    fixture.detectChanges();
    expect(cmp.editingPersonal()).toBe(true);
    expect(el.querySelector('app-manual-fields-form')).not.toBeNull();
    expect(el.querySelector('.details-grid')).toBeNull();

    // saved/cancelled return to the read-only view
    cmp.editingPersonal.set(false);
    fixture.detectChanges();
    expect(el.querySelector('app-manual-fields-form')).toBeNull();
    expect(el.querySelector('.details-grid')).not.toBeNull();
  });

  it('shows the empty state instead of the details card when no CV has been parsed', () => {
    const { fixture } = mount();
    const el = fixture.nativeElement as HTMLElement;

    expect(el.querySelector('app-profile-required-empty-state')).not.toBeNull();
    expect(el.querySelector('.details-grid')).toBeNull();
  });

  it('no longer renders the cards that moved to their own tabs', () => {
    const { fixture } = mount({ profiles: { en: makeProfile() } });
    const el = fixture.nativeElement as HTMLElement;

    expect(el.querySelector('app-apply-profile-card')).toBeNull();
    expect(el.querySelector('app-portfolio-card')).toBeNull();
    expect(el.querySelector('app-network-card')).toBeNull();
    expect(el.querySelector('app-profile-setup-card')).toBeNull();
  });
});
