import { JobDescriptionSection, ParsedJobDescription } from './job-description-block.model';

// HN "Who is Hiring?" posts conventionally tag sections with asterisks:
//   *Compensation*: 75% market salary + equity
//   *Stack*:
//   Python 3.9+, Django ...
// We detect headings of the shape "*Foo*:" or "**Foo:**" at the start of a
// line, with or without trailing colon, optionally followed by inline text.
const HEADING_PATTERN = /^\*+\s*([^*\n:]{1,80})\s*\*+\s*:?\s*(.*)$/;

// Plain-text headings, common in ATS postings ("Formación:", "Requisitos
// Técnicos:"): a short standalone line whose last character is a colon. The
// colon must terminate the line (rejects prose like "Bases de Datos: SQL y
// noSQL.") and the title may not contain sentence punctuation.
const PLAIN_HEADING_PATTERN = /^([^.;:\n]{1,60}):$/;

const BULLET_PATTERN = /^[-•·*]\s+/;

// Lower-cased heading text → emphasis bucket used by the UI for styling.
const EMPHASIS_MAP: readonly [RegExp, JobDescriptionSection['emphasis']][] = [
  [/\b(compensation|salary|pay|comp|compensación|salario|sueldo|beneficios)\b/i, 'compensation'],
  [/\b(apply|how\s*to\s*apply|contact|email|postular?\w*|aplicar|contacto)\b/i, 'apply'],
  [/\b(stack|tech\s*stack|technology|tools|requisitos|conocimientos|tecnologías?|herramientas)\b/i, 'stack'],
  [/\b(role|position|responsibilities|about\s*the\s*role|experiencia|funciones|responsabilidades|rol|formación)\b/i, 'role'],
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

// A body qualifies as a list when it is fully bulleted, or when it is 2+
// plain lines with no blank-line paragraph breaks (line-per-requirement
// postings). Prose and single-line bodies return undefined.
function extractListItems(body: string): string[] | undefined {
  if (!body) return undefined;
  const lines = body.split('\n').map((l) => l.trim());
  const nonEmpty = lines.filter((l) => l.length > 0);
  if (nonEmpty.length === 0) return undefined;
  const allBulleted = nonEmpty.every((l) => BULLET_PATTERN.test(l));
  const hasParagraphBreaks = lines.length !== nonEmpty.length;
  if (!allBulleted && (nonEmpty.length < 2 || hasParagraphBreaks)) return undefined;
  return nonEmpty.map((l) => l.replace(BULLET_PATTERN, ''));
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
    const items = extractListItems(current.body);
    if (items) current.items = items;
    sections.push(current);
    current = null;
    buffer = [];
  };

  for (const line of lines) {
    const trimmed = line.trim();
    const match = trimmed.match(HEADING_PATTERN);
    if (match) {
      flush();
      const title = match[1].trim();
      const inline = match[2].trim();
      current = { title, body: '', emphasis: detectEmphasis(title) };
      if (inline) buffer.push(inline);
      continue;
    }
    const plain = BULLET_PATTERN.test(trimmed) ? null : trimmed.match(PLAIN_HEADING_PATTERN);
    if (plain) {
      flush();
      const title = plain[1].trim();
      current = { title, body: '', emphasis: detectEmphasis(title) };
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
