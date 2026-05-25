import { Injectable, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';
import { environment } from '../../../environments/environment';
import { CoverLetterTemplate } from '../../pages/profile/models/cover-letter-template.model';

@Injectable({ providedIn: 'root' })
export class CoverLetterTemplatesService {
  private http = inject(HttpClient);
  private base = `${environment.apiUrl}/profile/cover-letter-templates`;

  readonly templates = signal<CoverLetterTemplate[] | null>(null);

  list(): Observable<CoverLetterTemplate[]> {
    return this.http.get<CoverLetterTemplate[]>(this.base).pipe(
      tap((items) => this.templates.set(items)),
    );
  }

  create(payload: {
    name: string;
    body: string;
    tone?: string;
    language?: string;
  }): Observable<CoverLetterTemplate> {
    return this.http.post<CoverLetterTemplate>(this.base, payload).pipe(
      tap((created) => {
        const current = this.templates() ?? [];
        this.templates.set([created, ...current]);
      }),
    );
  }

  update(
    id: string,
    patch: Partial<{ name: string; body: string; tone: string; language: string }>,
  ): Observable<CoverLetterTemplate> {
    return this.http.patch<CoverLetterTemplate>(`${this.base}/${id}`, patch).pipe(
      tap((updated) => {
        const current = this.templates() ?? [];
        this.templates.set(current.map((t) => (t.id === updated.id ? updated : t)));
      }),
    );
  }

  delete(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/${id}`).pipe(
      tap(() => {
        const current = this.templates() ?? [];
        this.templates.set(current.filter((t) => t.id !== id));
      }),
    );
  }
}
