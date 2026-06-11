import { TestBed } from '@angular/core/testing';
import { DeepAnalysisComponent } from './deep-analysis.component';
import { JobAnalysis } from '../../models/job-analysis.model';

const FULL_ANALYSIS: JobAnalysis = {
  job_id: 'j1',
  overall_score: 0.82,
  verdict: 'strong',
  dimensions: [
    { dimension: 'skills_role_fit', score: 0.9, rationale: 'Strong overlap on core stack.' },
  ],
  matched_skills: ['python', 'fastapi'],
  missing_skills: ['kubernetes'],
  pros: ['Remote friendly'],
  cons: ['Below target comp'],
  recommendations: ['Highlight backend depth'],
  narrative: 'A solid match overall.',
};

const EMPTY_ANALYSIS: JobAnalysis = {
  job_id: 'j2',
  overall_score: 0.4,
  verdict: '',
  dimensions: [],
  matched_skills: [],
  missing_skills: [],
  pros: [],
  cons: [],
  recommendations: [],
  narrative: '',
};

describe('DeepAnalysisComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [DeepAnalysisComponent],
    }).compileComponents();
  });

  function mount(analysis: JobAnalysis) {
    const fixture = TestBed.createComponent(DeepAnalysisComponent);
    fixture.componentRef.setInput('analysis', analysis);
    fixture.detectChanges();
    return fixture;
  }

  it('renders the narrative when present', () => {
    const fixture = mount(FULL_ANALYSIS);
    expect(fixture.nativeElement.querySelector('.deep-narrative').textContent.trim()).toBe(
      'A solid match overall.',
    );
  });

  it('renders pros, cons and recommendations', () => {
    const el = mount(FULL_ANALYSIS).nativeElement;
    expect(el.querySelectorAll('.pc-pro').length).toBe(1);
    expect(el.querySelectorAll('.pc-con').length).toBe(1);
    expect(el.querySelectorAll('.rec-list li').length).toBe(1);
  });

  it('does not render matched/gap skills (those live in the rail)', () => {
    const el = mount(FULL_ANALYSIS).nativeElement;
    expect(el.querySelector('.tag-match')).toBeNull();
    expect(el.querySelector('.tag-miss')).toBeNull();
  });

  it('omits optional blocks when their collections are empty', () => {
    const el = mount(EMPTY_ANALYSIS).nativeElement;
    expect(el.querySelector('.deep-narrative')).toBeNull();
    expect(el.querySelector('.deep-proscons')).toBeNull();
    expect(el.querySelector('.rec-list')).toBeNull();
  });
});
