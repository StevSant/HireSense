/**
 * Opens an untrusted, externally-sourced URL in a new tab, but only after
 * confirming it uses a safe web scheme (`http:`/`https:`).
 *
 * Ingested job URLs are attacker-influenceable and `window.open` performs no
 * sanitization (unlike Angular's `[href]` binding, which the framework
 * sanitizes), so a `javascript:` — or `data:`/`blob:`/`file:` — URL in a
 * malicious posting would otherwise run in, or leak, the app's origin.
 *
 * Returns `true` when the URL passed validation and was opened, `false` when
 * it was rejected (unparseable or a non-http(s) scheme).
 */
export function openExternalUrl(rawUrl: string): boolean {
  let parsed: URL;
  try {
    parsed = new URL(rawUrl);
  } catch {
    return false;
  }
  if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
    return false;
  }
  window.open(parsed.href, '_blank', 'noopener');
  return true;
}
