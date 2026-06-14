import { PortfolioProject } from './portfolio-project.model';

export interface PortfolioProjectsResponse {
  projects: PortfolioProject[];
  total: number;
  last_synced_at: string | null;
}
