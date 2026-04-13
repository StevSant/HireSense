import { NormalizedJob } from './normalized-job.model';

export interface PaginatedJobsResponse {
  jobs: NormalizedJob[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}
