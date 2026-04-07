export interface PortalEntry {
  name: string;
  platform: 'greenhouse' | 'lever' | 'ashby';
  board_id: string;
  categories: string[];
}
