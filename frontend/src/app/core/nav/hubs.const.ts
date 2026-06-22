export type HubId = 'discover' | 'pipeline' | 'insights' | 'profile' | 'admin';

export interface HubTab {
  readonly label: string;
  readonly path: string;
}

export interface Hub {
  readonly id: HubId;
  readonly label: string;
  readonly tabs: readonly HubTab[];
}

export const HUBS: readonly Hub[] = [
  {
    id: 'discover',
    label: 'Discover',
    tabs: [
      { label: 'Ingestion', path: '/dashboard/ingestion' },
      { label: 'Matching', path: '/dashboard/matching' },
      { label: 'Auto-Hunt', path: '/dashboard/autohunt' },
    ],
  },
  {
    id: 'pipeline',
    label: 'Pipeline',
    tabs: [
      { label: 'Applications', path: '/dashboard/applications' },
      { label: 'Interview', path: '/dashboard/interview' },
      { label: 'Outreach', path: '/dashboard/outreach' },
    ],
  },
  {
    id: 'insights',
    label: 'Insights',
    tabs: [{ label: 'Analytics', path: '/dashboard/analytics' }],
  },
  // Single sentinel tab: used by hubForUrl for URL->hub resolution only; the profile
  // hub renders its own internal signal tabs, so HubTabsComponent is suppressed for it.
  {
    id: 'profile',
    label: 'Profile',
    tabs: [{ label: 'Profile', path: '/dashboard/profile' }],
  },
  {
    id: 'admin',
    label: 'Admin',
    tabs: [
      { label: 'LLM Settings', path: '/dashboard/admin/llm-settings' },
      { label: 'LLM Usage', path: '/dashboard/admin/usage' },
      { label: 'Scheduler', path: '/dashboard/admin/scheduler' },
    ],
  },
];
