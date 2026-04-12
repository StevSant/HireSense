import { NormalizedJob } from './normalized-job.model';

export interface FetchResponse {
  count: number;
  jobs: NormalizedJob[];
}
