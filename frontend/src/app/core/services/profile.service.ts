import { Injectable, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';
import { environment } from '../../../environments/environment';
import { ApplyProfile } from '@core/contracts/apply-profile.model';
import { CandidateProfile } from '@core/contracts/candidate-profile.model';
import { ProfileManualFieldsUpdate } from '@core/contracts/profile-manual-fields-update.model';
import { UploadCVRequest } from '@core/contracts/upload-cv-request.model';
import { TranslateResponse } from '@core/contracts/translate-response.model';

@Injectable({ providedIn: 'root' })
export class ProfileService {
  /** All uploaded profiles keyed by language. */
  readonly profiles = signal<Record<string, CandidateProfile>>({});

  /** Active profile — the one currently displayed/used for matching. */
  readonly activeLanguage = signal<string>('en');

  /**
   * False until the first profile fetch settles.
   *
   * The profile tabs are separate routed components, so they cannot read a
   * loading flag off a shared parent. The shell bootstraps once and flips this;
   * each tab derives its spinner from it and no tab refetches on navigation.
   */
  readonly loaded = signal(false);

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
    return this.http
      .post<CandidateProfile>(`${environment.apiUrl}/profile/upload-file`, formData)
      .pipe(
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

  updateManualFields(
    profileId: string,
    update: ProfileManualFieldsUpdate,
  ): Observable<CandidateProfile> {
    return this.http
      .patch<CandidateProfile>(`${environment.apiUrl}/profile/${profileId}`, update)
      .pipe(
        tap((profile) => {
          this.profiles.update((all) => ({ ...all, [profile.language]: profile }));
        }),
      );
  }

  setApplyProfile(applyProfile: ApplyProfile): Observable<CandidateProfile> {
    return this.http
      .put<CandidateProfile>(`${environment.apiUrl}/profile/apply-profile`, applyProfile)
      .pipe(
        tap((profile) => {
          // The apply profile is one-per-person: the backend writes it onto every
          // language row and echoes back whichever row is newest. Keying the cache
          // by the response's language would leave the other languages stale, so
          // fan the saved answers out across all cached profiles.
          this.profiles.update((all) => {
            const next: Record<string, CandidateProfile> = {};
            for (const [language, cached] of Object.entries(all)) {
              next[language] = { ...cached, apply_profile: profile.apply_profile };
            }
            next[profile.language] = profile;
            return next;
          });
        }),
      );
  }

  translate(targetLanguage: string): Observable<TranslateResponse> {
    return this.http
      .post<TranslateResponse>(`${environment.apiUrl}/profile/translate`, {
        target_language: targetLanguage,
      })
      .pipe(
        tap((res) => {
          this.profiles.update((all) => ({ ...all, [res.profile.language]: res.profile }));
          this.activeLanguage.set(res.profile.language);
        }),
      );
  }

  downloadCvPdf(language: string): Observable<Blob> {
    return this.http.get(`${environment.apiUrl}/profile/cv.pdf`, {
      params: { language },
      responseType: 'blob',
    });
  }
}
