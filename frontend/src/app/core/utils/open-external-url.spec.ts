import { afterEach, describe, expect, it, vi } from 'vitest';
import { openExternalUrl } from './open-external-url';

describe('openExternalUrl', () => {
  afterEach(() => vi.restoreAllMocks());

  it('opens http URLs in a new tab with noopener', () => {
    const open = vi.spyOn(window, 'open').mockReturnValue(null);
    const result = openExternalUrl('http://example.com/job/123');
    expect(result).toBe(true);
    expect(open).toHaveBeenCalledWith('http://example.com/job/123', '_blank', 'noopener');
  });

  it('opens https URLs in a new tab', () => {
    const open = vi.spyOn(window, 'open').mockReturnValue(null);
    const result = openExternalUrl('https://jobs.example.com/posting?id=42');
    expect(result).toBe(true);
    expect(open).toHaveBeenCalledOnce();
  });

  it('rejects javascript: scheme without opening', () => {
    const open = vi.spyOn(window, 'open').mockReturnValue(null);
    const result = openExternalUrl('javascript:alert(document.cookie)');
    expect(result).toBe(false);
    expect(open).not.toHaveBeenCalled();
  });

  it('rejects data: scheme without opening', () => {
    const open = vi.spyOn(window, 'open').mockReturnValue(null);
    const result = openExternalUrl('data:text/html,<script>alert(1)</script>');
    expect(result).toBe(false);
    expect(open).not.toHaveBeenCalled();
  });

  it('rejects an unparseable / relative URL without opening', () => {
    const open = vi.spyOn(window, 'open').mockReturnValue(null);
    const result = openExternalUrl('/not/an/absolute/url');
    expect(result).toBe(false);
    expect(open).not.toHaveBeenCalled();
  });
});
