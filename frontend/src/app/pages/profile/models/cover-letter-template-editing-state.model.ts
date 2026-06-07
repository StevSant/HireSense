export type CoverLetterTemplateEditingState =
  | { mode: 'closed' }
  | { mode: 'new' }
  | { mode: 'edit'; id: string };
