import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { HubTabsComponent } from './hub-tabs.component';
import { HUBS } from './hubs.const';

@Component({
  standalone: true,
  imports: [HubTabsComponent],
  template: '<app-hub-tabs [hub]="hub" />',
})
class HostComponent {
  hub = HUBS.find((h) => h.id === 'pipeline')!;
}

describe('HubTabsComponent', () => {
  it('renders one link per hub tab with the right labels and hrefs', () => {
    TestBed.configureTestingModule({
      imports: [HostComponent],
      providers: [provideRouter([])],
    });
    const fixture = TestBed.createComponent(HostComponent);
    fixture.detectChanges();

    const links = Array.from(
      fixture.nativeElement.querySelectorAll('a.hub-tab'),
    ) as HTMLAnchorElement[];

    expect(links.map((a) => a.textContent?.trim())).toEqual([
      'Applications',
      'Interview',
      'Tracking',
      'Outreach',
    ]);
    expect(links[0].getAttribute('href')).toBe('/dashboard/applications');
  });
});
