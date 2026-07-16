import { Component, DestroyRef, OnInit, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { TitleCasePipe, DatePipe } from '@angular/common';
import { InterviewService } from '../../core/services/interview.service';
import { IngestionService } from '../../core/services/ingestion.service';
import { mapLlmError } from '../../core/services/llm-error.util';
import { Competency } from './models/competency.model';
import { InterviewPrep } from './models/interview-prep.model';
import { Story } from './models/story.model';
import { ApplicationsPrepListComponent } from './components/applications-prep-list.component';
import { SortableHeaderDirective } from '../../core/components/sortable-header';
import { CompanyLinkComponent } from '../../core/components/company-link';
import { createSortState } from '../../core/utils/sort-state';
import { sortItems } from '../../core/utils/sort-items';

type StorySortField = 'title' | 'competency' | 'created';

@Component({
  selector: 'app-interview',
  standalone: true,
  imports: [
    FormsModule,
    TitleCasePipe,
    DatePipe,
    ApplicationsPrepListComponent,
    SortableHeaderDirective,
    CompanyLinkComponent,
  ],
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

  // Client-side sort + competency filter over the loaded story bank.
  storySort = createSortState<StorySortField>('created', 'desc', ['title', 'competency']);
  competencyFilter = signal<Competency | ''>('');

  visibleStories = computed(() => {
    let rows = this.stories();
    const competency = this.competencyFilter();
    if (competency) rows = rows.filter((s) => s.competency === competency);
    const field = this.storySort.field();
    return sortItems(rows, (s) => this.storySortValue(s, field), this.storySort.dir());
  });

  private storySortValue(s: Story, field: StorySortField): string {
    switch (field) {
      case 'title':
        return s.title;
      case 'competency':
        return s.competency;
      case 'created':
        return s.created_at;
    }
  }

  onCompetencyFilterChange(event: Event): void {
    this.competencyFilter.set((event.target as HTMLSelectElement).value as Competency | '');
  }

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

  private ingestionService = inject(IngestionService);
  private route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);

  constructor(private interviewService: InterviewService) {}

  ngOnInit(): void {
    this.loadStories();
    this.applyJobIdFromQuery();
  }

  private applyJobIdFromQuery(): void {
    const jobId = this.route.snapshot.queryParamMap.get('job_id');
    if (!jobId) return;
    this.ingestionService
      .getJob(jobId)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (job) => {
          this.prepJobTitle.set(job.title);
          this.prepCompany.set(job.company);
          this.prepDescription.set(job.description);
        },
        error: () => {},
      });
  }

  loadStories(): void {
    this.storiesLoading.set(true);
    this.storiesError.set('');
    this.interviewService
      .listStories()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
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

    this.interviewService
      .createStory(body)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
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
    this.interviewService
      .deleteStory(id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
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

    this.interviewService
      .prepare({ job_title, company, description })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (prep) => {
          this.prepResult.set(prep);
          this.preparing.set(false);
        },
        error: (err) => {
          this.prepError.set(mapLlmError(err, 'Failed to generate prep'));
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
