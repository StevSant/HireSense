import { Injectable, inject } from '@angular/core';
import { HttpParams } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { ApiClient, API_ROUTES } from '@core/api';
import { PagedResult } from '@core/contracts/paged-result.model';
import { fetchAllPages } from '../utils/fetch-all-pages';
import { toPagedResult } from '../utils/to-paged-result';
import { ApplicationAggregate } from '@core/contracts/application-aggregate.model';
import { ApplicationListItem } from '@core/contracts/application-list-item.model';
import { ApplicationMatch } from '@core/contracts/application-match.model';
import { CvOptimization } from '@core/contracts/cv-optimization.model';
import { ApplicationInterviewPrep } from '@core/contracts/application-interview-prep.model';
import { CoverLetter } from '@core/contracts/cover-letter.model';
import { CoverLetterLibraryItem } from '@core/contracts/cover-letter-library-item.model';

@Injectable({ providedIn: 'root' })
export class ApplicationsService {
  private api = inject(ApiClient);

  /** One page of applications, with the server's unfiltered total. */
  listPage(limit: number, offset: number): Observable<PagedResult<ApplicationListItem>> {
    return this.api
      .getResponse<ApplicationListItem[]>(API_ROUTES.applications.root(), {
        params: new HttpParams().set('limit', limit).set('offset', offset),
      })
      .pipe(map(toPagedResult));
  }

  /**
   * Every application, walked page by page.
   *
   * The screens that consume this (the list, the outreach picker, the interview
   * prep list) sort, filter and count client-side, so fetching only the default
   * first page silently dropped rows and made the status-tab badge counts wrong
   * once the user passed one page of applications.
   */
  listAll(): Observable<PagedResult<ApplicationListItem>> {
    return fetchAllPages((limit, offset) => this.listPage(limit, offset));
  }

  /** One page of the cross-application cover letter library. */
  listCoverLettersPage(
    limit: number,
    offset: number,
  ): Observable<PagedResult<CoverLetterLibraryItem>> {
    return this.api
      .getResponse<CoverLetterLibraryItem[]>(API_ROUTES.applications.coverLetters(), {
        params: new HttpParams().set('limit', limit).set('offset', offset),
      })
      .pipe(map(toPagedResult));
  }

  /** The whole cover letter library — the card sorts and searches it locally. */
  listAllCoverLetters(): Observable<PagedResult<CoverLetterLibraryItem>> {
    return fetchAllPages((limit, offset) => this.listCoverLettersPage(limit, offset));
  }

  get(id: string): Observable<ApplicationAggregate> {
    return this.api.get<ApplicationAggregate>(API_ROUTES.applications.byId({ id }));
  }

  createFromJob(jobId: string): Observable<ApplicationAggregate> {
    return this.api.post<ApplicationAggregate>(API_ROUTES.applications.root(), { job_id: jobId });
  }

  createManual(payload: {
    title: string;
    company: string;
    description: string;
    url?: string;
    notes?: string;
    location?: string;
    remote_modality?: 'remote' | 'hybrid' | 'on_site';
    salary_range?: string;
    source?: string;
    posted_date?: string;
  }): Observable<ApplicationAggregate> {
    return this.api.post<ApplicationAggregate>(API_ROUTES.applications.root(), payload);
  }

  remove(id: string): Observable<void> {
    return this.api.delete<void>(API_ROUTES.applications.byId({ id }));
  }

  updateSnapshot(
    id: string,
    payload: { description?: string; required_skills?: string[] },
  ): Observable<ApplicationAggregate> {
    return this.api.put<ApplicationAggregate>(API_ROUTES.applications.jobSnapshot({ id }), payload);
  }

  regenerateSkills(id: string): Observable<ApplicationAggregate> {
    return this.api.post<ApplicationAggregate>(
      API_ROUTES.applications.regenerateSkills({ id }),
      {},
    );
  }

  generateMatch(id: string, cvLanguage: string): Observable<ApplicationMatch> {
    return this.api.post<ApplicationMatch>(API_ROUTES.applications.match({ id }), {
      cv_language: cvLanguage,
    });
  }

  generateOptimization(
    id: string,
    payload: { cv_language: string; match_id?: string },
  ): Observable<CvOptimization> {
    return this.api.post<CvOptimization>(API_ROUTES.applications.optimize({ id }), payload);
  }

  generateInterviewPrep(id: string): Observable<ApplicationInterviewPrep> {
    return this.api.post<ApplicationInterviewPrep>(
      API_ROUTES.applications.interviewPrep({ id }),
      {},
    );
  }

  generateCoverLetter(
    id: string,
    payload: { cv_language: string; tone?: string },
  ): Observable<CoverLetter> {
    return this.api.post<CoverLetter>(API_ROUTES.applications.coverLetter({ id }), payload);
  }

  downloadCvPdf(id: string): Observable<Blob> {
    return this.api.getBlob(API_ROUTES.applications.cvPdf({ id }));
  }

  /**
   * Fetch a CV PDF as a blob for inline preview. `original: true` compiles the
   * untouched profile CV in `language`; otherwise the latest optimized CV.
   */
  fetchCvPdf(
    id: string,
    opts: { original?: boolean; language?: 'en' | 'es' } = {},
  ): Observable<Blob> {
    let params = new HttpParams();
    if (opts.original) params = params.set('original', 'true');
    if (opts.language) params = params.set('language', opts.language);
    return this.api.getBlob(API_ROUTES.applications.cvPdf({ id }), { params });
  }

  /** Compile the user's untouched profile CV (no optimization required). */
  downloadOriginalCvPdf(id: string, language: 'en' | 'es' = 'en'): Observable<Blob> {
    const params = new HttpParams().set('original', 'true').set('language', language);
    return this.api.getBlob(API_ROUTES.applications.cvPdf({ id }), { params });
  }

  downloadCoverLetterPdf(id: string): Observable<Blob> {
    return this.api.getBlob(API_ROUTES.applications.coverLetterPdf({ id }));
  }

  downloadBundle(id: string): Observable<Blob> {
    return this.api.getBlob(API_ROUTES.applications.bundleZip({ id }));
  }

  markApplied(id: string): Observable<ApplicationAggregate> {
    return this.api.post<ApplicationAggregate>(API_ROUTES.applications.markApplied({ id }), {});
  }
}
