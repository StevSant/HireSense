// Pure, framework-free matching core for Apply Assist autofill. This is the
// TESTED reference implementation; the userscript at public/apply-assist.user.js
// inlines a faithful copy (userscripts run standalone and can't import).
//
// LABEL_PATTERNS mirrors the backend `ats_field_map.py` _LABEL_PATTERNS — the
// backend stays the source of truth; keep the two in sync when either changes.

export type PrefillValue = string | boolean | number;

export interface PrefillFill {
  canonicalKey: string;
  value: PrefillValue;
  labelPatterns: string[];
}

export interface LabeledField {
  label: string;
}

export interface FillTarget {
  fieldIndex: number;
  canonicalKey: string;
  value: string;
}

export const LABEL_PATTERNS: Record<string, string[]> = {
  first_name: ['first name'],
  last_name: ['last name'],
  full_name: ['full name'],
  preferred_name: ['preferred name', 'preferred first name'],
  email: ['email', 'e-mail'],
  phone: ['phone', 'mobile', 'telephone'],
  location: ['location', 'city', 'current location', 'where are you'],
  linkedin_url: ['linkedin'],
  github_url: ['github'],
  portfolio_url: ['portfolio', 'website', 'personal site'],
  work_authorization: ['work authorization', 'authorized to work', 'right to work'],
  requires_visa_sponsorship: ['sponsorship', 'visa', 'require sponsorship'],
  desired_salary: ['salary', 'expected salary', 'compensation expectation'],
  years_of_experience: ['years of experience', 'years experience'],
  willing_to_relocate: ['relocate', 'relocation'],
  start_availability: ['availability', 'start date', 'notice period', 'when can you start'],
};

/** True when any pattern appears (case-insensitive substring) in the label. */
export function labelMatches(labelText: string, patterns: string[]): boolean {
  const haystack = labelText.toLowerCase();
  return patterns.some((p) => haystack.includes(p.toLowerCase()));
}

/** Render a prefill value for a text input (booleans become Yes/No). */
export function formatValue(value: PrefillValue): string {
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  return String(value);
}

/**
 * Turn a flat prefill object into fills, keeping only keys we have both a value
 * and a known label mapping for.
 */
export function buildFills(
  prefill: Record<string, PrefillValue>,
  patterns: Record<string, string[]> = LABEL_PATTERNS,
): PrefillFill[] {
  const fills: PrefillFill[] = [];
  for (const key of Object.keys(patterns)) {
    if (key in prefill && prefill[key] !== null && prefill[key] !== undefined) {
      fills.push({ canonicalKey: key, value: prefill[key], labelPatterns: patterns[key] });
    }
  }
  return fills;
}

/**
 * Map each fill to the first unused form field whose label matches. Each field
 * is claimed at most once; fills with no matching field are skipped.
 */
export function planFills(fills: PrefillFill[], fields: LabeledField[]): FillTarget[] {
  const used = new Set<number>();
  const targets: FillTarget[] = [];
  for (const fill of fills) {
    const idx = fields.findIndex(
      (f, i) => !used.has(i) && labelMatches(f.label, fill.labelPatterns),
    );
    if (idx === -1) continue;
    used.add(idx);
    targets.push({
      fieldIndex: idx,
      canonicalKey: fill.canonicalKey,
      value: formatValue(fill.value),
    });
  }
  return targets;
}
