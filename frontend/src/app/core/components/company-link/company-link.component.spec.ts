import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { CompanyLinkComponent } from './company-link.component';

@Component({
  standalone: true,
  imports: [CompanyLinkComponent],
  template: `<app-company-link [name]="name" />`,
})
class HostComponent {
  name: string | null = 'Acme';
}

function mount(name: string | null) {
  TestBed.configureTestingModule({ imports: [HostComponent], providers: [provideRouter([])] });
  const fixture = TestBed.createComponent(HostComponent);
  fixture.componentInstance.name = name;
  fixture.detectChanges();
  return fixture;
}

describe('CompanyLinkComponent', () => {
  it('links to the company detail page', () => {
    const fixture = mount('Acme');
    const link = fixture.nativeElement.querySelector('a') as HTMLAnchorElement;
    expect(link.getAttribute('href')).toBe('/dashboard/company/Acme');
    expect(link.textContent?.trim()).toBe('Acme');
  });

  it('renders an em dash and no link when empty', () => {
    const fixture = mount(null);
    expect(fixture.nativeElement.querySelector('a')).toBeNull();
    expect(fixture.nativeElement.textContent).toContain('—');
  });
});
