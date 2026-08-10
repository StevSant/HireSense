export interface Story {
  id: string;
  title: string;
  competency: string;
  situation: string;
  task: string;
  action: string;
  result: string;
  reflection: string | null;
  tags: string | null;
  created_at: string;
  updated_at: string;
}
