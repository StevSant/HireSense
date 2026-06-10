export interface PortfolioProjectText {
  title: string;
  description: string | null;
}

export interface PortfolioProject {
  id: string;
  source: string;
  source_key: string;
  url: string | null;
  demo_url: string | null;
  pinned: boolean;
  position: number | null;
  tech: string[];
  translations: Record<string, PortfolioProjectText>;
}
