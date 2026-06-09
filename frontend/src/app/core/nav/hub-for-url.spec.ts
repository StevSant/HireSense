import { hubForUrl } from './hub-for-url';

describe('hubForUrl', () => {
  it('maps a hub tab path to its hub id', () => {
    expect(hubForUrl('/dashboard/matching')).toBe('discover');
    expect(hubForUrl('/dashboard/applications')).toBe('pipeline');
    expect(hubForUrl('/dashboard/analytics')).toBe('insights');
    expect(hubForUrl('/dashboard/profile')).toBe('profile');
    expect(hubForUrl('/dashboard/admin/usage')).toBe('admin');
  });

  it('ignores query string and fragment', () => {
    expect(hubForUrl('/dashboard/matching?job_id=1')).toBe('discover');
    expect(hubForUrl('/dashboard/ingestion#top')).toBe('discover');
  });

  it('returns null for drill-down and unknown routes', () => {
    expect(hubForUrl('/dashboard/applications/1')).toBeNull();
    expect(hubForUrl('/dashboard/job/1')).toBeNull();
    expect(hubForUrl('/dashboard/company/Acme')).toBeNull();
    expect(hubForUrl('/dashboard/optimization')).toBeNull();
    expect(hubForUrl('/')).toBeNull();
  });
});
