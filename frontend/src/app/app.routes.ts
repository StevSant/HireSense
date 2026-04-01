import { Routes } from '@angular/router';
import { authGuard } from './core/guards/auth.guard';

export const routes: Routes = [
  { path: 'login', loadComponent: () => import('./pages/login/login.component').then(m => m.LoginComponent) },
  { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
  {
    path: 'dashboard',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/dashboard/dashboard.component').then(m => m.DashboardComponent),
    children: [
      { path: '', redirectTo: 'ingestion', pathMatch: 'full' },
      { path: 'ingestion', loadComponent: () => import('./pages/ingestion/ingestion.component').then(m => m.IngestionComponent) },
      { path: 'profile', loadComponent: () => import('./pages/profile/profile.component').then(m => m.ProfileComponent) },
      { path: 'matching', loadComponent: () => import('./pages/matching/matching.component').then(m => m.MatchingComponent) },
      { path: 'optimization', loadComponent: () => import('./pages/optimization/optimization.component').then(m => m.OptimizationComponent) },
    ],
  },
  { path: '**', redirectTo: 'login' },
];
