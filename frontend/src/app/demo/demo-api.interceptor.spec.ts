import {
  HttpClient,
  HttpErrorResponse,
  provideHttpClient,
  withInterceptors,
} from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { firstValueFrom } from 'rxjs';
import { describe, expect, it } from 'vitest';
import { demoApiInterceptor } from './demo-api.interceptor';

function setup(): HttpClient {
  TestBed.configureTestingModule({
    providers: [provideHttpClient(withInterceptors([demoApiInterceptor]))],
  });
  return TestBed.inject(HttpClient);
}

describe('demoApiInterceptor', () => {
  it('auto-authenticates a non-admin demo visitor', async () => {
    const user = await firstValueFrom(
      setup().get<{ username: string; role: string }>('/api/auth/me'),
    );

    expect(user).toEqual({ username: 'demo.candidate', role: 'user' });
  });

  it('returns a coherent ranked job collection and detail', async () => {
    const http = setup();
    const page = await firstValueFrom(
      http.get<{ jobs: { id: string; match_score: number }[]; total: number }>(
        '/api/ingestion/jobs',
      ),
    );
    const detail = await firstValueFrom(
      http.get<{ id: string; title: string }>(`/api/ingestion/jobs/${page.jobs[0].id}`),
    );

    expect(page.total).toBeGreaterThanOrEqual(3);
    expect(page.jobs[0].match_score).toBeGreaterThan(page.jobs[1].match_score);
    expect(detail.id).toBe(page.jobs[0].id);
    expect(detail.title).toBeTruthy();
  });

  it('returns prepared pipeline and analytics content', async () => {
    const http = setup();
    const applications = await firstValueFrom(
      http.get<{ id: string; has_match: boolean }[]>('/api/applications'),
    );
    const funnel = await firstValueFrom(
      http.get<{ total_applications: number; stages: unknown[] }>('/api/analytics/funnel'),
    );

    expect(applications.length).toBeGreaterThanOrEqual(3);
    expect(applications[0].has_match).toBe(true);
    expect(funnel.total_applications).toBe(applications.length);
    expect(funnel.stages.length).toBeGreaterThan(2);
  });

  it('serves a precomputed match result for the featured application', async () => {
    const match = await firstValueFrom(
      setup().post<{ overall_score: number; matched_skills: string[] }>(
        '/api/applications/demo-app-1/match',
        {},
      ),
    );

    expect(match.overall_score).toBeGreaterThan(0.8);
    expect(match.matched_skills).toContain('Angular');
  });

  it('serves the complete featured application journey', async () => {
    const application = await firstValueFrom(
      setup().get<{
        id: string;
        latest_match: unknown;
        latest_optimization: unknown;
        latest_interview_prep: unknown;
        latest_cover_letter: unknown;
      }>('/api/applications/demo-app-1'),
    );

    expect(application.id).toBe('demo-app-1');
    expect(application.latest_match).toBeTruthy();
    expect(application.latest_optimization).toBeTruthy();
    expect(application.latest_interview_prep).toBeTruthy();
    expect(application.latest_cover_letter).toBeTruthy();
  });

  it('fills every insight section and portfolio engagement', async () => {
    const http = setup();
    const [market, skillGap, comp, focus, engagement] = await Promise.all([
      firstValueFrom(http.get<{ top_skills: unknown[] }>('/api/analytics/market')),
      firstValueFrom(http.get<{ missing: unknown[] }>('/api/analytics/skill-gap')),
      firstValueFrom(http.get<{ insufficient_data: boolean }>('/api/analytics/comp')),
      firstValueFrom(http.get<{ insufficient_data: boolean }>('/api/analytics/focus')),
      firstValueFrom(
        http.get<{ configured: boolean; visits: unknown[] }>('/api/portfolio/engagement'),
      ),
    ]);

    expect(market.top_skills.length).toBeGreaterThan(2);
    expect(skillGap.missing.length).toBeGreaterThan(1);
    expect(comp.insufficient_data).toBe(false);
    expect(focus.insufficient_data).toBe(false);
    expect(engagement.configured).toBe(true);
    expect(engagement.visits.length).toBeGreaterThan(0);
  });

  it('loads a synthetic candidate profile instead of an upload prompt', async () => {
    const profiles = await firstValueFrom(
      setup().get<{ name: string; skills: string[] }[]>('/api/profile/list'),
    );

    expect(profiles[0].name).toBe('Alex Rivera');
    expect(profiles[0].skills).toContain('Angular');
  });

  it('rejects unsupported mutations with a clear read-only response', async () => {
    try {
      await firstValueFrom(setup().post('/api/profile/upload', { file: 'private' }));
      throw new Error('Expected the demo API to reject an upload');
    } catch (error) {
      expect(error).toBeInstanceOf(HttpErrorResponse);
      expect((error as HttpErrorResponse).status).toBe(403);
      expect((error as HttpErrorResponse).error.detail).toContain('read-only');
    }
  });
});
