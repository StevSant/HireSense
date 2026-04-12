# Standalone Components & Lazy Routes

No NgModules. All components are standalone with lazy-loaded routes.

## Component Declaration

```typescript
@Component({
  selector: 'app-tracking',
  standalone: true,
  imports: [FormsModule, TitleCasePipe, DatePipe],
  templateUrl: './tracking.component.html',
  styleUrl: './tracking.component.scss',
})
export class TrackingComponent { ... }
```

## Route Registration

Use `loadComponent()` for code splitting:

```typescript
{
  path: 'tracking',
  loadComponent: () =>
    import('./pages/tracking/tracking.component')
      .then(m => m.TrackingComponent),
}
```

## Rules

- Every component is `standalone: true`
- No `NgModule` declarations
- Import pipes and directives directly in the component's `imports` array
- All page routes use `loadComponent()` for lazy loading
- Auth-protected routes use `canActivate: [authGuard]` at the parent level
