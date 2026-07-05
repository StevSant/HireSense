import { parseCvSection } from './parse-cv-section';

describe('parseCvSection', () => {
  it('parses a single entry as heading, role, then bullet list', () => {
    const content = [
      'Project Alpha',
      '',
      'Backend Developer 2025',
      '',
      '- Built an API',
      '- Wrote tests',
    ].join('\n');

    const blocks = parseCvSection(content);

    expect(blocks).toEqual([
      { kind: 'heading', text: 'Project Alpha' },
      { kind: 'role', text: 'Backend Developer 2025' },
      { kind: 'list', items: ['Built an API', 'Wrote tests'] },
    ]);
  });

  it('treats each project title as a heading even when entries are NOT blank-line separated', () => {
    // Reproduces the ES→EN translation case: the spacing that normally splits
    // projects (>=4 newlines) collapsed to a single blank line, so all three
    // projects land in one entry. Every title must still render as a heading.
    const content = [
      'Centinela IA',
      '',
      'AI Agent — Backend Developer',
      '',
      '- Achieved 1st place',
      '', // only ONE blank line between projects (collapsed by translation)
      'SME Risk Assessment Agent',
      '',
      'Backend — AI Developer',
      '',
      '- Built the agent',
      '',
      'StreamFlowMusic',
      '',
      'Backend Developer 2025',
      '',
      '- Built a REST API',
    ].join('\n');

    const blocks = parseCvSection(content);

    const headings = blocks
      .filter((b) => b.kind === 'heading')
      .map((b) => (b as { text: string }).text);
    const roles = blocks.filter((b) => b.kind === 'role').map((b) => (b as { text: string }).text);

    expect(headings).toEqual(['Centinela IA', 'SME Risk Assessment Agent', 'StreamFlowMusic']);
    expect(roles).toEqual([
      'AI Agent — Backend Developer',
      'Backend — AI Developer',
      'Backend Developer 2025',
    ]);
  });

  it('keeps separate entries (>=4 newlines) working the same way', () => {
    const content = [
      'Project Alpha',
      '',
      'Role A',
      '',
      '- Did A',
      '\n\n',
      'Project Beta',
      '',
      'Role B',
      '',
      '- Did B',
    ].join('\n');

    const headings = parseCvSection(content)
      .filter((b) => b.kind === 'heading')
      .map((b) => (b as { text: string }).text);

    expect(headings).toEqual(['Project Alpha', 'Project Beta']);
  });

  it('renders a long single line as a paragraph, not a heading', () => {
    const long = 'A'.repeat(150);
    const blocks = parseCvSection(long);
    expect(blocks).toEqual([{ kind: 'paragraph', text: long }]);
  });
});
