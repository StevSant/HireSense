import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { PortfolioCardComponent } from './portfolio-card.component';
import { environment } from '../../../../../environments/environment';

describe('PortfolioCardComponent', () => {
  let fixture: ComponentFixture<PortfolioCardComponent>;
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [PortfolioCardComponent],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    fixture = TestBed.createComponent(PortfolioCardComponent);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  function flushProjects(projects: unknown[], last: string | null, total = projects.length) {
    httpMock
      .expectOne((req) => req.url === `${environment.apiUrl}/portfolio/projects`)
      .flush({ projects, total, last_synced_at: last });
    fixture.detectChanges();
  }

  function project(over: Record<string, unknown> = {}) {
    return {
      id: 'p1',
      source: 'supabase',
      source_key: 'x',
      url: null,
      demo_url: null,
      pinned: false,
      position: null,
      include_in_matching: true,
      tech: [],
      translations: { en: { title: 'X', description: null } },
      ...over,
    };
  }

  it('renders synced projects with tech tags', () => {
    fixture.detectChanges(); // ngOnInit → load
    flushProjects(
      [
        {
          id: 'p1',
          source: 'supabase',
          source_key: 'hiresense',
          url: 'https://x',
          demo_url: null,
          pinned: true,
          position: 1,
          tech: ['python', 'angular'],
          translations: { en: { title: 'HireSense', description: 'AI job hunting' } },
        },
      ],
      '2026-06-09T00:00:00Z',
    );
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('HireSense');
    expect(text).toContain('python');
  });

  it('shows the empty state when nothing is synced', () => {
    fixture.detectChanges();
    flushProjects([], null);
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('No portfolio projects synced yet');
  });

  it('sync button posts and reloads', () => {
    fixture.detectChanges();
    flushProjects([], null);
    (fixture.nativeElement as HTMLElement).querySelector('button')!.click();
    httpMock
      .expectOne(`${environment.apiUrl}/portfolio/sync`)
      .flush({ counts_by_source: { supabase: 1 }, errors: {}, synced_at: '2026-06-09T00:00:00Z' });
    flushProjects(
      [
        {
          id: 'p1',
          source: 'supabase',
          source_key: 'x',
          url: null,
          demo_url: null,
          pinned: false,
          position: null,
          tech: [],
          translations: { en: { title: 'X', description: null } },
        },
      ],
      '2026-06-09T00:00:00Z',
    );
    expect((fixture.nativeElement as HTMLElement).textContent ?? '').toContain('X');
  });

  it('renders a card grid with description snippet and caps tech chips with +N more', () => {
    fixture.detectChanges();
    flushProjects(
      [
        project({
          tech: ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'],
          translations: { en: { title: 'HireSense', description: 'AI job hunting' } },
        }),
      ],
      '2026-06-09T00:00:00Z',
    );
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('.project-grid')).toBeTruthy();
    expect(el.textContent ?? '').toContain('AI job hunting');
    expect(el.textContent ?? '').toContain('+2 more');
  });

  it('toggling "Counts toward matching" patches the project', () => {
    fixture.detectChanges();
    flushProjects([project({ id: 'p1', source_key: 'x', include_in_matching: true })], null);
    const el = fixture.nativeElement as HTMLElement;
    const checkbox = el.querySelector('.matching-toggle input') as HTMLInputElement;
    expect(checkbox.checked).toBe(true);
    checkbox.click(); // unchecks and fires the change handler
    const req = httpMock.expectOne(`${environment.apiUrl}/portfolio/projects/p1/matching`);
    expect(req.request.method).toBe('PATCH');
    expect(req.request.body).toEqual({ include_in_matching: false });
    req.flush({ include_in_matching: false });
  });

  it('paginates with Prev/Next and shows the X–Y of N indicator', () => {
    fixture.detectChanges();
    flushProjects([project({ id: 'a', source_key: 'a' })], '2026-06-09T00:00:00Z', 30);
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('.page-indicator')?.textContent).toContain('1–1 of 30');
    const next = [...el.querySelectorAll('button')].find((b) => b.textContent?.trim() === 'Next')!;
    expect(next.disabled).toBe(false);
    next.click();
    httpMock
      .expectOne(
        (req) =>
          req.url === `${environment.apiUrl}/portfolio/projects` &&
          req.params.get('offset') === '12',
      )
      .flush({
        projects: [project({ id: 'b', source_key: 'b' })],
        total: 30,
        last_synced_at: null,
      });
    fixture.detectChanges();
    expect(el.querySelector('.page-indicator')?.textContent).toContain('13–13 of 30');
  });
});
