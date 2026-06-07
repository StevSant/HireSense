import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { CoverLetterTemplate } from '../../pages/profile/models/cover-letter-template.model';
import { CoverLetterTemplateUpsert } from '../../pages/profile/models/cover-letter-template-upsert.model';

@Injectable({ providedIn: 'root' })
export class CoverLetterTemplatesService {
  private http = inject(HttpClient);
  private base = `${environment.apiUrl}/cover-letter-templates`;

  list(): Observable<CoverLetterTemplate[]> {
    return this.http.get<CoverLetterTemplate[]>(this.base);
  }

  create(payload: CoverLetterTemplateUpsert): Observable<CoverLetterTemplate> {
    return this.http.post<CoverLetterTemplate>(this.base, payload);
  }

  update(id: string, payload: CoverLetterTemplateUpsert): Observable<CoverLetterTemplate> {
    return this.http.patch<CoverLetterTemplate>(`${this.base}/${id}`, payload);
  }

  remove(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/${id}`);
  }
}
