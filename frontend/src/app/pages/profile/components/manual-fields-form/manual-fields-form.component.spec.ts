import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import { ManualFieldsFormComponent } from './manual-fields-form.component';
import { ProfileService } from '../../../../core/services/profile.service';

function makeProfile(over: Partial<Record<string, unknown>> = {}) {
  return {
    id: 'p1',
    name: 'Ada',
    email: null,
    phone: null,
    location: null,
    sections: [],
    raw_tex: '',
    language: 'en',
    skills: [],
    linkedin_url: null,
    github_url: null,
    portfolio_url: null,
    ...over,
  };
}

describe('ManualFieldsFormComponent', () => {
  function mount(
    updateManualFields = vi.fn(() => of(makeProfile({ name: 'Ada Lovelace' }))),
  ) {
    TestBed.configureTestingModule({
      imports: [ManualFieldsFormComponent],
      providers: [{ provide: ProfileService, useValue: { updateManualFields } }],
    });
    const fixture = TestBed.createComponent(ManualFieldsFormComponent);
    fixture.componentRef.setInput('profile', makeProfile());
    fixture.detectChanges();
    return { fixture, cmp: fixture.componentInstance, updateManualFields };
  }

  it('save emits saved, refreshes the baseline, and flashes', () => {
    const { cmp, updateManualFields } = mount();
    const saved = vi.fn();
    cmp.saved.subscribe(saved);

    cmp.set('name', 'Grace Hopper');
    expect(cmp.isDirty()).toBe(true);
    cmp.save();

    expect(updateManualFields).toHaveBeenCalled();
    expect(saved).toHaveBeenCalledTimes(1);
    expect(cmp.savedFlash()).toBe(true);
    expect(cmp.isDirty()).toBe(false); // baseline updated to the saved profile
  });

  it('cancel resets the form and emits cancelled', () => {
    const { cmp } = mount();
    const cancelled = vi.fn();
    cmp.cancelled.subscribe(cancelled);

    cmp.set('name', 'Changed');
    expect(cmp.isDirty()).toBe(true);
    cmp.cancel();

    expect(cmp.isDirty()).toBe(false);
    expect(cancelled).toHaveBeenCalledTimes(1);
  });

  it('disables Save while the form is pristine (dirty-guard)', () => {
    const { fixture } = mount();
    const saveBtn = (fixture.nativeElement as HTMLElement).querySelector(
      'button[type="submit"]',
    ) as HTMLButtonElement;
    expect(saveBtn.disabled).toBe(true);
  });
});
