import { PROFILE_ROUTES } from './profile-routes.const';

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
      { label: 'Opportunities', path: '/dashboard/opportunities' },
      { label: 'Auto-Hunt', path: '/dashboard/autohunt' },
      { label: 'Autopilot drafts', path: '/dashboard/autopilot/drafts' },
    ],
  },
  {
    id: 'pipeline',
    label: 'Pipeline',
    tabs: [
      { label: 'Applications', path: '/dashboard/applications' },
      { label: 'Inbox review', path: '/dashboard/applications/signals' },
      { label: 'Interview', path: '/dashboard/interview' },
      { label: 'Outreach', path: '/dashboard/outreach' },
    ],
  },
  {
    id: 'insights',
    label: 'Insights',
    tabs: [
      { label: 'Pay', path: '/dashboard/analytics/pay' },
      { label: 'Fit', path: '/dashboard/analytics/fit' },
      { label: 'Pipeline', path: '/dashboard/analytics/pipeline' },
      { label: 'Market', path: '/dashboard/analytics/market' },
      { label: 'Portfolio', path: '/dashboard/analytics/portfolio' },
    ],
  },
  {
    id: 'profile',
    label: 'Profile',
    tabs: [
      { label: 'CV', path: PROFILE_ROUTES.cv },
      { label: 'Personal details', path: PROFILE_ROUTES.personal },
      { label: 'Apply profile', path: PROFILE_ROUTES.apply },
      { label: 'Sources', path: PROFILE_ROUTES.sources },
      { label: 'Cover letters', path: PROFILE_ROUTES.coverLetters },
    ],
  },
  {
    id: 'admin',
    label: 'Admin',
    tabs: [
      { label: 'LLM Settings', path: '/dashboard/admin/llm-settings' },
      { label: 'LLM Usage', path: '/dashboard/admin/usage' },
      { label: 'Scheduler', path: '/dashboard/admin/scheduler' },
      { label: 'Notifications', path: '/dashboard/admin/notifications' },
    ],
  },
];
