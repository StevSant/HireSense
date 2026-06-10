import { PortfolioProject } from './portfolio-project.model';

export interface PortfolioProjectsResponse {
  projects: PortfolioProject[];
  last_synced_at: string | null;
}
