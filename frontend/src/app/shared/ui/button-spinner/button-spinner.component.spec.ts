import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { ButtonSpinnerComponent } from './button-spinner.component';

@Component({
  selector: 'app-spinner-host',
  standalone: true,
  imports: [ButtonSpinnerComponent],
  template: `<button type="button">Save<app-button-spinner /></button>`,
})
class SpinnerHostComponent {}

describe('ButtonSpinnerComponent', () => {
  function mount(): HTMLElement {
    TestBed.configureTestingModule({ imports: [SpinnerHostComponent] });
    const fixture = TestBed.createComponent(SpinnerHostComponent);
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  it('leaves the label of the button it sits in untouched', () => {
    const host = mount();

    const button = host.querySelector('button');

    // The spinner is decorative: it must not end up in the button's name.
    expect(button?.textContent?.trim()).toBe('Save');
  });

  it('renders as a single empty element carrying no content of its own', () => {
    const host = mount();

    const spinner = host.querySelector('app-button-spinner');

    expect(spinner).not.toBeNull();
    expect(spinner?.children.length).toBe(0);
    expect(spinner?.textContent).toBe('');
  });
});
