import { HttpErrorResponse } from '@angular/common/http';
import { Injectable, signal } from '@angular/core';
import { Observable } from 'rxjs';

interface LlmRunState {
  readonly running: boolean;
  readonly result: unknown;
  readonly error: string;
}

const IDLE_STATE: LlmRunState = { running: false, result: null, error: '' };

/**
 * Generic keyed coordinator for LLM-backed requests.
 *
 * Lives at the root injector so an in-flight generation survives the
 * originating component being destroyed (tab switch, page navigation).
 * Each call site picks its own key (e.g. an application or job id) so
 * unrelated runs never clash; results and errors are cached per key and
 * stay readable after the run completes, even from a freshly-mounted
 * component that never saw the request start.
 *
 * Mirrors {@link CvOptimizationRunnerService} and
 * {@link CoverLetterRunnerService}, generalized for call sites that need
 * to read back the run's own result rather than refetch an aggregate.
 */
@Injectable({ providedIn: 'root' })
export class LlmRunnerService {
  private states = signal<ReadonlyMap<string, LlmRunState>>(new Map());

  isRunning(key: string): boolean {
    return this.stateFor(key).running;
  }

  result<T>(key: string): T | null {
    return (this.stateFor(key).result as T | null) ?? null;
  }

  error(key: string): string {
    return this.stateFor(key).error;
  }

  /**
   * Starts `source` under `key`; a second call for the same key while one
   * is already in flight is ignored. `mapError` turns a failed response
   * into the text shown to the user. `onNext`, if given, fires
   * synchronously alongside the cache write — for local, same-instance
   * side effects (e.g. seeding an editable field) on top of the cached
   * value read back via {@link result}.
   */
  run<T>(
    key: string,
    source: Observable<T>,
    mapError: (err: HttpErrorResponse) => string,
    onNext?: (result: T) => void,
  ): void {
    if (this.isRunning(key)) return;
    this.patch(key, { running: true, error: '' });
    source.subscribe({
      next: (result) => {
        this.patch(key, { running: false, result });
        onNext?.(result);
      },
      error: (err: HttpErrorResponse) => {
        this.patch(key, { running: false, error: mapError(err) });
      },
    });
  }

  /** Drops any cached state for `key`, e.g. before starting a fresh run. */
  clear(key: string): void {
    this.states.update((states) => {
      if (!states.has(key)) return states;
      const next = new Map(states);
      next.delete(key);
      return next;
    });
  }

  private stateFor(key: string): LlmRunState {
    return this.states().get(key) ?? IDLE_STATE;
  }

  private patch(key: string, partial: Partial<LlmRunState>): void {
    this.states.update((states) => {
      const next = new Map(states);
      next.set(key, { ...(next.get(key) ?? IDLE_STATE), ...partial });
      return next;
    });
  }
}
