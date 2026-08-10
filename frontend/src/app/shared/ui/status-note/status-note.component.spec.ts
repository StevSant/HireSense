import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { StatusNoteComponent } from './status-note.component';

@Component({
  selector: 'app-status-note-host',
  standalone: true,
  imports: [StatusNoteComponent],
  template: `
    <app-status-note>Loading…</app-status-note>
    <app-status-note><strong class="empty-label">No opportunities yet</strong></app-status-note>
  `,
})
class StatusNoteHostComponent {}

describe('StatusNoteComponent', () => {
  function mountNotes(): Element[] {
    TestBed.configureTestingModule({ imports: [StatusNoteHostComponent] });
    const fixture = TestBed.createComponent(StatusNoteHostComponent);
    fixture.detectChanges();
    return Array.from((fixture.nativeElement as HTMLElement).querySelectorAll('app-status-note'));
  }

  it('shows the text the caller projects into it', () => {
    const [loading] = mountNotes();

    expect(loading.textContent?.trim()).toBe('Loading…');
  });

  it('projects markup as-is instead of flattening it to text', () => {
    const [, empty] = mountNotes();

    const label = empty.querySelector('strong.empty-label');

    expect(label).not.toBeNull();
    expect(label?.textContent).toBe('No opportunities yet');
  });

  it('adds no wrapper element, so the caller owns the box around the note', () => {
    const [, empty] = mountNotes();

    const label = empty.querySelector('strong.empty-label');

    // The muted treatment lives on :host; a wrapper here would break parent
    // rules that space or target the note's direct children.
    expect(label?.parentElement).toBe(empty);
    expect(empty.children.length).toBe(1);
  });
});
