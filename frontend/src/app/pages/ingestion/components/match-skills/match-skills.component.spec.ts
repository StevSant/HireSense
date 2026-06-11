import { TestBed } from '@angular/core/testing';
import { MatchSkillsComponent } from './match-skills.component';

describe('MatchSkillsComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [MatchSkillsComponent],
    }).compileComponents();
  });

  function mount(matched: string[], missing: string[]) {
    const fixture = TestBed.createComponent(MatchSkillsComponent);
    fixture.componentRef.setInput('matched', matched);
    fixture.componentRef.setInput('missing', missing);
    fixture.detectChanges();
    return fixture;
  }

  it('renders matched and missing skill tags', () => {
    const el = mount(['python', 'fastapi'], ['kubernetes']).nativeElement;
    expect(el.querySelectorAll('.tag-match').length).toBe(2);
    expect(el.querySelectorAll('.tag-miss').length).toBe(1);
  });

  it('omits a column when its collection is empty', () => {
    const el = mount([], ['kubernetes']).nativeElement;
    expect(el.querySelectorAll('.skills-col').length).toBe(1);
    expect(el.querySelectorAll('.tag-miss').length).toBe(1);
  });
});
