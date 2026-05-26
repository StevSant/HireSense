import { JobDescriptionSection, ParsedJobDescription } from './job-description-block.model';

// HN "Who is Hiring?" posts conventionally tag sections with asterisks:
//   *Compensation*: 75% market salary + equity
//   *Stack*:
//   Python 3.9+, Django ...
// We detect headings of the shape "*Foo*:" or "**Foo:**" at the start of a
// line, with or without trailing colon, optionally followed by inline text.
const HEADING_PATTERN = /^\*+\s*([^*\n:]{1,80})\s*\*+\s*:?\s*(.*)$/;

// Lower-cased heading text → emphasis bucket used by the UI for styling.
const EMPHASIS_MAP: ReadonlyArray<[RegExp, JobDescriptionSection['emphasis']]> = [
  [/\b(compensation|salary|pay|comp)\b/i, 'compensation'],
  [/\b(apply|how\s*to\s*apply|contact|email)\b/i, 'apply'],
  [/\b(stack|tech\s*stack|technology|tools)\b/i, 'stack'],
  [/\b(role|position|responsibilities|about\s*the\s*role)\b/i, 'role'],
];

function detectEmphasis(title: string): JobDescriptionSection['emphasis'] {
  for (const [pattern, kind] of EMPHASIS_MAP) {
    if (pattern.test(title)) return kind;
  }
  return undefined;
}

function trimBlock(value: string): string {
  return value.replace(/\s+$/g, '').replace(/^\n+/, '');
}

export function parseJobDescription(description: string): ParsedJobDescription {
  if (!description) {
    return { intro: '', sections: [] };
  }
  const lines = description.replace(/\r\n/g, '\n').split('\n');
  const sections: JobDescriptionSection[] = [];
  const introLines: string[] = [];
  let current: JobDescriptionSection | null = null;
  let buffer: string[] = [];

  const flush = () => {
    if (!current) return;
    current.body = trimBlock(buffer.join('\n'));
    sections.push(current);
    current = null;
    buffer = [];
  };

  for (const line of lines) {
    const match = line.trim().match(HEADING_PATTERN);
    if (match) {
      flush();
      const title = match[1].trim();
      const inline = match[2].trim();
      current = { title, body: '', emphasis: detectEmphasis(title) };
      if (inline) buffer.push(inline);
      continue;
    }
    if (current) {
      buffer.push(line);
    } else {
      introLines.push(line);
    }
  }
  flush();

  return {
    intro: trimBlock(introLines.join('\n')),
    sections,
  };
}
