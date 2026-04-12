import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { InterviewPrep } from '../../pages/interview/models/interview-prep.model';
import { Story } from '../../pages/interview/models/story.model';

export interface PrepareRequest {
  job_title: string;
  company: string;
  description: string;
}

@Injectable({ providedIn: 'root' })
export class InterviewService {
  constructor(private http: HttpClient) {}

  listStories(): Observable<Story[]> {
    return this.http.get<Story[]>(`${environment.apiUrl}/interview/stories`);
  }

  createStory(body: Record<string, string>): Observable<Story> {
    return this.http.post<Story>(`${environment.apiUrl}/interview/stories`, body);
  }

  deleteStory(id: string): Observable<void> {
    return this.http.delete<void>(`${environment.apiUrl}/interview/stories/${id}`);
  }

  prepare(request: PrepareRequest): Observable<InterviewPrep> {
    return this.http.post<InterviewPrep>(`${environment.apiUrl}/interview/prepare`, request);
  }
}
