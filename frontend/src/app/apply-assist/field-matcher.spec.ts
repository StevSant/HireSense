import { buildFills, formatValue, labelMatches, planFills } from './field-matcher';

describe('field-matcher', () => {
  describe('labelMatches', () => {
    it('matches case-insensitive substrings', () => {
      expect(labelMatches('First Name*', ['first name'])).toBe(true);
      expect(labelMatches('Your E-Mail', ['email', 'e-mail'])).toBe(true);
    });

    it('does not match unrelated labels', () => {
      expect(labelMatches('Cover Letter', ['first name'])).toBe(false);
    });
  });

  describe('formatValue', () => {
    it('renders booleans as Yes/No and passes other values through', () => {
      expect(formatValue(true)).toBe('Yes');
      expect(formatValue(false)).toBe('No');
      expect(formatValue(8)).toBe('8');
      expect(formatValue('Ada')).toBe('Ada');
    });
  });

  describe('buildFills', () => {
    it('keeps only keys present in prefill with a known label mapping', () => {
      const fills = buildFills({ email: 'a@b.com', unknown_key: 'x' });
      expect(fills.map((f) => f.canonicalKey)).toEqual(['email']);
      expect(fills[0].labelPatterns).toContain('email');
    });
  });

  describe('planFills', () => {
    const fills = buildFills({
      first_name: 'Ada',
      email: 'ada@example.com',
      requires_visa_sponsorship: false,
    });

    it('maps fills to the first matching field and formats values', () => {
      const fields = [
        { label: 'First Name*' },
        { label: 'Email*' },
        { label: 'Will you require visa sponsorship?' },
      ];
      const targets = planFills(fills, fields);
      const byKey = Object.fromEntries(targets.map((t) => [t.canonicalKey, t]));

      expect(byKey['first_name'].fieldIndex).toBe(0);
      expect(byKey['email'].value).toBe('ada@example.com');
      expect(byKey['requires_visa_sponsorship'].value).toBe('No');
    });

    it('claims each field at most once', () => {
      // Two fills could match "name", but only the first field is consumed.
      const twoNameFills = buildFills({ first_name: 'Ada', full_name: 'Ada Lovelace' });
      const targets = planFills(twoNameFills, [{ label: 'Name' }]);
      // "Name" contains neither "first name" nor "full name" → no match at all.
      expect(targets).toEqual([]);
    });

    it('skips fills with no matching field', () => {
      const targets = planFills(fills, [{ label: 'Cover Letter' }]);
      expect(targets).toEqual([]);
    });
  });
});
