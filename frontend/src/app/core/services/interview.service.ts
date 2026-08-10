import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiClient, API_ROUTES } from '@core/api';
import { InterviewPrep } from '@core/contracts/interview-prep.model';
import { PrepareRequest } from '@core/contracts/prepare-request.model';
import { Story } from '@core/contracts/story.model';

@Injectable({ providedIn: 'root' })
export class InterviewService {
  constructor(private api: ApiClient) {}

  listStories(): Observable<Story[]> {
    return this.api.get<Story[]>(API_ROUTES.interview.stories());
  }

  createStory(body: Record<string, string>): Observable<Story> {
    return this.api.post<Story>(API_ROUTES.interview.stories(), body);
  }

  deleteStory(id: string): Observable<void> {
    return this.api.delete<void>(API_ROUTES.interview.story({ id }));
  }

  prepare(request: PrepareRequest): Observable<InterviewPrep> {
    return this.api.post<InterviewPrep>(API_ROUTES.interview.prepare(), request);
  }
}
