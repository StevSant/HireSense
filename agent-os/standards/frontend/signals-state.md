# Signals-Only State Management

Use Angular signals for all component reactive state. This aligns with Angular's direction away from RxJS for local state.

## Usage

```typescript
// Component state
items = signal<Item[]>([]);
loading = signal(false);
error = signal('');

// Derived state
count = computed(() => this.items().length);

// Mutations
this.loading.set(true);
this.items.update(list => [...list, newItem]);
```

## Rules

- Use `signal()` for mutable state, `computed()` for derived state
- No `BehaviorSubject` or `ReplaySubject` for component-local state
- RxJS is fine for HTTP calls (`HttpClient` returns `Observable`) — subscribe in the component and write results into signals
- Use `signal.update()` for immutable transforms (arrays, objects)
- Use `signal.set()` for primitive replacements
