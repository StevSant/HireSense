import { ApplicationStatus } from '@core/contracts/application-status.model';

export interface StatusTab {
  readonly value: ApplicationStatus | '';
  readonly label: string;
}

/**
 * Canonical status tabs. Values mirror the backend ApplicationStatus enum
 * (tracking/domain/models.py); '' is the "All" pseudo-tab.
 */
export const STATUS_TABS: readonly StatusTab[] = [
  { value: '', label: 'All' },
  { value: 'saved', label: 'Saved' },
  { value: 'applied', label: 'Applied' },
  { value: 'interviewing', label: 'Interviewing' },
  { value: 'offered', label: 'Offer' },
  { value: 'accepted', label: 'Accepted' },
  { value: 'rejected', label: 'Rejected' },
];
