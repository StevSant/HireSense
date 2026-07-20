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
  description: null,
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

  it('shows the source About text even when the LLM is not configured', () => {
    const withAbout: CompanyResearch = {
      ...research,
      funding_stage: 'LLM not configured',
      tech_stack: 'LLM not configured',
      culture_summary: 'LLM not configured',
      growth_trajectory: 'LLM not configured',
      pros: 'LLM not configured',
      cons: 'LLM not configured',
      description: 'Somos una consultora de TI.',
    };
    const fixture = mount(withAbout);
    const el = fixture.nativeElement as HTMLElement;
    // About renders independent of the generated (sentinel) sections.
    expect(el.querySelector('.intel-about')?.textContent ?? '').toContain(
      'Somos una consultora de TI.',
    );
    expect(el.querySelectorAll('.intel-sections section').length).toBe(0);
  });

  it('shows a transient-unavailable message (not the no-LLM one) for the "Research unavailable" sentinel', () => {
    const unavailable: CompanyResearch = {
      ...research,
      funding_stage: 'Research unavailable',
      tech_stack: 'Research unavailable',
      culture_summary: 'Research unavailable',
      growth_trajectory: 'Research unavailable',
      pros: 'Research unavailable',
      cons: 'Research unavailable',
    };
    const fixture = mount(unavailable);
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('temporarily unavailable');
    expect(text).not.toContain("isn't configured");
    expect(fixture.nativeElement.querySelectorAll('.intel-sections section').length).toBe(0);
  });

  it('resets the logo fallback when the company (and its logo_url) changes', () => {
    const withLogo: CompanyResearch = { ...research, logo_url: 'https://bc.cl/logo.png' };
    const fixture = mount(withLogo);

    fixture.componentInstance.onLogoError();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.intel-logo')).toBeNull();
    expect(fixture.nativeElement.querySelector('.intel-monogram')).not.toBeNull();

    const otherCompany: CompanyResearch = {
      ...research,
      id: '2',
      company_name: 'Other Co',
      logo_url: 'https://other.co/logo.png',
    };
    fixture.componentRef.setInput('research', otherCompany);
    fixture.detectChanges();

    expect(fixture.componentInstance.showLogo()).toBe(true);
    expect(fixture.nativeElement.querySelector('.intel-logo')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('.intel-monogram')).toBeNull();
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
