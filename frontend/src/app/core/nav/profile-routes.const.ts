/**
 * Canonical paths for the Profile hub tabs.
 *
 * Shared by the hub nav, the setup checklist's per-step links and the "no
 * profile yet" empty state, so a tab path only ever changes in one place.
 */
export const PROFILE_ROUTES = {
  cv: '/dashboard/profile/cv',
  personal: '/dashboard/profile/personal',
  apply: '/dashboard/profile/apply',
  sources: '/dashboard/profile/sources',
  coverLetters: '/dashboard/profile/cover-letters',
} as const;
