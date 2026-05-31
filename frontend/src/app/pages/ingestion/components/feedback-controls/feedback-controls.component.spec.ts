import { TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';
import { FeedbackControlsComponent } from './feedback-controls.component';
import { PreferenceService } from '../../../../core/services/preference.service';

describe('FeedbackControlsComponent', () => {
  let submitFeedback: ReturnType<typeof vi.fn>;

  beforeEach(async () => {
    submitFeedback = vi.fn().mockReturnValue(
      of({ id: 's', job_id: 'j1', kind: 'thumbs_up', created_at: null }),
    );
    await TestBed.configureTestingModule({
      imports: [FeedbackControlsComponent],
      providers: [{ provide: PreferenceService, useValue: { submitFeedback } }],
    }).compileComponents();
  });

  function mount(jobId = 'j1') {
    const fixture = TestBed.createComponent(FeedbackControlsComponent);
    fixture.componentRef.setInput('jobId', jobId);
    fixture.detectChanges();
    return fixture;
  }

  it('renders four feedback buttons', () => {
    const fixture = mount();
    const buttons = fixture.nativeElement.querySelectorAll('button.fb-btn');
    expect(buttons.length).toBe(4);
  });

  it('calls submitFeedback with the clicked kind', () => {
    const fixture = mount();
    const buttons = fixture.nativeElement.querySelectorAll('button.fb-btn');
    (buttons[0] as HTMLButtonElement).click();
    expect(submitFeedback).toHaveBeenCalledWith('j1', 'thumbs_up');
  });

  it('emits feedbackSubmitted on success', () => {
    const fixture = mount();
    let emitted: string | null = null;
    fixture.componentInstance.feedbackSubmitted.subscribe((k) => (emitted = k));
    (fixture.nativeElement.querySelector('button.fb-btn') as HTMLButtonElement).click();
    expect(emitted).toBe('thumbs_up');
    expect(fixture.componentInstance.lastSent()).toBe('thumbs_up');
  });

  it('shows error affordance and does not emit on failure', () => {
    submitFeedback.mockReturnValue(throwError(() => new Error('fail')));
    const fixture = mount();
    let emitted = false;
    fixture.componentInstance.feedbackSubmitted.subscribe(() => (emitted = true));
    (fixture.nativeElement.querySelector('button.fb-btn') as HTMLButtonElement).click();
    fixture.detectChanges();
    expect(fixture.componentInstance.failed()).toBe(true);
    expect(emitted).toBe(false);
    expect(fixture.nativeElement.querySelector('.fb-error')).not.toBeNull();
  });
});
