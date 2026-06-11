import { TestBed } from '@angular/core/testing';
import { JobDescriptionComponent } from './job-description.component';

function mount(description: string, collapsible = false) {
  TestBed.configureTestingModule({ imports: [JobDescriptionComponent] });
  const fixture = TestBed.createComponent(JobDescriptionComponent);
  fixture.componentRef.setInput('description', description);
  fixture.componentRef.setInput('collapsible', collapsible);
  fixture.detectChanges();
  return fixture;
}

describe('JobDescriptionComponent', () => {
  it('renders structured sections when the description has *Headers*', () => {
    const fixture = mount('Intro line\n*Stack*:\nPython, Django');
    const text = fixture.nativeElement.textContent;
    expect(text).toContain('Stack');
    expect(text).toContain('Python, Django');
    expect(fixture.nativeElement.querySelectorAll('.jd-section').length).toBeGreaterThan(0);
  });

  it('renders plain "Heading:" descriptions as section cards with bullet lists', () => {
    const fixture = mount('Formación:\nIngeniería Informática o afín.\nRequisitos:\nLinux intermedio\nDocker intermedio');
    expect(fixture.nativeElement.querySelectorAll('.jd-section').length).toBe(2);
    const items = fixture.nativeElement.querySelectorAll('.jd-list li');
    expect(items.length).toBe(2);
    expect(items[0].textContent).toContain('Linux intermedio');
    expect(fixture.nativeElement.querySelector('.jd-raw')).toBeNull();
  });

  it('falls back to raw text when there are no sections', () => {
    const fixture = mount('Just a plain description with no headers.');
    expect(fixture.nativeElement.querySelector('.jd-raw')).not.toBeNull();
    expect(fixture.nativeElement.textContent).toContain('plain description');
  });

  it('clamps long descriptions when collapsible, expanding on toggle', () => {
    const long = 'Tasks:\n' + 'A fairly long requirement line.\n'.repeat(80);
    const fixture = mount(long, true);
    expect(fixture.nativeElement.querySelector('.jd-content.jd-clamped')).not.toBeNull();
    const toggle = fixture.nativeElement.querySelector('.jd-toggle');
    expect(toggle.textContent).toContain('Show full description');

    toggle.click();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.jd-content.jd-clamped')).toBeNull();
    expect(fixture.nativeElement.querySelector('.jd-toggle').textContent).toContain('Show less');
  });

  it('shows no toggle for short descriptions even when collapsible', () => {
    const fixture = mount('Stack:\nPython, Django', true);
    expect(fixture.nativeElement.querySelector('.jd-toggle')).toBeNull();
    expect(fixture.nativeElement.querySelector('.jd-clamped')).toBeNull();
  });

  it('never clamps when not collapsible (default)', () => {
    const long = 'Tasks:\n' + 'A fairly long requirement line.\n'.repeat(80);
    const fixture = mount(long);
    expect(fixture.nativeElement.querySelector('.jd-toggle')).toBeNull();
    expect(fixture.nativeElement.querySelector('.jd-clamped')).toBeNull();
  });
});
