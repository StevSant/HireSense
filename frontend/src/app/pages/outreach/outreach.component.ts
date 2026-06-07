import { Component, DestroyRef, OnInit, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import { OutreachService } from '../../core/services/outreach.service';
import { ApplicationsService } from '../../core/services/applications.service';
import { ApplicationListItem } from '../applications/models/application-list-item.model';
import { OutreachEvent } from './models/outreach-event.model';
import { OutreachEventKind } from './models/outreach-event-kind.model';
import { OutreachNudge } from './models/outreach-nudge.model';

@Component({
  selector: 'app-outreach',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './outreach.component.html',
  styleUrl: './outreach.component.scss',
})
export class OutreachComponent implements OnInit {
  private outreach = inject(OutreachService);
  private applicationsService = inject(ApplicationsService);
  private route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);

  // Target picker
  applications = signal<ApplicationListItem[]>([]);
  selectedApplicationId = signal('');

  // Compose
  contactName = signal('');
  channel = signal('');
  message = signal('');
  generating = signal(false);
  // Inline notice for graceful degradation (503 no LLM, 404 missing app, etc.)
  composeNotice = signal('');
  copied = signal(false);

  // Record
  recording = signal(false);
  recordError = signal('');

  // Timeline
  events = signal<OutreachEvent[]>([]);
  timelineError = signal('');
  timelineLoading = signal(false);

  // Nudges
  nudges = signal<OutreachNudge[]>([]);
  nudgesError = signal('');
  nudgesLoading = signal(false);

  hasSelection = computed(() => this.selectedApplicationId().trim().length > 0);

  ngOnInit(): void {
    this.loadApplications();
    this.loadNudges();
  }

  private loadApplications(): void {
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
      });
  }

  selectApplication(id: string): void {
    this.selectedApplicationId.set(id);
    this.composeNotice.set('');
    this.recordError.set('');
    if (id) {
      this.loadTimeline();
    } else {
      this.events.set([]);
    }
  }

  onSelectChange(id: string): void {
    this.selectApplication(id);
  }

  generate(): void {
    const applicationId = this.selectedApplicationId();
    if (!applicationId) {
      this.composeNotice.set('Pick an application first.');
      return;
    }
    this.generating.set(true);
    this.composeNotice.set('');
    const contact = this.contactName().trim();
    const channel = this.channel().trim();
    this.outreach
      .generate({
        application_id: applicationId,
        ...(contact ? { contact_name: contact } : {}),
        ...(channel ? { channel } : {}),
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.message.set(res.message);
          this.generating.set(false);
        },
        error: (err) => {
          this.generating.set(false);
          if (err?.status === 503) {
            this.composeNotice.set('Message generation is unavailable — check the LLM settings.');
          } else if (err?.status === 404) {
            this.composeNotice.set('That application could not be found.');
          } else {
            this.composeNotice.set(err?.error?.detail ?? 'Could not generate a message.');
          }
        },
      });
  }

  copyMessage(): void {
    const text = this.message();
    if (!text) return;
    navigator.clipboard?.writeText(text);
    this.copied.set(true);
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
          this.events.set([...events].reverse());
          this.timelineLoading.set(false);
        },
        error: (err) => {
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
