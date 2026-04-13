import { Injectable, signal, computed } from '@angular/core';
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
  /** All uploaded profiles keyed by language. */
  readonly profiles = signal<Record<string, CandidateProfile>>({});

  /** Active profile — the one currently displayed/used for matching. */
  readonly activeLanguage = signal<string>('en');

  readonly profile = computed(() => {
    const all = this.profiles();
    const lang = this.activeLanguage();
    return all[lang] ?? Object.values(all)[0] ?? null;
  });

  constructor(private http: HttpClient) {}

  uploadCV(request: UploadCVRequest): Observable<CandidateProfile> {
    return this.http.post<CandidateProfile>(`${environment.apiUrl}/profile/upload`, request).pipe(
      tap((profile) => {
        this.profiles.update((all) => ({ ...all, [profile.language]: profile }));
        this.activeLanguage.set(profile.language);
      }),
    );
  }

  uploadFile(file: File, language: string): Observable<CandidateProfile> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('language', language);
    return this.http.post<CandidateProfile>(`${environment.apiUrl}/profile/upload-file`, formData).pipe(
      tap((profile) => {
        this.profiles.update((all) => ({ ...all, [profile.language]: profile }));
        this.activeLanguage.set(profile.language);
      }),
    );
  }

  getCurrentProfile(): Observable<CandidateProfile> {
    return this.http.get<CandidateProfile>(`${environment.apiUrl}/profile/current`).pipe(
      tap((profile) => {
        this.profiles.update((all) => ({ ...all, [profile.language]: profile }));
        this.activeLanguage.set(profile.language);
      }),
    );
  }

  listProfiles(): Observable<CandidateProfile[]> {
    return this.http.get<CandidateProfile[]>(`${environment.apiUrl}/profile/list`).pipe(
      tap((list) => {
        const byLang: Record<string, CandidateProfile> = {};
        for (const p of list) {
          // Keep only the first (newest) per language
          if (!byLang[p.language]) {
            byLang[p.language] = p;
          }
        }
        this.profiles.set(byLang);
      }),
    );
  }
}
