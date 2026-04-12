import { NormalizedJob } from './normalized-job.model';

export interface ScanError {
  portal: string;
  platform: string;
  error: string;
}

export interface ScanResult {
  total_fetched: number;
  new: number;
  duplicates: number;
  jobs: NormalizedJob[];
  errors: ScanError[];
}
