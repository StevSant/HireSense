import { Component, OnInit, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { TitleCasePipe } from '@angular/common';
import { environment } from '../../../environments/environment';
import { Competency } from '../../core/models/competency.model';
import { Story } from '../../core/models/story.model';
import { InterviewPrep } from '../../core/models/interview-prep.model';

@Component({
  selector: 'app-interview',
  standalone: true,
  imports: [FormsModule, TitleCasePipe],
  templateUrl: './interview.component.html',
  styleUrl: './interview.component.scss',
})
export class InterviewComponent implements OnInit {
  // Story bank state
  stories = signal<Story[]>([]);
  storiesLoading = signal(false);
  storiesError = signal('');
  showAddStoryForm = signal(false);
  addingStory = signal(false);

  // New story form fields
  newTitle = signal('');
  newCompetency = signal<Competency>('leadership');
  newSituation = signal('');
  newTask = signal('');
  newAction = signal('');
  newResult = signal('');
  newReflection = signal('');
  newTags = signal('');

  // Prepare section state
  prepJobTitle = signal('');
  prepCompany = signal('');
  prepDescription = signal('');
  preparing = signal(false);
  prepError = signal('');
  prepResult = signal<InterviewPrep | null>(null);

  readonly competencyOptions: Competency[] = [
    'leadership',
    'problem_solving',
    'collaboration',
    'communication',
    'adaptability',
    'technical',
    'initiative',
    'conflict_resolution',
  ];

  constructor(private http: HttpClient) {}

  ngOnInit(): void {
    this.loadStories();
  }

  loadStories(): void {
    this.storiesLoading.set(true);
    this.storiesError.set('');
    this.http.get<Story[]>(`${environment.apiUrl}/interview/stories`).subscribe({
      next: (stories) => {
        this.stories.set(stories);
        this.storiesLoading.set(false);
      },
      error: (err) => {
        this.storiesError.set(err.error?.detail || 'Failed to load stories');
        this.storiesLoading.set(false);
      },
    });
  }

  toggleAddStoryForm(): void {
    this.showAddStoryForm.update((v) => !v);
    if (!this.showAddStoryForm()) {
      this.resetStoryForm();
    }
  }

  addStory(): void {
    const title = this.newTitle().trim();
    const situation = this.newSituation().trim();
    const task = this.newTask().trim();
    const action = this.newAction().trim();
    const result = this.newResult().trim();
    if (!title || !situation || !task || !action || !result) {
      return;
    }
    this.addingStory.set(true);
    const body: Record<string, string> = {
      title,
      competency: this.newCompetency(),
      situation,
      task,
      action,
      result,
    };
    const reflection = this.newReflection().trim();
    if (reflection) body['reflection'] = reflection;
    const tags = this.newTags().trim();
    if (tags) body['tags'] = tags;

    this.http.post<Story>(`${environment.apiUrl}/interview/stories`, body).subscribe({
      next: (story) => {
        this.stories.update((list) => [story, ...list]);
        this.addingStory.set(false);
        this.showAddStoryForm.set(false);
        this.resetStoryForm();
      },
      error: (err) => {
        this.storiesError.set(err.error?.detail || 'Failed to add story');
        this.addingStory.set(false);
      },
    });
  }

  deleteStory(id: string): void {
    this.http.delete(`${environment.apiUrl}/interview/stories/${id}`).subscribe({
      next: () => {
        this.stories.update((list) => list.filter((s) => s.id !== id));
      },
      error: (err) => {
        this.storiesError.set(err.error?.detail || 'Failed to delete story');
      },
    });
  }

  generatePrep(): void {
    const job_title = this.prepJobTitle().trim();
    const company = this.prepCompany().trim();
    const description = this.prepDescription().trim();
    if (!job_title || !company || !description) {
      return;
    }
    this.preparing.set(true);
    this.prepError.set('');
    this.prepResult.set(null);

    this.http
      .post<InterviewPrep>(`${environment.apiUrl}/interview/prepare`, {
        job_title,
        company,
        description,
      })
      .subscribe({
        next: (prep) => {
          this.prepResult.set(prep);
          this.preparing.set(false);
        },
        error: (err) => {
          this.prepError.set(err.error?.detail || 'Failed to generate prep');
          this.preparing.set(false);
        },
      });
  }

  onNewTitleInput(event: Event): void {
    this.newTitle.set((event.target as HTMLInputElement).value);
  }

  onNewCompetencyChange(event: Event): void {
    this.newCompetency.set((event.target as HTMLSelectElement).value as Competency);
  }

  onNewSituationInput(event: Event): void {
    this.newSituation.set((event.target as HTMLTextAreaElement).value);
  }

  onNewTaskInput(event: Event): void {
    this.newTask.set((event.target as HTMLTextAreaElement).value);
  }

  onNewActionInput(event: Event): void {
    this.newAction.set((event.target as HTMLTextAreaElement).value);
  }

  onNewResultInput(event: Event): void {
    this.newResult.set((event.target as HTMLTextAreaElement).value);
  }

  onNewReflectionInput(event: Event): void {
    this.newReflection.set((event.target as HTMLTextAreaElement).value);
  }

  onNewTagsInput(event: Event): void {
    this.newTags.set((event.target as HTMLInputElement).value);
  }

  onPrepJobTitleInput(event: Event): void {
    this.prepJobTitle.set((event.target as HTMLInputElement).value);
  }

  onPrepCompanyInput(event: Event): void {
    this.prepCompany.set((event.target as HTMLInputElement).value);
  }

  onPrepDescriptionInput(event: Event): void {
    this.prepDescription.set((event.target as HTMLTextAreaElement).value);
  }

  private resetStoryForm(): void {
    this.newTitle.set('');
    this.newCompetency.set('leadership');
    this.newSituation.set('');
    this.newTask.set('');
    this.newAction.set('');
    this.newResult.set('');
    this.newReflection.set('');
    this.newTags.set('');
  }
}
