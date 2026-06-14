import { Routes } from '@angular/router';
import { authGuard } from './core/guards/auth.guard';
import { adminGuard } from './core/guards/admin.guard';

export const routes: Routes = [
  {
    path: 'login',
    loadComponent: () => import('./pages/login/login.component').then((m) => m.LoginComponent),
  },
  { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
  {
    path: 'dashboard',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./pages/dashboard/dashboard.component').then((m) => m.DashboardComponent),
    children: [
      { path: '', redirectTo: 'ingestion', pathMatch: 'full' },
      {
        path: 'ingestion',
        loadComponent: () =>
          import('./pages/ingestion/ingestion.component').then((m) => m.IngestionComponent),
      },
      {
        path: 'profile',
        loadComponent: () =>
          import('./pages/profile/profile.component').then((m) => m.ProfileComponent),
      },
      {
        path: 'applications',
        loadComponent: () =>
          import('./pages/applications/applications.component').then(
            (m) => m.ApplicationsComponent,
          ),
      },
      {
        path: 'applications/:id',
        loadComponent: () =>
          import('./pages/applications/application-detail.component').then(
            (m) => m.ApplicationDetailComponent,
          ),
      },
      {
        path: 'matching',
        loadComponent: () =>
          import('./pages/matching/matching.component').then((m) => m.MatchingComponent),
      },
      {
        path: 'optimization',
        loadComponent: () =>
          import('./pages/optimization/optimization.component').then(
            (m) => m.OptimizationComponent,
          ),
      },
      // Tracking/Pipeline was merged into Applications; keep a redirect so old links/bookmarks work.
      { path: 'tracking', redirectTo: 'applications', pathMatch: 'full' },
      {
        path: 'outreach',
        loadComponent: () =>
          import('./pages/outreach/outreach.component').then((m) => m.OutreachComponent),
      },
      {
        path: 'autohunt',
        loadComponent: () =>
          import('./pages/autohunt/autohunt.component').then((m) => m.AutohuntComponent),
      },
      {
        path: 'analytics',
        loadComponent: () =>
          import('./pages/analytics/analytics.component').then((m) => m.AnalyticsComponent),
      },
      {
        path: 'company/:name',
        loadComponent: () =>
          import('./pages/company/company.component').then((m) => m.CompanyComponent),
      },
      {
        path: 'job/:id',
        loadComponent: () => import('./pages/job/job.component').then((m) => m.JobDetailComponent),
      },
      {
        path: 'interview',
        loadComponent: () =>
          import('./pages/interview/interview.component').then((m) => m.InterviewComponent),
      },
      {
        path: 'admin/llm-settings',
        canActivate: [adminGuard],
        loadComponent: () =>
          import('./pages/admin/admin-llm-settings.component').then(
            (m) => m.AdminLLMSettingsComponent,
          ),
      },
      {
        path: 'admin/usage',
        canActivate: [adminGuard],
        loadComponent: () =>
          import('./pages/admin/admin-usage.component').then((m) => m.AdminUsageComponent),
      },
      { path: 'account', redirectTo: 'profile', pathMatch: 'full' },
    ],
  },
  { path: '**', redirectTo: 'login' },
];
