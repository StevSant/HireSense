import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import { ApplicationsService } from '../../../core/services/applications.service';
import { ApplicationCreateDialogComponent } from './application-create-dialog.component';

describe('ApplicationCreateDialogComponent', () => {
  function mount() {
    const createManual = vi.fn(() => of({ id: 'app-1' }));
    TestBed.configureTestingModule({
      imports: [ApplicationCreateDialogComponent],
      providers: [{ provide: ApplicationsService, useValue: { createManual } }],
    });
    const fixture = TestBed.createComponent(ApplicationCreateDialogComponent);
    fixture.detectChanges();
    return { fixture, createManual };
  }

  it('keeps optional listing metadata collapsed initially', () => {
    const { fixture } = mount();

    const details = fixture.nativeElement.querySelector('details.listing-metadata');
    expect(details).not.toBeNull();
    expect(details.open).toBe(false);
  });

  it('submits salary text and optional listing metadata unchanged', () => {
    const { fixture, createManual } = mount();
    const component = fixture.componentInstance;
    component.title.set('  Backend Engineer  ');
    component.company.set('  Acme  ');
    component.description.set('Build APIs');
    component.location.set('Quito');
    component.remoteModality.set('on_site');
    component.salaryRange.set('USD 1,500-2,000/mo');
    component.source.set('Referral');
    component.postedDate.set('2026-07-01');

    component.submit();

    expect(createManual).toHaveBeenCalledWith({
      title: 'Backend Engineer',
      company: 'Acme',
      description: 'Build APIs',
      url: undefined,
      location: 'Quito',
      remote_modality: 'on_site',
      salary_range: 'USD 1,500-2,000/mo',
      source: 'Referral',
      posted_date: '2026-07-01T00:00:00Z',
    });
  });
});
