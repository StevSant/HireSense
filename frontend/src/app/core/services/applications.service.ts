import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { environment } from '../../../environments/environment';
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
  private http = inject(HttpClient);
  private base = `${environment.apiUrl}/applications`;

  /** One page of applications, with the server's unfiltered total. */
  listPage(limit: number, offset: number): Observable<PagedResult<ApplicationListItem>> {
    return this.http
      .get<ApplicationListItem[]>(this.base, {
        params: new HttpParams().set('limit', limit).set('offset', offset),
        observe: 'response',
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
    return this.http
      .get<CoverLetterLibraryItem[]>(`${this.base}/cover-letters`, {
        params: new HttpParams().set('limit', limit).set('offset', offset),
        observe: 'response',
      })
      .pipe(map(toPagedResult));
  }

  /** The whole cover letter library — the card sorts and searches it locally. */
  listAllCoverLetters(): Observable<PagedResult<CoverLetterLibraryItem>> {
    return fetchAllPages((limit, offset) => this.listCoverLettersPage(limit, offset));
  }

  get(id: string): Observable<ApplicationAggregate> {
    return this.http.get<ApplicationAggregate>(`${this.base}/${id}`);
  }

  createFromJob(jobId: string): Observable<ApplicationAggregate> {
    return this.http.post<ApplicationAggregate>(this.base, { job_id: jobId });
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
    return this.http.post<ApplicationAggregate>(this.base, payload);
  }

  remove(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/${id}`);
  }

  updateSnapshot(
    id: string,
    payload: { description?: string; required_skills?: string[] },
  ): Observable<ApplicationAggregate> {
    return this.http.put<ApplicationAggregate>(`${this.base}/${id}/job-snapshot`, payload);
  }

  regenerateSkills(id: string): Observable<ApplicationAggregate> {
    return this.http.post<ApplicationAggregate>(
      `${this.base}/${id}/job-snapshot/regenerate-skills`,
      {},
    );
  }

  generateMatch(id: string, cvLanguage: string): Observable<ApplicationMatch> {
    return this.http.post<ApplicationMatch>(`${this.base}/${id}/match`, {
      cv_language: cvLanguage,
    });
  }

  generateOptimization(
    id: string,
    payload: { cv_language: string; match_id?: string },
  ): Observable<CvOptimization> {
    return this.http.post<CvOptimization>(`${this.base}/${id}/optimize`, payload);
  }

  generateInterviewPrep(id: string): Observable<ApplicationInterviewPrep> {
    return this.http.post<ApplicationInterviewPrep>(`${this.base}/${id}/interview-prep`, {});
  }

  generateCoverLetter(
    id: string,
    payload: { cv_language: string; tone?: string },
  ): Observable<CoverLetter> {
    return this.http.post<CoverLetter>(`${this.base}/${id}/cover-letter`, payload);
  }

  downloadCvPdf(id: string): Observable<Blob> {
    return this.http.get(`${this.base}/${id}/cv.pdf`, { responseType: 'blob' });
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
    return this.http.get(`${this.base}/${id}/cv.pdf`, { params, responseType: 'blob' });
  }

  /** Compile the user's untouched profile CV (no optimization required). */
  downloadOriginalCvPdf(id: string, language: 'en' | 'es' = 'en'): Observable<Blob> {
    const params = new HttpParams().set('original', 'true').set('language', language);
    return this.http.get(`${this.base}/${id}/cv.pdf`, { params, responseType: 'blob' });
  }

  downloadCoverLetterPdf(id: string): Observable<Blob> {
    return this.http.get(`${this.base}/${id}/cover-letter.pdf`, { responseType: 'blob' });
  }

  downloadBundle(id: string): Observable<Blob> {
    return this.http.get(`${this.base}/${id}/bundle.zip`, { responseType: 'blob' });
  }

  markApplied(id: string): Observable<ApplicationAggregate> {
    return this.http.post<ApplicationAggregate>(`${this.base}/${id}/mark-applied`, {});
  }
}
