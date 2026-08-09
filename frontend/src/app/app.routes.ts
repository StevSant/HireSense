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
        children: [
          { path: '', redirectTo: 'cv', pathMatch: 'full' },
          {
            path: 'cv',
            loadComponent: () =>
              import('./pages/profile/tabs/cv-tab/profile-cv-tab.component').then(
                (m) => m.ProfileCvTabComponent,
              ),
          },
          {
            path: 'personal',
            loadComponent: () =>
              import('./pages/profile/tabs/personal-tab/profile-personal-tab.component').then(
                (m) => m.ProfilePersonalTabComponent,
              ),
          },
          {
            path: 'cover-letters',
            loadComponent: () =>
              import('./pages/profile/tabs/cover-letters-tab/profile-cover-letters-tab.component').then(
                (m) => m.ProfileCoverLettersTabComponent,
              ),
          },
        ],
      },
      {
        path: 'applications',
        loadComponent: () =>
          import('./pages/applications/applications.component').then(
            (m) => m.ApplicationsComponent,
          ),
      },
      {
        path: 'applications/signals',
        loadComponent: () =>
          import('./pages/applications/components/inbox-signals.component').then(
            (m) => m.InboxSignalsComponent,
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
        path: 'opportunities',
        loadComponent: () =>
          import('./pages/opportunities/opportunities.component').then(
            (m) => m.OpportunitiesComponent,
          ),
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
      {
        path: 'admin/scheduler',
        canActivate: [adminGuard],
        loadComponent: () =>
          import('./pages/admin/scheduler/scheduler.component').then((m) => m.SchedulerComponent),
      },
      {
        path: 'admin/notifications',
        canActivate: [adminGuard],
        loadComponent: () =>
          import('./pages/admin/notifications/notifications.component').then(
            (m) => m.NotificationsComponent,
          ),
      },
      {
        path: 'autopilot/drafts',
        loadComponent: () =>
          import('./pages/autopilot/drafts/drafts.component').then((m) => m.DraftsComponent),
      },
      { path: 'account', redirectTo: 'profile', pathMatch: 'full' },
    ],
  },
  { path: '**', redirectTo: 'login' },
];
