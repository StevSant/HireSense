export type CvSectionBlock =
  | { kind: 'list'; items: string[] }
  | { kind: 'definitions'; entries: { term: string; description: string }[] }
  | { kind: 'role'; text: string }
  | { kind: 'heading'; text: string }
  | { kind: 'paragraph'; text: string };
