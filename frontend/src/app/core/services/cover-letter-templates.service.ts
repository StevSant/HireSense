import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiClient, API_ROUTES } from '@core/api';
import { CoverLetterTemplate } from '@core/contracts/cover-letter-template.model';
import { CoverLetterTemplateUpsert } from '@core/contracts/cover-letter-template-upsert.model';

@Injectable({ providedIn: 'root' })
export class CoverLetterTemplatesService {
  private api = inject(ApiClient);

  list(): Observable<CoverLetterTemplate[]> {
    return this.api.get<CoverLetterTemplate[]>(API_ROUTES.coverLetterTemplates.root());
  }

  create(payload: CoverLetterTemplateUpsert): Observable<CoverLetterTemplate> {
    return this.api.post<CoverLetterTemplate>(API_ROUTES.coverLetterTemplates.root(), payload);
  }

  update(id: string, payload: CoverLetterTemplateUpsert): Observable<CoverLetterTemplate> {
    return this.api.patch<CoverLetterTemplate>(
      API_ROUTES.coverLetterTemplates.byId({ id }),
      payload,
    );
  }

  remove(id: string): Observable<void> {
    return this.api.delete<void>(API_ROUTES.coverLetterTemplates.byId({ id }));
  }
}
