import { describe, expect, it } from 'vitest';
import { createSortState } from './sort-state';

type F = 'match' | 'posted' | 'title';

describe('createSortState', () => {
  it('exposes the initial field, direction and token', () => {
    const s = createSortState<F>('match', 'desc', ['title']);
    expect(s.field()).toBe('match');
    expect(s.dir()).toBe('desc');
    expect(s.token()).toBe('match_desc');
  });

  it('flips direction when toggling the active field', () => {
    const s = createSortState<F>('match', 'desc', ['title']);
    s.toggle('match');
    expect(s.dir()).toBe('asc');
    expect(s.token()).toBe('match_asc');
    s.toggle('match');
    expect(s.dir()).toBe('desc');
  });

  it('selects a new field with its default direction', () => {
    const s = createSortState<F>('match', 'desc', ['title']);
    s.toggle('title'); // text field -> asc default
    expect(s.field()).toBe('title');
    expect(s.dir()).toBe('asc');
    s.toggle('posted'); // non-text -> desc default
    expect(s.field()).toBe('posted');
    expect(s.dir()).toBe('desc');
  });

  it('reports the active field', () => {
    const s = createSortState<F>('match', 'desc', ['title']);
    expect(s.isActive('match')).toBe(true);
    expect(s.isActive('title')).toBe(false);
  });
});
