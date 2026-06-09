import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { DashboardComponent } from './dashboard.component';
import { AuthService } from '../../core/services/auth.service';

function makeAuth(over: Partial<Record<string, unknown>> = {}) {
  return {
    logout: () => {},
    ...over,
  };
}

describe('DashboardComponent', () => {
  function mount(auth: unknown = makeAuth()) {
    TestBed.configureTestingModule({
      imports: [DashboardComponent],
      providers: [provideRouter([]), { provide: AuthService, useValue: auth }],
    });
    const fixture = TestBed.createComponent(DashboardComponent);
    fixture.detectChanges();
    return fixture;
  }

  it('renders the navigation shell with the sidebar closed by default', () => {
    const fixture = mount();
    const cmp = fixture.componentInstance;

    expect(cmp.sidebarOpen()).toBe(false);
    expect(fixture.nativeElement.querySelector('aside.sidebar')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('.dashboard-layout.sidebar-open')).toBeNull();
  });

  it('renders exactly five hub links in the sidebar', () => {
    const fixture = mount();
    const links = fixture.nativeElement.querySelectorAll('aside.sidebar nav a');
    expect(links.length).toBe(5);
  });

  it('highlights the hub that matches the active hub signal', () => {
    const fixture = mount();
    const cmp = fixture.componentInstance;

    cmp.activeHub.set('pipeline');
    fixture.detectChanges();

    const active = fixture.nativeElement.querySelector('aside.sidebar nav a.active');
    expect(active).not.toBeNull();
    expect(active.textContent).toContain('Pipeline');
  });

  it('exposes the hub tab bar for routed hubs but not for profile', () => {
    const fixture = mount();
    const cmp = fixture.componentInstance;

    cmp.activeHub.set('discover');
    expect(cmp.hubTabs()?.id).toBe('discover');

    cmp.activeHub.set('profile');
    expect(cmp.hubTabs()).toBeNull();

    cmp.activeHub.set(null);
    expect(cmp.hubTabs()).toBeNull();
  });

  it('toggles and closes the sidebar via signal updates', () => {
    const fixture = mount();
    const cmp = fixture.componentInstance;

    cmp.toggleSidebar();
    expect(cmp.sidebarOpen()).toBe(true);
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.dashboard-layout.sidebar-open')).not.toBeNull();

    cmp.closeSidebar();
    expect(cmp.sidebarOpen()).toBe(false);
  });

  it('delegates logout to the auth service', () => {
    const logout = vi.fn();
    const fixture = mount(makeAuth({ logout }));

    fixture.componentInstance.logout();

    expect(logout).toHaveBeenCalled();
  });
});
