import { NormalizedJob } from '@core/contracts/normalized-job.model';

export interface FetchResponse {
  count: number;
  jobs: NormalizedJob[];
}
