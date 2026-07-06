import { parseJobDescription } from './parse-job-description';

describe('parseJobDescription', () => {
  it('still parses HN-style *Heading*: sections', () => {
    const parsed = parseJobDescription('Intro line\n*Stack*:\nPython, Django');
    expect(parsed.intro).toBe('Intro line');
    expect(parsed.sections).toHaveLength(1);
    expect(parsed.sections[0].title).toBe('Stack');
    expect(parsed.sections[0].emphasis).toBe('stack');
    expect(parsed.sections[0].body).toBe('Python, Django');
  });

  it('detects standalone plain "Heading:" lines as sections', () => {
    const parsed = parseJobDescription(
      'Formación:\nEstudios de Ingeniería Informática, o afín.\nExperiencia:\n2-3 años en Python.\nDiseño de software.',
    );
    expect(parsed.intro).toBe('');
    expect(parsed.sections.map((s) => s.title)).toEqual(['Formación', 'Experiencia']);
  });

  it('does not treat lines with mid-line colons or sentence punctuation as headings', () => {
    const parsed = parseJobDescription(
      'Requisitos:\nBases de Datos: SQL y noSQL, como MongoDB. Nivel básico.\nGit: Nivel intermedio.',
    );
    expect(parsed.sections).toHaveLength(1);
    expect(parsed.sections[0].title).toBe('Requisitos');
    expect(parsed.sections[0].body).toContain('Bases de Datos: SQL y noSQL');
  });

  it('rejects headings longer than 60 characters', () => {
    const longLine = 'a'.repeat(61) + ':';
    const parsed = parseJobDescription(`${longLine}\nbody`);
    expect(parsed.sections).toHaveLength(0);
    expect(parsed.intro).toContain('body');
  });

  it('turns multi-line plain bodies into list items while keeping body intact', () => {
    const parsed = parseJobDescription('Requisitos:\nLinux intermedio\nDocker intermedio\nAnsible');
    expect(parsed.sections[0].items).toEqual(['Linux intermedio', 'Docker intermedio', 'Ansible']);
    expect(parsed.sections[0].body).toBe('Linux intermedio\nDocker intermedio\nAnsible');
  });

  it('strips bullet markers from list items', () => {
    const parsed = parseJobDescription('Tasks:\n- Build features\n• Review code\n* Ship it');
    expect(parsed.sections[0].items).toEqual(['Build features', 'Review code', 'Ship it']);
  });

  it('keeps single-line bodies as prose (no items)', () => {
    const parsed = parseJobDescription('Stack:\nPython, Django, PostgreSQL.');
    expect(parsed.sections[0].items).toBeUndefined();
  });

  it('keeps paragraph-style bodies (blank-line separated) as prose unless fully bulleted', () => {
    const parsed = parseJobDescription(
      'About:\nFirst paragraph of prose.\n\nSecond paragraph of prose.',
    );
    expect(parsed.sections[0].items).toBeUndefined();
  });

  it('treats fully bulleted bodies as lists even with blank lines between bullets', () => {
    const parsed = parseJobDescription('Perks:\n- Remote work\n\n- Health insurance');
    expect(parsed.sections[0].items).toEqual(['Remote work', 'Health insurance']);
  });

  it('maps Spanish headings onto emphasis buckets', () => {
    const parsed = parseJobDescription(
      'Salario:\n$60k\nConocimientos Específicos / Requisitos Técnicos:\nLinux\nDocker\nFunciones:\nDesarrollar\nMantener\nCómo postular:\nEnvía tu CV',
    );
    const byTitle = Object.fromEntries(parsed.sections.map((s) => [s.title, s.emphasis]));
    expect(byTitle['Salario']).toBe('compensation');
    expect(byTitle['Conocimientos Específicos / Requisitos Técnicos']).toBe('stack');
    expect(byTitle['Funciones']).toBe('role');
    expect(byTitle['Cómo postular']).toBe('apply');
  });

  it('does not treat bullet lines ending with a colon as headings', () => {
    const parsed = parseJobDescription('Tasks:\n- Build features such as:\nmore text');
    expect(parsed.sections).toHaveLength(1);
    expect(parsed.sections[0].title).toBe('Tasks');
  });
});
