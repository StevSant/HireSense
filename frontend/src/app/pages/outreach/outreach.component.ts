import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { HttpErrorResponse } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import { OutreachService } from '../../core/services/outreach.service';
import { NetworkService } from '../../core/services/network.service';
import { ApplicationsService } from '../../core/services/applications.service';
import { LlmRunnerService } from '../../core/services/llm-runner.service';
import { ApplicationListItem } from '../applications/models/application-list-item.model';
import { NetworkContact } from '../profile/models/network-contact.model';
import { OutreachEvent } from './models/outreach-event.model';
import { OutreachEventKind } from './models/outreach-event-kind.model';
import { OutreachNudge } from './models/outreach-nudge.model';
import { GenerateResponse } from './models/generate-response.model';
import { createSortState } from '../../core/utils/sort-state';
import { sortItems } from '../../core/utils/sort-items';
import { parseSortToken } from '../../core/utils/parse-sort-token';

@Component({
  selector: 'app-outreach',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './outreach.component.html',
  styleUrl: './outreach.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class OutreachComponent implements OnInit {
  private outreach = inject(OutreachService);
  private network = inject(NetworkService);
  private applicationsService = inject(ApplicationsService);
  private llmRunner = inject(LlmRunnerService);
  private route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);

  // Target picker
  applications = signal<ApplicationListItem[]>([]);
  applicationsError = signal('');
  selectedApplicationId = signal('');

  // Compose
  contactName = signal('');
  channel = signal('');
  // Editable — seeded from a generated draft, but the user can hand-edit it
  // afterwards, so it stays a plain signal rather than a computed mirror of
  // the cached run result.
  message = signal('');
  // Keyed by target application id. The run lives in LlmRunnerService so it
  // survives navigating away from this page mid-generation; reselecting the
  // same application later re-hydrates `message` from the cached result.
  private generateKey = computed(() => `outreach:generate:${this.selectedApplicationId()}`);
  generating = computed(() => this.llmRunner.isRunning(this.generateKey()));
  // Generate keys whose cached result has already been used to seed
  // `message` on this component instance — either by a hydration read in
  // selectApplication() or by generate() itself completing. Seeding is
  // one-shot per key so reselecting an application the user has already
  // hand-edited never overwrites the edit with the (unchanged) cached draft.
  private seededMessageKeys = new Set<string>();
  // Manual guard messages (e.g. "pick an application") merged with the
  // generate run's mapped error, if any, for the current target.
  private manualNotice = signal('');
  composeNotice = computed(() => this.manualNotice() || this.llmRunner.error(this.generateKey()));
  copied = signal(false);
  private copiedResetTimer: ReturnType<typeof setTimeout> | undefined;

  // Record
  recording = signal(false);
  recordError = signal('');

  // Timeline
  events = signal<OutreachEvent[]>([]);
  timelineError = signal('');
  timelineLoading = signal(false);
  // Client-side sort (newest/oldest) + kind filter over the loaded timeline.
  eventSort = createSortState<'created'>('created', 'desc', []);
  kindFilter = signal<OutreachEventKind | ''>('');

  visibleEvents = computed(() => {
    let rows = this.events();
    const kind = this.kindFilter();
    if (kind) rows = rows.filter((e) => e.kind === kind);
    return sortItems(rows, (e) => e.created_at, this.eventSort.dir());
  });

  // LinkedIn contact suggestions for the selected application's company.
  suggestions = signal<NetworkContact[]>([]);

  // Nudges
  nudges = signal<OutreachNudge[]>([]);
  nudgesError = signal('');
  nudgesLoading = signal(false);

  hasSelection = computed(() => this.selectedApplicationId().trim().length > 0);

  ngOnInit(): void {
    this.loadApplications();
    this.loadNudges();
  }

  loadApplications(): void {
    this.applicationsError.set('');
    this.applicationsService
      .list()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (apps) => {
          this.applications.set(apps);
          const fromQuery = this.route.snapshot.queryParamMap.get('application_id');
          if (fromQuery && apps.some((a) => a.id === fromQuery)) {
            this.selectApplication(fromQuery);
          }
        },
        error: (err: HttpErrorResponse) => {
          this.applicationsError.set(err?.error?.detail ?? 'Could not load your applications.');
        },
      });
  }

  selectApplication(id: string): void {
    this.selectedApplicationId.set(id);
    this.manualNotice.set('');
    this.recordError.set('');
    this.suggestions.set([]);
    // Pick up a draft generated (and possibly completed) while this page was
    // unmounted — e.g. the user clicked Generate, navigated away, and came
    // back. Only seeds once per key: reselecting an application whose draft
    // was already surfaced here must never clobber a hand-edit made since,
    // and leaves `message` untouched when there's nothing cached yet.
    const key = this.generateKey();
    if (id && !this.seededMessageKeys.has(key)) {
      const cached = this.llmRunner.result<GenerateResponse>(key);
      if (cached) {
        this.message.set(cached.message);
        this.seededMessageKeys.add(key);
      }
    }
    if (id) {
      this.loadTimeline();
      this.loadSuggestions(id);
    } else {
      this.events.set([]);
    }
  }

  private loadSuggestions(applicationId: string): void {
    const app = this.applications().find((a) => a.id === applicationId);
    const company = app?.company?.trim();
    if (!company) return;
    this.network
      .match(company)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          // Ignore late responses for a previously selected application so a
          // slow request can't overwrite the current selection's suggestions.
          if (this.selectedApplicationId() !== applicationId) return;
          this.suggestions.set(res.contacts.slice(0, 5));
        },
        error: () => {
          // Suggestions are best-effort; silently swallow errors.
        },
      });
  }

  useContact(contact: NetworkContact): void {
    this.contactName.set(`${contact.first_name} ${contact.last_name}`);
  }

  onSelectChange(id: string): void {
    this.selectApplication(id);
  }

  generate(): void {
    const applicationId = this.selectedApplicationId();
    if (!applicationId) {
      this.manualNotice.set('Pick an application first.');
      return;
    }
    this.manualNotice.set('');
    const contact = this.contactName().trim();
    const channel = this.channel().trim();
    // Captured once: an explicit Generate click always overwrites `message`
    // (and (re)marks the key seeded) with whatever this run produces, even
    // if the selection somehow changes before the response lands.
    const key = this.generateKey();
    this.llmRunner.run(
      key,
      this.outreach.generate({
        application_id: applicationId,
        ...(contact ? { contact_name: contact } : {}),
        ...(channel ? { channel } : {}),
      }),
      (err) => this.mapGenerateError(err),
      (res) => {
        this.message.set(res.message);
        this.seededMessageKeys.add(key);
      },
    );
  }

  private mapGenerateError(err: HttpErrorResponse): string {
    if (err?.status === 503) {
      return 'Message generation is unavailable — check the LLM settings.';
    }
    if (err?.status === 404) {
      return 'That application could not be found.';
    }
    return err?.error?.detail ?? 'Could not generate a message.';
  }

  copyMessage(): void {
    const text = this.message();
    if (!text) return;
    navigator.clipboard?.writeText(text);
    this.copied.set(true);
    clearTimeout(this.copiedResetTimer);
    this.copiedResetTimer = setTimeout(() => this.copied.set(false), 2000);
  }

  record(kind: OutreachEventKind): void {
    const applicationId = this.selectedApplicationId();
    if (!applicationId) {
      this.recordError.set('Pick an application first.');
      return;
    }
    this.recording.set(true);
    this.recordError.set('');
    const contact = this.contactName().trim();
    const channel = this.channel().trim();
    const message = this.message().trim();
    this.outreach
      .record({
        application_id: applicationId,
        kind,
        ...(message ? { message } : {}),
        ...(contact ? { contact_name: contact } : {}),
        ...(channel ? { channel } : {}),
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.recording.set(false);
          this.loadTimeline();
        },
        error: (err) => {
          this.recording.set(false);
          this.recordError.set(err?.error?.detail ?? 'Could not record outreach.');
        },
      });
  }

  private loadTimeline(): void {
    const applicationId = this.selectedApplicationId();
    if (!applicationId) return;
    this.timelineLoading.set(true);
    this.timelineError.set('');
    this.outreach
      .listEvents(applicationId)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (events) => {
          // Ignore late responses after the user switched applications.
          if (this.selectedApplicationId() !== applicationId) return;
          // Store in natural (server) order; visibleEvents applies sort/filter.
          this.events.set(events);
          this.timelineLoading.set(false);
        },
        error: (err) => {
          if (this.selectedApplicationId() !== applicationId) return;
          this.timelineLoading.set(false);
          this.timelineError.set(err?.error?.detail ?? 'Could not load the timeline.');
        },
      });
  }

  private loadNudges(): void {
    this.nudgesLoading.set(true);
    this.nudgesError.set('');
    this.outreach
      .dueFollowups()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (nudges) => {
          this.nudges.set(nudges);
          this.nudgesLoading.set(false);
        },
        error: (err) => {
          this.nudgesLoading.set(false);
          this.nudgesError.set(err?.error?.detail ?? 'Could not load follow-up nudges.');
        },
      });
  }

  onEventSort(event: Event): void {
    const parsed = parseSortToken<'created'>((event.target as HTMLSelectElement).value);
    if (parsed) this.eventSort.set(parsed.field, parsed.dir);
  }

  onKindFilterChange(event: Event): void {
    this.kindFilter.set((event.target as HTMLSelectElement).value as OutreachEventKind | '');
  }

  selectNudge(nudge: OutreachNudge): void {
    this.selectApplication(nudge.application_id);
  }

  markFollowedUp(nudge: OutreachNudge): void {
    this.outreach
      .record({ application_id: nudge.application_id, kind: 'followed_up' })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.nudges.set(this.nudges().filter((n) => n.application_id !== nudge.application_id));
          if (nudge.application_id === this.selectedApplicationId()) {
            this.loadTimeline();
          }
        },
        error: (err) => {
          this.nudgesError.set(err?.error?.detail ?? 'Could not record the follow-up.');
        },
      });
  }
}
