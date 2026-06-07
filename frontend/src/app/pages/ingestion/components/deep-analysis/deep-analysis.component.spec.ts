import { TestBed } from '@angular/core/testing';
import { DeepAnalysisComponent } from './deep-analysis.component';
import { JobAnalysis } from '../../models/job-analysis.model';

const FULL_ANALYSIS: JobAnalysis = {
  job_id: 'j1',
  overall_score: 0.82,
  verdict: 'strong',
  dimensions: [
    { dimension: 'skills_role_fit', score: 0.9, rationale: 'Strong overlap on core stack.' },
    { dimension: 'seniority', score: 0.6, rationale: '' },
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

  it('renders the overall score as a percentage and the verdict', () => {
    const fixture = mount(FULL_ANALYSIS);
    const score = fixture.nativeElement.querySelector('.deep-overall-score');
    expect(score.textContent.trim()).toBe('82%');
    expect(fixture.nativeElement.querySelector('.deep-verdict').textContent.trim()).toBe('strong');
  });

  it('renders the narrative when present', () => {
    const fixture = mount(FULL_ANALYSIS);
    expect(fixture.nativeElement.querySelector('.deep-narrative').textContent.trim()).toBe(
      'A solid match overall.',
    );
  });

  it('renders a row per dimension with a humanized label', () => {
    const fixture = mount(FULL_ANALYSIS);
    const rows = fixture.nativeElement.querySelectorAll('.dim-row');
    expect(rows.length).toBe(2);
    const firstName = fixture.nativeElement.querySelector('.dim-name');
    expect(firstName.textContent.trim()).toBe('Skills role fit');
  });

  it('renders matched skills, gaps, pros, cons and recommendations', () => {
    const fixture = mount(FULL_ANALYSIS);
    const el = fixture.nativeElement;
    expect(el.querySelectorAll('.tag-match').length).toBe(2);
    expect(el.querySelectorAll('.tag-miss').length).toBe(1);
    expect(el.querySelectorAll('.pc-pro').length).toBe(1);
    expect(el.querySelectorAll('.pc-con').length).toBe(1);
    expect(el.querySelectorAll('.rec-list li').length).toBe(1);
  });

  it('omits optional blocks when their collections are empty', () => {
    const fixture = mount(EMPTY_ANALYSIS);
    const el = fixture.nativeElement;
    expect(el.querySelector('.deep-narrative')).toBeNull();
    expect(el.querySelector('.deep-verdict')).toBeNull();
    expect(el.querySelector('.dim-list')).toBeNull();
    expect(el.querySelector('.deep-skills')).toBeNull();
    expect(el.querySelector('.deep-proscons')).toBeNull();
  });

  it('barWidth clamps the score into a 0-100% range', () => {
    const fixture = mount(FULL_ANALYSIS);
    const c = fixture.componentInstance;
    expect(c.barWidth(0.5)).toBe('50%');
    expect(c.barWidth(-1)).toBe('0%');
    expect(c.barWidth(5)).toBe('100%');
  });

  it('humanize replaces underscores and capitalizes', () => {
    const fixture = mount(FULL_ANALYSIS);
    expect(fixture.componentInstance.humanize('skills_role_fit')).toBe('Skills role fit');
  });
});
