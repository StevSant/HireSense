import { Routes } from '@angular/router';
import { authGuard } from './core/guards/auth.guard';
import { adminGuard } from './core/guards/admin.guard';
import { AnalyticsStore } from './pages/analytics/analytics.store';

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
            path: 'apply',
            loadComponent: () =>
              import('./pages/profile/tabs/apply-tab/profile-apply-tab.component').then(
                (m) => m.ProfileApplyTabComponent,
              ),
          },
          {
            path: 'sources',
            loadComponent: () =>
              import('./pages/profile/tabs/sources-tab/profile-sources-tab.component').then(
                (m) => m.ProfileSourcesTabComponent,
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
        path: 'submission',
        loadComponent: () =>
          import('./pages/submission/queue/queue.component').then((m) => m.QueueComponent),
      },
      {
        path: 'autohunt',
        loadComponent: () =>
          import('./pages/autohunt/autohunt.component').then((m) => m.AutohuntComponent),
      },
      {
        path: 'analytics',
        // Route-scoped so the shell and every tab share one store that is
        // discarded on leave (no stale figures on a later visit).
        providers: [AnalyticsStore],
        loadComponent: () =>
          import('./pages/analytics/analytics.component').then((m) => m.AnalyticsComponent),
        children: [
          { path: '', redirectTo: 'pay', pathMatch: 'full' },
          {
            path: 'pay',
            loadComponent: () =>
              import('./pages/analytics/tabs/pay-tab/analytics-pay-tab.component').then(
                (m) => m.AnalyticsPayTabComponent,
              ),
          },
          {
            path: 'fit',
            loadComponent: () =>
              import('./pages/analytics/tabs/fit-tab/analytics-fit-tab.component').then(
                (m) => m.AnalyticsFitTabComponent,
              ),
          },
          {
            path: 'pipeline',
            loadComponent: () =>
              import('./pages/analytics/tabs/pipeline-tab/analytics-pipeline-tab.component').then(
                (m) => m.AnalyticsPipelineTabComponent,
              ),
          },
          {
            path: 'market',
            loadComponent: () =>
              import('./pages/analytics/tabs/market-tab/analytics-market-tab.component').then(
                (m) => m.AnalyticsMarketTabComponent,
              ),
          },
          {
            path: 'portfolio',
            loadComponent: () =>
              import('./pages/analytics/tabs/portfolio-tab/analytics-portfolio-tab.component').then(
                (m) => m.AnalyticsPortfolioTabComponent,
              ),
          },
        ],
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
        path: 'admin/runs',
        canActivate: [adminGuard],
        loadComponent: () =>
          import('./pages/admin/runs/runs.component').then((m) => m.RunsComponent),
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
