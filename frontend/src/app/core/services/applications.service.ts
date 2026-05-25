import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { ApplicationAggregate } from '../../pages/applications/models/application-aggregate.model';
import { ApplicationListItem } from '../../pages/applications/models/application-list-item.model';
import { ApplicationMatch } from '../../pages/applications/models/application-match.model';
import { CvOptimization } from '../../pages/applications/models/cv-optimization.model';
import { ApplicationInterviewPrep } from '../../pages/applications/models/application-interview-prep.model';
import { CoverLetter } from '../../pages/applications/models/cover-letter.model';

@Injectable({ providedIn: 'root' })
export class ApplicationsService {
  private http = inject(HttpClient);
  private base = `${environment.apiUrl}/applications`;

  list(): Observable<ApplicationListItem[]> {
    return this.http.get<ApplicationListItem[]>(this.base);
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

  cvPdfUrl(id: string): string {
    return `${this.base}/${id}/cv.pdf`;
  }

  coverLetterPdfUrl(id: string): string {
    return `${this.base}/${id}/cover-letter.pdf`;
  }

  bundleUrl(id: string): string {
    return `${this.base}/${id}/bundle.zip`;
  }

  markApplied(id: string): Observable<ApplicationAggregate> {
    return this.http.post<ApplicationAggregate>(`${this.base}/${id}/mark-applied`, {});
  }
}
