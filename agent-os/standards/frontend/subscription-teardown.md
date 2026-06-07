# Subscription Teardown

Every component subscription must be torn down when the component is destroyed. Standardize on `inject(DestroyRef)` + `takeUntilDestroyed(this.destroyRef)`.

HTTP observables complete on response, so they aren't classic memory leaks — but an in-flight response that arrives *after* navigation will still write into the destroyed component's signals, and any future long-lived stream (WebSocket, polling, a shared `Subject`) would leak outright. Piping every subscription through `takeUntilDestroyed` removes that whole class of bug uniformly.

## Pattern

```typescript
import { Component, DestroyRef, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

export class TrackingComponent {
  private readonly destroyRef = inject(DestroyRef);
  private tracking = inject(TrackingService);

  load(): void {
    this.tracking
      .list()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (apps) => this.applications.set(apps),
        error: (err) => this.error.set(err.error?.detail ?? 'Failed to load'),
      });
  }
}
```

## Rules

- Add `private readonly destroyRef = inject(DestroyRef);` to every component that subscribes to an observable.
- Put `.pipe(takeUntilDestroyed(this.destroyRef))` immediately before `.subscribe(...)` — after any existing operators.
- **Always pass the explicit `destroyRef`.** The zero-arg `takeUntilDestroyed()` only works inside an injection context (field initializer / constructor). Subscriptions in lifecycle hooks (`ngOnInit`), event handlers, and `next`/`error` callbacks run *outside* that context, so the argument-less form throws. The explicit form works everywhere, so use it unconditionally for consistency.
- Preserve existing operators — append `takeUntilDestroyed` to the pipe, don't replace anything:

  ```typescript
  .pipe(
    debounceTime(environment.feedbackRefetchDebounceMs),
    takeUntilDestroyed(this.destroyRef),
  )
  .subscribe(...)
  ```

  ```typescript
  .pipe(
    finalize(() => this.loading.set(false)),
    takeUntilDestroyed(this.destroyRef),
  )
  .subscribe(...)
  ```

## Exception: intentionally long-lived root services

Root-scoped (`providedIn: 'root'`) coordinator services that exist *specifically* so a subscription survives component destruction (e.g. `CvOptimizationRunnerService`, `CoverLetterRunnerService` — an in-flight CV/cover-letter generation must outlive the tab that started it) do **not** use `takeUntilDestroyed`. Their lifetime is the root injector, so tying teardown to it adds nothing and contradicts their purpose. This exception applies only to services whose documented job is to outlive components — not to ordinary components.
