export interface JobDescriptionSection {
  /** Human-readable heading (e.g. "Compensation", "Stack"). */
  title: string;
  /** Section body — already collapsed to consistent line breaks. */
  body: string;
  /**
   * Highlight key for visually distinct sections (compensation, apply, etc.).
   * Plain string so consumers can use it as a CSS class suffix.
   */
  emphasis?: 'compensation' | 'apply' | 'stack' | 'role';
}

export interface ParsedJobDescription {
  /**
   * Free-text intro that appears before any detected section heading.
   * Empty when the description starts with a heading.
   */
  intro: string;
  sections: JobDescriptionSection[];
}
