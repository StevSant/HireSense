import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';
import { createSortState } from '../../utils/sort-state';
import { SortableHeaderComponent } from './sortable-header.component';

type F = 'match' | 'title';

@Component({
  standalone: true,
  imports: [SortableHeaderComponent],
  template: `<table><thead><tr>
    <th appSortHeader [state]="state" field="match" (sorted)="count = count + 1">Match</th>
    <th appSortHeader [state]="state" field="title" (sorted)="count = count + 1">Title</th>
  </tr></thead></table>`,
})
class HostComponent {
  state = createSortState<F>('match', 'desc', ['title']);
  count = 0;
}

describe('SortableHeaderComponent', () => {
  it('marks the active column with aria-sort and toggles on click', () => {
    const fixture = TestBed.createComponent(HostComponent);
    fixture.detectChanges();
    const ths: HTMLTableCellElement[] = Array.from(
      fixture.nativeElement.querySelectorAll('th'),
    );
    expect(ths[0].getAttribute('aria-sort')).toBe('descending');
    expect(ths[1].getAttribute('aria-sort')).toBe('none');

    ths[0].querySelector('button')!.click();
    fixture.detectChanges();
    expect(ths[0].getAttribute('aria-sort')).toBe('ascending');

    ths[1].querySelector('button')!.click();
    fixture.detectChanges();
    expect(ths[1].getAttribute('aria-sort')).toBe('ascending'); // text default asc
    expect(ths[0].getAttribute('aria-sort')).toBe('none');
  });

  it('emits the sorted output on each click', () => {
    const fixture = TestBed.createComponent(HostComponent);
    fixture.detectChanges();
    const button = fixture.nativeElement.querySelector('th button') as HTMLButtonElement;
    button.click();
    button.click();
    fixture.detectChanges();
    expect(fixture.componentInstance.count).toBe(2);
  });
});
