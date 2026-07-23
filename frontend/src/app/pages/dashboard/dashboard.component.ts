import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterOutlet, RouterLink, Router, NavigationEnd } from '@angular/router';
import { filter } from 'rxjs/operators';
import { AuthService } from '../../core/services/auth.service';
import { HUBS, HubTabsComponent, hubForUrl } from '../../core/nav';
import { environment } from '../../../environments/environment';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [RouterOutlet, RouterLink, HubTabsComponent],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss',
})
export class DashboardComponent {
  private auth = inject(AuthService);
  private router = inject(Router);
  private destroyRef = inject(DestroyRef);

  sidebarOpen = signal(false);
  readonly demoMode = environment.demo;
  // router.url at construction time is already the post-redirect URL; the NavigationEnd
  // subscription uses urlAfterRedirects for the same reason on later navigations.
  activeHub = signal(hubForUrl(this.router.url));

  hubTabs = computed(() => {
    const id = this.activeHub();
    // 'profile' uses its own internal signal tabs; suppress the shared hub tab bar for it.
    if (!id || id === 'profile') return null;
    return HUBS.find((hub) => hub.id === id) ?? null;
  });

  constructor() {
    this.router.events
      .pipe(
        filter((e): e is NavigationEnd => e instanceof NavigationEnd),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((e) => {
        this.sidebarOpen.set(false);
        this.activeHub.set(hubForUrl(e.urlAfterRedirects));
      });
  }

  toggleSidebar(): void {
    this.sidebarOpen.update((v) => !v);
  }

  closeSidebar(): void {
    this.sidebarOpen.set(false);
  }

  logout(): void {
    this.auth.logout();
  }
}
