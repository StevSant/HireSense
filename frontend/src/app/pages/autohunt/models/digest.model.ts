import { DigestEntry } from './digest-entry.model';

export interface Digest {
  id: string;
  created_at: string | null;
  cutoff_at: string;
  entries: DigestEntry[];
  job_count: number;
}
