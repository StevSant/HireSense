import { CvSectionBlock } from './cv-section-block.model';

const BULLET_PATTERN = /^[-•*]\s+/;
const DEFINITION_PATTERN = /^([^:\n]{1,60}):\s*(?:[—–-]+\s*)?(.+)$/;

function normaliseDashes(text: string): string {
  return text.replace(/\s+--+\s+/g, ' — ');
}

function parseDefinition(line: string): { term: string; description: string } | null {
  const match = line.match(DEFINITION_PATTERN);
  if (!match) return null;
  const term = match[1].trim();
  const description = match[2].trim();
  if (!term || !description) return null;
  if (term.split(/\s+/).length > 6) return null;
  return { term, description };
}

// Within a section, individual jobs/projects/degrees are separated by 3+
// blank lines (≥4 newlines) in the parsed CV text. Inside a single entry,
// blocks (heading, role, bullets) are separated by 1–2 blank lines.
const ENTRY_SEPARATOR = /\n{4,}/;
const BLOCK_SEPARATOR = /\n{2,}/;

// A single line longer than this is treated as a paragraph (e.g. Summary)
// rather than a heading, even when it sits at position 0 of an entry.
const PARAGRAPH_MIN_LENGTH = 120;

export function parseCvSection(content: string): CvSectionBlock[] {
  if (!content) return [];
  const blocks: CvSectionBlock[] = [];
  const entries = content.replace(/\r\n/g, '\n').split(ENTRY_SEPARATOR);

  for (const entry of entries) {
    const trimmedEntry = entry.trim();
    if (!trimmedEntry) continue;
    const paragraphs = trimmedEntry.split(BLOCK_SEPARATOR);
    let positionInEntry = 0;

    for (const para of paragraphs) {
      const trimmed = para.trim();
      if (!trimmed) continue;
      const lines = trimmed.split('\n').map((l) => l.trim()).filter(Boolean);
      if (!lines.length) continue;

      if (lines.every((l) => BULLET_PATTERN.test(l))) {
        blocks.push({
          kind: 'list',
          items: lines.map((l) => normaliseDashes(l.replace(BULLET_PATTERN, ''))),
        });
        positionInEntry++;
        continue;
      }

      const definitions = lines.map(parseDefinition);
      if (definitions.every((d): d is { term: string; description: string } => d !== null)) {
        blocks.push({ kind: 'definitions', entries: definitions });
        positionInEntry++;
        continue;
      }

      if (lines.length === 1) {
        const single = normaliseDashes(lines[0]);
        if (single.length > PARAGRAPH_MIN_LENGTH) {
          blocks.push({ kind: 'paragraph', text: single });
        } else if (positionInEntry === 0) {
          blocks.push({ kind: 'heading', text: single });
        } else {
          blocks.push({ kind: 'role', text: single });
        }
        positionInEntry++;
        continue;
      }

      blocks.push({ kind: 'paragraph', text: lines.map(normaliseDashes).join(' ') });
      positionInEntry++;
    }
  }

  return blocks;
}
