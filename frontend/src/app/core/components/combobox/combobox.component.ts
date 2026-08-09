import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  HostListener,
  computed,
  inject,
  input,
  output,
  signal,
} from '@angular/core';
import { ComboboxOption } from './combobox-option.model';

// Unique per instance so aria-activedescendant/aria-controls point at this
// combobox's own nodes when several are on the page.
let nextId = 0;

/**
 * Filtering single-select combobox following the WAI-ARIA 1.2 pattern
 * (editable combobox with list autocomplete).
 *
 * Use this only where the option list is long or grows with the data. Short
 * static enums (tone, language, status, sort order) should stay native
 * `<select>` — native wins on mobile and with assistive tech.
 */
@Component({
  selector: 'app-combobox',
  standalone: true,
  templateUrl: './combobox.component.html',
  styleUrl: './combobox.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ComboboxComponent {
  private host = inject(ElementRef<HTMLElement>);

  options = input.required<readonly ComboboxOption[]>();
  /** Currently selected option value; '' when nothing is chosen. */
  value = input<string>('');
  placeholder = input<string>('');
  /** Labels the text input for assistive tech when there is no visible <label>. */
  ariaLabel = input<string>('');
  /** Id of a visible <label> element, when the host renders one. */
  labelledBy = input<string>('');
  emptyText = input<string>('No matches');
  disabled = input<boolean>(false);

  valueChange = output<string>();
  /** Fires the first time the list is opened — hosts use it to lazy-load options. */
  opened = output<void>();

  readonly id = `combobox-${nextId++}`;

  open = signal(false);
  query = signal('');
  activeIndex = signal(-1);

  private hasOpened = false;

  selectedLabel = computed(() => {
    const current = this.value();
    return this.options().find((o) => o.value === current)?.label ?? '';
  });

  filtered = computed<readonly ComboboxOption[]>(() => {
    const q = this.query().trim().toLowerCase();
    const all = this.options();
    if (!q) return all;
    return all.filter((o) => o.label.toLowerCase().includes(q));
  });

  /** Typed text while filtering, the selected label otherwise. */
  displayValue = computed(() => (this.open() ? this.query() : this.selectedLabel()));

  activeOptionId = computed(() => {
    const i = this.activeIndex();
    return i >= 0 && i < this.filtered().length ? this.optionId(i) : null;
  });

  optionId(index: number): string {
    return `${this.id}-option-${index}`;
  }

  onInput(event: Event): void {
    this.query.set((event.target as HTMLInputElement).value);
    this.openList();
    // Filtering changes what row 0 is, so point at the first match again.
    this.activeIndex.set(this.filtered().length ? 0 : -1);
  }

  onFocus(): void {
    this.openList();
  }

  onToggle(): void {
    if (this.disabled()) return;
    if (this.open()) {
      this.close();
    } else {
      this.openList();
    }
  }

  onKeydown(event: KeyboardEvent): void {
    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault();
        if (!this.open()) {
          this.openList();
          return;
        }
        this.move(1);
        return;
      case 'ArrowUp':
        event.preventDefault();
        if (!this.open()) {
          this.openList();
          return;
        }
        this.move(-1);
        return;
      case 'Home':
        if (!this.open()) return;
        event.preventDefault();
        this.activeIndex.set(this.filtered().length ? 0 : -1);
        return;
      case 'End':
        if (!this.open()) return;
        event.preventDefault();
        this.activeIndex.set(this.filtered().length - 1);
        return;
      case 'Enter': {
        if (!this.open()) return;
        const option = this.filtered()[this.activeIndex()];
        if (option) {
          event.preventDefault();
          this.select(option);
        }
        return;
      }
      case 'Escape':
        if (!this.open()) return;
        event.preventDefault();
        this.close();
        return;
      case 'Tab':
        // Let focus move on, but never leave a half-typed filter on screen.
        this.close();
        return;
    }
  }

  select(option: ComboboxOption): void {
    this.valueChange.emit(option.value);
    this.close();
  }

  @HostListener('document:click', ['$event'])
  onDocumentClick(event: MouseEvent): void {
    if (!this.open()) return;
    if (!this.host.nativeElement.contains(event.target as Node)) {
      this.close();
    }
  }

  private openList(): void {
    if (this.disabled() || this.open()) return;
    this.open.set(true);
    this.activeIndex.set(this.indexOfSelected());
    if (!this.hasOpened) {
      this.hasOpened = true;
      this.opened.emit();
    }
  }

  private close(): void {
    this.open.set(false);
    this.query.set('');
    this.activeIndex.set(-1);
  }

  private indexOfSelected(): number {
    const current = this.value();
    const i = this.filtered().findIndex((o) => o.value === current);
    return i >= 0 ? i : this.filtered().length ? 0 : -1;
  }

  private move(delta: number): void {
    const count = this.filtered().length;
    if (!count) {
      this.activeIndex.set(-1);
      return;
    }
    const next = this.activeIndex() + delta;
    // Wrap, so ArrowUp from the top lands on the last option.
    this.activeIndex.set(((next % count) + count) % count);
  }
}
