import { TestBed } from '@angular/core/testing';
import { ComboboxComponent } from './combobox.component';
import { ComboboxOption } from './combobox-option.model';

const OPTIONS: ComboboxOption[] = [
  { value: 'a', label: 'Remotive' },
  { value: 'b', label: 'Jobicy' },
  { value: 'c', label: 'GetOnBoard' },
];

describe('ComboboxComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [ComboboxComponent] }).compileComponents();
  });

  function mount(opts: { options?: ComboboxOption[]; value?: string } = {}) {
    const fixture = TestBed.createComponent(ComboboxComponent);
    fixture.componentRef.setInput('options', opts.options ?? OPTIONS);
    fixture.componentRef.setInput('value', opts.value ?? '');
    fixture.detectChanges();
    return fixture;
  }

  const input = (f: ReturnType<typeof mount>) =>
    f.nativeElement.querySelector('input.combobox-input') as HTMLInputElement;
  const listbox = (f: ReturnType<typeof mount>) =>
    f.nativeElement.querySelector('.combobox-listbox') as HTMLElement;
  const optionEls = (f: ReturnType<typeof mount>) =>
    [...f.nativeElement.querySelectorAll('.combobox-option')] as HTMLElement[];

  function key(f: ReturnType<typeof mount>, k: string) {
    input(f).dispatchEvent(
      new KeyboardEvent('keydown', { key: k, bubbles: true, cancelable: true }),
    );
    f.detectChanges();
  }

  function type(f: ReturnType<typeof mount>, text: string) {
    input(f).value = text;
    input(f).dispatchEvent(new Event('input'));
    f.detectChanges();
  }

  it('exposes the ARIA combobox contract', () => {
    const fixture = mount();
    const el = input(fixture);

    expect(el.getAttribute('role')).toBe('combobox');
    expect(el.getAttribute('aria-expanded')).toBe('false');
    expect(el.getAttribute('aria-autocomplete')).toBe('list');
    expect(el.getAttribute('aria-controls')).toBe(listbox(fixture).id);
    expect(listbox(fixture).getAttribute('role')).toBe('listbox');
  });

  it('starts closed and opens on focus', () => {
    const fixture = mount();
    expect(listbox(fixture).hidden).toBe(true);

    input(fixture).dispatchEvent(new Event('focus'));
    fixture.detectChanges();

    expect(listbox(fixture).hidden).toBe(false);
    expect(input(fixture).getAttribute('aria-expanded')).toBe('true');
  });

  it('shows the selected label when closed', () => {
    const fixture = mount({ value: 'b' });
    expect(input(fixture).value).toBe('Jobicy');
  });

  it('filters options by substring, case-insensitively', () => {
    const fixture = mount();
    type(fixture, 'board');

    expect(optionEls(fixture).map((o) => o.textContent?.trim())).toEqual(['GetOnBoard']);
  });

  it('renders the empty text when nothing matches', () => {
    const fixture = mount();
    type(fixture, 'zzz');

    expect(optionEls(fixture)).toHaveLength(0);
    expect(fixture.nativeElement.querySelector('.combobox-empty')).not.toBeNull();
  });

  it('moves the active option with the arrow keys and tracks aria-activedescendant', () => {
    const fixture = mount();
    key(fixture, 'ArrowDown'); // opens
    expect(input(fixture).getAttribute('aria-activedescendant')).toBe(optionEls(fixture)[0].id);

    key(fixture, 'ArrowDown');
    expect(input(fixture).getAttribute('aria-activedescendant')).toBe(optionEls(fixture)[1].id);

    key(fixture, 'ArrowUp');
    expect(input(fixture).getAttribute('aria-activedescendant')).toBe(optionEls(fixture)[0].id);
  });

  it('wraps from the first option to the last on ArrowUp', () => {
    const fixture = mount();
    key(fixture, 'ArrowDown');
    key(fixture, 'ArrowUp');

    expect(input(fixture).getAttribute('aria-activedescendant')).toBe(optionEls(fixture)[2].id);
  });

  it('emits the active option value on Enter and closes', () => {
    const fixture = mount();
    let emitted: string | null = null;
    fixture.componentInstance.valueChange.subscribe((v) => (emitted = v));

    key(fixture, 'ArrowDown');
    key(fixture, 'ArrowDown');
    key(fixture, 'Enter');

    expect(emitted).toBe('b');
    expect(listbox(fixture).hidden).toBe(true);
  });

  it('emits on click and opens with the chosen option active', () => {
    const fixture = mount({ value: 'c' });
    let emitted: string | null = null;
    fixture.componentInstance.valueChange.subscribe((v) => (emitted = v));

    input(fixture).dispatchEvent(new Event('focus'));
    fixture.detectChanges();
    expect(optionEls(fixture)[2].getAttribute('aria-selected')).toBe('true');

    optionEls(fixture)[0].click();
    fixture.detectChanges();

    expect(emitted).toBe('a');
  });

  it('moves aria-selected with the active option, not the committed value', () => {
    const fixture = mount({ value: 'a' });

    input(fixture).dispatchEvent(new Event('focus'));
    fixture.detectChanges();
    // Opens on the committed value, so active and selected coincide.
    expect(optionEls(fixture)[0].getAttribute('aria-selected')).toBe('true');

    key(fixture, 'ArrowDown');

    // aria-selected follows aria-activedescendant; the old row must clear it,
    // otherwise a screen reader never announces the row being arrowed onto.
    const els = optionEls(fixture);
    expect(input(fixture).getAttribute('aria-activedescendant')).toBe(els[1].id);
    expect(els[1].getAttribute('aria-selected')).toBe('true');
    expect(els[0].getAttribute('aria-selected')).toBe('false');
  });

  it('keeps focus on the input when an option is picked with the mouse', () => {
    const fixture = mount();
    // Attached to the document so focus assertions are meaningful.
    document.body.appendChild(fixture.nativeElement);

    input(fixture).focus();
    fixture.detectChanges();
    expect(document.activeElement).toBe(input(fixture));

    const mousedown = new MouseEvent('mousedown', { bubbles: true, cancelable: true });
    optionEls(fixture)[1].dispatchEvent(mousedown);
    fixture.detectChanges();

    // preventDefault on mousedown is what stops the option from taking focus.
    expect(mousedown.defaultPrevented).toBe(true);
    expect(document.activeElement).toBe(input(fixture));

    fixture.nativeElement.remove();
  });

  it('closes on Escape without emitting, and restores the selected label', () => {
    const fixture = mount({ value: 'b' });
    let emitted = false;
    fixture.componentInstance.valueChange.subscribe(() => (emitted = true));

    type(fixture, 'remo');
    key(fixture, 'Escape');

    expect(emitted).toBe(false);
    expect(listbox(fixture).hidden).toBe(true);
    expect(input(fixture).value).toBe('Jobicy');
  });

  it('closes when a click lands outside the component', () => {
    const fixture = mount();
    input(fixture).dispatchEvent(new Event('focus'));
    fixture.detectChanges();
    expect(listbox(fixture).hidden).toBe(false);

    document.body.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    fixture.detectChanges();

    expect(listbox(fixture).hidden).toBe(true);
  });

  it('emits opened once so hosts can lazy-load their options', () => {
    const fixture = mount();
    let opens = 0;
    fixture.componentInstance.opened.subscribe(() => opens++);

    input(fixture).dispatchEvent(new Event('focus'));
    fixture.detectChanges();
    key(fixture, 'Escape');
    input(fixture).dispatchEvent(new Event('focus'));
    fixture.detectChanges();

    expect(opens).toBe(1);
  });

  it('does not open when disabled', () => {
    const fixture = mount();
    fixture.componentRef.setInput('disabled', true);
    fixture.detectChanges();

    input(fixture).dispatchEvent(new Event('focus'));
    fixture.detectChanges();

    expect(listbox(fixture).hidden).toBe(true);
  });
});
