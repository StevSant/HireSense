import { TestBed } from '@angular/core/testing';
import { CompanyIntelComponent } from './company-intel.component';
import { CompanyResearch } from '../../../tracking/models/company-research.model';

const research: CompanyResearch = {
  id: '1',
  company_name: 'BC Tecnología',
  funding_stage: 'Series A',
  tech_stack: 'Python',
  culture_summary: 'Great',
  growth_trajectory: 'Up',
  red_flags: null,
  pros: 'p',
  cons: 'c',
  industry: 'SaaS',
  company_size: '51-200',
  headquarters: 'Santiago, CL',
  website: 'https://bc.cl',
  logo_url: null,
  created_at: null,
  updated_at: null,
};

describe('CompanyIntelComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CompanyIntelComponent],
    }).compileComponents();
  });

  function mount(value: CompanyResearch | null, loading = false, refreshing = false) {
    const fixture = TestBed.createComponent(CompanyIntelComponent);
    fixture.componentRef.setInput('research', value);
    fixture.componentRef.setInput('loading', loading);
    fixture.componentRef.setInput('refreshing', refreshing);
    fixture.detectChanges();
    return fixture;
  }

  it('renders firmographics and a monogram when no logo', () => {
    const fixture = mount(research);
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('SaaS');
    expect(text).toContain('Santiago, CL');
    expect(text).toContain('B'); // monogram initial
    expect(fixture.nativeElement.querySelector('.intel-logo')).toBeNull();
  });

  it('shows a loading state instead of research content', () => {
    const fixture = mount(null, true);
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Loading company intel');
  });

  it('hides not-configured sentinel sections and shows a fallback message', () => {
    const notConfigured: CompanyResearch = {
      ...research,
      funding_stage: 'LLM not configured',
      tech_stack: 'LLM not configured',
      culture_summary: 'Research unavailable',
      growth_trajectory: 'LLM not configured',
      pros: 'LLM not configured',
      cons: 'LLM not configured',
    };
    const fixture = mount(notConfigured);
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelectorAll('.intel-sections section').length).toBe(0);
    expect(el.textContent ?? '').toContain("isn't configured");
  });

  it('emits refresh when the button is clicked and disables it while refreshing', () => {
    const fixture = mount(research, false, true);
    const emitted: void[] = [];
    fixture.componentInstance.refresh.subscribe(() => emitted.push(undefined));
    const button = fixture.nativeElement.querySelector('.intel-refresh') as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    button.click();
    fixture.componentRef.setInput('refreshing', false);
    fixture.detectChanges();
    fixture.nativeElement.querySelector('.intel-refresh').click();
    expect(emitted.length).toBe(1);
  });
});
