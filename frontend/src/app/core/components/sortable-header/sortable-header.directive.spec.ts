import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';
import { createSortState } from '../../utils/sort-state';
import { SortableHeaderDirective } from './sortable-header.directive';

type F = 'match' | 'title';

@Component({
  standalone: true,
  imports: [SortableHeaderDirective],
  template: `<table>
    <thead>
      <tr>
        <th appSortHeader [state]="state" field="match" (sorted)="count = count + 1">Match</th>
        <th appSortHeader [state]="state" field="title" (sorted)="count = count + 1">Title</th>
      </tr>
    </thead>
  </table>`,
})
class HostComponent {
  state = createSortState<F>('match', 'desc', ['title']);
  count = 0;
}

describe('SortableHeaderDirective', () => {
  it('marks the active column with aria-sort and toggles on click', () => {
    const fixture = TestBed.createComponent(HostComponent);
    fixture.detectChanges();
    const ths: HTMLTableCellElement[] = Array.from(fixture.nativeElement.querySelectorAll('th'));
    expect(ths[0].getAttribute('aria-sort')).toBe('descending');
    expect(ths[1].getAttribute('aria-sort')).toBe('none');

    ths[0].click();
    fixture.detectChanges();
    expect(ths[0].getAttribute('aria-sort')).toBe('ascending');

    ths[1].click();
    fixture.detectChanges();
    expect(ths[1].getAttribute('aria-sort')).toBe('ascending'); // text default asc
    expect(ths[0].getAttribute('aria-sort')).toBe('none');
  });

  it('is keyboard focusable', () => {
    const fixture = TestBed.createComponent(HostComponent);
    fixture.detectChanges();
    const th = fixture.nativeElement.querySelector('th') as HTMLTableCellElement;
    expect(th.getAttribute('tabindex')).toBe('0');
  });

  it('emits the sorted output on each activation', () => {
    const fixture = TestBed.createComponent(HostComponent);
    fixture.detectChanges();
    const th = fixture.nativeElement.querySelector('th') as HTMLTableCellElement;
    th.click();
    th.click();
    fixture.detectChanges();
    expect(fixture.componentInstance.count).toBe(2);
  });
});
