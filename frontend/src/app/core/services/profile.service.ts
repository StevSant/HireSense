import { Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';
import { environment } from '../../../environments/environment';
import { CandidateProfile } from '../../pages/profile/models/candidate-profile.model';

export interface UploadCVRequest {
  tex_content: string;
  language: string;
}

@Injectable({ providedIn: 'root' })
export class ProfileService {
  /** Persisted profile — survives page navigation. */
  readonly profile = signal<CandidateProfile | null>(null);

  constructor(private http: HttpClient) {}

  uploadCV(request: UploadCVRequest): Observable<CandidateProfile> {
    return this.http.post<CandidateProfile>(`${environment.apiUrl}/profile/upload`, request).pipe(
      tap((profile) => this.profile.set(profile)),
    );
  }

  uploadFile(file: File, language: string): Observable<CandidateProfile> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('language', language);
    return this.http.post<CandidateProfile>(`${environment.apiUrl}/profile/upload-file`, formData).pipe(
      tap((profile) => this.profile.set(profile)),
    );
  }

  getCurrentProfile(): Observable<CandidateProfile> {
    return this.http.get<CandidateProfile>(`${environment.apiUrl}/profile/current`).pipe(
      tap((profile) => this.profile.set(profile)),
    );
  }
}
