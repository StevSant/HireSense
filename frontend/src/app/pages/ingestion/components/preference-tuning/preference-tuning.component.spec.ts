import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import { PreferenceTuningComponent } from './preference-tuning.component';
import { PreferenceService } from '../../../../core/services/preference.service';

const ACTIVE_EXPLAIN = {
  active: true,
  total_signals: 3,
  positive_count: 2,
  negative_count: 1,
  counts_by_kind: { thumbs_up: 2, thumbs_down: 1 },
  drift_magnitude: 0.42,
};

describe('PreferenceTuningComponent', () => {
  let explain: ReturnType<typeof vi.fn>;
  let reset: ReturnType<typeof vi.fn>;

  beforeEach(async () => {
    explain = vi.fn().mockReturnValue(of(ACTIVE_EXPLAIN));
    reset = vi.fn().mockReturnValue(of(undefined));
    await TestBed.configureTestingModule({
      imports: [PreferenceTuningComponent],
      providers: [{ provide: PreferenceService, useValue: { explain, reset } }],
    }).compileComponents();
  });

  function mount() {
    const fixture = TestBed.createComponent(PreferenceTuningComponent);
    fixture.detectChanges();
    return fixture;
  }

  it('loads the explanation when expanded', () => {
    const fixture = mount();
    fixture.componentInstance.toggle();
    fixture.detectChanges();
    expect(explain).toHaveBeenCalled();
    expect(fixture.componentInstance.explanation()?.total_signals).toBe(3);
  });

  it('reset calls the service when confirmed', () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    const fixture = mount();
    fixture.componentInstance.reset();
    expect(reset).toHaveBeenCalled();
  });

  it('reset does nothing when cancelled', () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false);
    const fixture = mount();
    fixture.componentInstance.reset();
    expect(reset).not.toHaveBeenCalled();
  });
});
