import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';
import { ProfileSourcesTabComponent } from './profile-sources-tab.component';
import { NetworkService } from '../../../../core/services/network.service';
import { PortfolioService } from '../../../../core/services/portfolio.service';

describe('ProfileSourcesTabComponent', () => {
  function mount() {
    TestBed.configureTestingModule({
      imports: [ProfileSourcesTabComponent],
      providers: [
        provideRouter([]),
        {
          provide: PortfolioService,
          useValue: {
            listProjects: () => of({ projects: [], total: 0, last_synced_at: null }),
          },
        },
        { provide: NetworkService, useValue: { summary: () => of(null) } },
      ],
    });
    const fixture = TestBed.createComponent(ProfileSourcesTabComponent);
    fixture.detectChanges();
    return { fixture };
  }

  // No ProfileService is provided at all: both cards must work before a CV
  // exists, which is the whole reason they share a profile-free tab.
  it('renders both source cards without a parsed profile', () => {
    const { fixture } = mount();
    const el = fixture.nativeElement as HTMLElement;

    expect(el.querySelector('app-network-card')).not.toBeNull();
    expect(el.querySelector('app-portfolio-card')).not.toBeNull();
  });
});
