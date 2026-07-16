import { HttpErrorResponse } from '@angular/common/http';
import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Observable, Subject, of } from 'rxjs';
import { LlmRunnerService } from './llm-runner.service';

describe('LlmRunnerService', () => {
  it('reports idle state for a key that has never run', () => {
    const service = TestBed.inject(LlmRunnerService);

    expect(service.isRunning('never-run')).toBe(false);
    expect(service.result('never-run')).toBeNull();
    expect(service.error('never-run')).toBe('');
  });

  it('marks a key running while in flight, then caches the result on completion', () => {
    const service = TestBed.inject(LlmRunnerService);
    const subject = new Subject<{ ok: boolean }>();

    service.run('key-1', subject.asObservable(), () => 'mapped error');

    expect(service.isRunning('key-1')).toBe(true);
    expect(service.result('key-1')).toBeNull();

    subject.next({ ok: true });
    subject.complete();

    expect(service.isRunning('key-1')).toBe(false);
    expect(service.result<{ ok: boolean }>('key-1')).toEqual({ ok: true });
  });

  it('maps errors via the caller-supplied mapper and clears running without caching a result', () => {
    const service = TestBed.inject(LlmRunnerService);
    const subject = new Subject<unknown>();
    const mapError = vi.fn(() => 'mapped failure');

    service.run('err-key', subject.asObservable(), mapError);
    subject.error(new HttpErrorResponse({ status: 500 }));

    expect(mapError).toHaveBeenCalled();
    expect(service.isRunning('err-key')).toBe(false);
    expect(service.error('err-key')).toBe('mapped failure');
    expect(service.result('err-key')).toBeNull();
  });

  it('ignores a second run() for the same key while the first is still in flight', () => {
    const service = TestBed.inject(LlmRunnerService);
    let subscribeCount = 0;
    const source = new Observable<number>(() => {
      subscribeCount++;
    });

    service.run('busy-key', source, () => 'err');
    service.run('busy-key', source, () => 'err');

    expect(subscribeCount).toBe(1);
  });

  it('invokes onNext synchronously with the result in addition to caching it', () => {
    const service = TestBed.inject(LlmRunnerService);
    const onNext = vi.fn();

    service.run('onnext-key', of({ value: 'hi' }), () => 'err', onNext);

    expect(onNext).toHaveBeenCalledWith({ value: 'hi' });
  });

  it('clear() drops cached state for a key', () => {
    const service = TestBed.inject(LlmRunnerService);

    service.run('clear-key', of({ a: 1 }), () => 'err');
    expect(service.result('clear-key')).toEqual({ a: 1 });

    service.clear('clear-key');

    expect(service.result('clear-key')).toBeNull();
    expect(service.error('clear-key')).toBe('');
    expect(service.isRunning('clear-key')).toBe(false);
  });

  it('keeps a run in flight — and later caches its result — after the component that started it is destroyed', () => {
    const service = TestBed.inject(LlmRunnerService);
    const subject = new Subject<{ value: string }>();

    // A host component that kicks off a run in its constructor, the way a
    // real page component would from a click handler. No takeUntilDestroyed
    // is used here, or in the service — that's the point being verified.
    @Component({ template: '', standalone: true })
    class HostComponent {
      constructor() {
        service.run('survive-destroy-key', subject.asObservable(), () => 'mapped');
      }
    }

    const fixture = TestBed.createComponent(HostComponent);
    fixture.detectChanges();

    expect(service.isRunning('survive-destroy-key')).toBe(true);

    // Destroy the originating component — any component-owned subscription
    // (e.g. takeUntilDestroyed) would be torn down here.
    fixture.destroy();

    // The run is root-owned, so it's still in flight after destroy.
    expect(service.isRunning('survive-destroy-key')).toBe(true);
    expect(service.result('survive-destroy-key')).toBeNull();

    // Completing it after destroy still lands in the cache, readable by a
    // freshly-mounted component that never saw the request start.
    subject.next({ value: 'done' });
    subject.complete();

    expect(service.isRunning('survive-destroy-key')).toBe(false);
    expect(service.result<{ value: string }>('survive-destroy-key')).toEqual({ value: 'done' });
  });

  it('surfaces an error that arrives after the originating component is destroyed', () => {
    const service = TestBed.inject(LlmRunnerService);
    const subject = new Subject<unknown>();

    @Component({ template: '', standalone: true })
    class HostComponent {
      constructor() {
        service.run('survive-destroy-error-key', subject.asObservable(), () => 'late failure');
      }
    }

    const fixture = TestBed.createComponent(HostComponent);
    fixture.detectChanges();
    fixture.destroy();

    subject.error(new HttpErrorResponse({ status: 503 }));

    expect(service.isRunning('survive-destroy-error-key')).toBe(false);
    expect(service.error('survive-destroy-error-key')).toBe('late failure');
  });
});
