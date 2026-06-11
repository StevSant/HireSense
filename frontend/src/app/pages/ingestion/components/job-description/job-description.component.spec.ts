import { TestBed } from '@angular/core/testing';
import { JobDescriptionComponent } from './job-description.component';

function mount(description: string) {
  TestBed.configureTestingModule({ imports: [JobDescriptionComponent] });
  const fixture = TestBed.createComponent(JobDescriptionComponent);
  fixture.componentRef.setInput('description', description);
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
});
