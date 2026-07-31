import { Opportunity } from './opportunity.model';

export interface PaginatedOpportunitiesResponse {
  items: Opportunity[];
  total: number;
  page: number;
  page_size: number;
}
