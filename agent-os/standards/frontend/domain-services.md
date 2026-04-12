# Domain Services

Each backend domain has a matching Angular service in `core/services/` that wraps HTTP calls. Components never inject `HttpClient` directly.

## Service Pattern

```typescript
// core/services/tracking.service.ts
@Injectable({ providedIn: 'root' })
export class TrackingService {
  constructor(private http: HttpClient) {}

  list(status?: ApplicationStatus): Observable<TrackedApplication[]> {
    const params = status ? { status } : {};
    return this.http.get<TrackedApplication[]>(
      `${environment.apiUrl}/tracking`, { params }
    );
  }

  create(req: CreateApplicationRequest): Observable<TrackedApplication> {
    return this.http.post<TrackedApplication>(
      `${environment.apiUrl}/tracking`, req
    );
  }
}
```

## Component Usage

```typescript
export class TrackingComponent {
  constructor(private tracking: TrackingService) {}

  loadApplications(): void {
    this.loading.set(true);
    this.tracking.list(this.statusFilter()).subscribe({
      next: apps => {
        this.applications.set(apps);
        this.loading.set(false);
      },
      error: err => { ... },
    });
  }
}
```

## Rules

- One service per backend domain in `core/services/`
- Services return `Observable<T>` — components subscribe and write to signals
- Services handle URL construction and params
- Components handle loading/error state
- `providedIn: 'root'` for all domain services
- File naming: `{domain}.service.ts`
