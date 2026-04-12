import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { CandidateProfile } from '../../pages/profile/models/candidate-profile.model';

export interface UploadCVRequest {
  tex_content: string;
  language: string;
}

@Injectable({ providedIn: 'root' })
export class ProfileService {
  constructor(private http: HttpClient) {}

  uploadCV(request: UploadCVRequest): Observable<CandidateProfile> {
    return this.http.post<CandidateProfile>(`${environment.apiUrl}/profile/upload`, request);
  }
}
