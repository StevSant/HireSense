import { HUBS, HubId } from './hubs.const';

/**
 * Resolve which hub a dashboard URL belongs to, by exact base-path match.
 * Query string and fragment are ignored. Drill-down/detail routes (e.g.
 * `/dashboard/applications/1`) have no hub tab and return null.
 */
export function hubForUrl(url: string): HubId | null {
  const path = url.split(/[?#]/)[0];
  for (const hub of HUBS) {
    if (hub.tabs.some((tab) => tab.path === path)) {
      return hub.id;
    }
  }
  return null;
}
