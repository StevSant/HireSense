export interface CoverLetterTemplate {
  id: string;
  name: string;
  tone: string;
  language: string;
  opening: string;
  body: string;
  signature: string;
  created_at: string | null;
  updated_at: string | null;
}
