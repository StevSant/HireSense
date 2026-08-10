import { ChangeDetectionStrategy, Component, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ComboboxComponent } from '@core/components/combobox';
import { NetworkContact } from '@core/contracts/network-contact.model';
import { OutreachEventKind } from '@core/contracts/outreach-event-kind.model';
import { OutreachNudge } from '@core/contracts/outreach-nudge.model';
import { parseSortToken } from '@core/utils/parse-sort-token';
import { OutreachStore } from './outreach.store';

/**
 * Outreach page — draft a message, record what was sent, chase follow-ups.
 *
 * A view over OutreachStore: every signal below is the store's own signal
 * re-exposed under the name the template already used, and every handler is
 * either a DOM-event adapter (parsing the `Event` a native <select> emits) or
 * a straight delegation. Keeping the store's API in plain values rather than
 * DOM events is what lets it be exercised without a fixture.
 */
@Component({
  selector: 'app-outreach',
  standalone: true,
  imports: [FormsModule, ComboboxComponent],
  providers: [OutreachStore],
  templateUrl: './outreach.component.html',
  styleUrl: './outreach.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class OutreachComponent implements OnInit {
  private store = inject(OutreachStore);

  applications = this.store.applications;
  applicationOptions = this.store.applicationOptions;
  applicationsError = this.store.applicationsError;
  selectedApplicationId = this.store.selectedApplicationId;
  hasSelection = this.store.hasSelection;

  contactName = this.store.contactName;
  channel = this.store.channel;
  message = this.store.message;
  generating = this.store.generating;
  composeNotice = this.store.composeNotice;
  copied = this.store.copied;

  recording = this.store.recording;
  recordError = this.store.recordError;

  events = this.store.events;
  timelineError = this.store.timelineError;
  timelineLoading = this.store.timelineLoading;
  eventSort = this.store.eventSort;
  kindFilter = this.store.kindFilter;
  visibleEvents = this.store.visibleEvents;

  suggestions = this.store.suggestions;

  nudges = this.store.nudges;
  nudgesError = this.store.nudgesError;
  nudgesLoading = this.store.nudgesLoading;

  ngOnInit(): void {
    this.store.init();
  }

  loadApplications(): void {
    this.store.loadApplications();
  }

  selectApplication(id: string): void {
    this.store.selectApplication(id);
  }

  onSelectChange(id: string): void {
    this.store.selectApplication(id);
  }

  useContact(contact: NetworkContact): void {
    this.store.useContact(contact);
  }

  generate(): void {
    this.store.generate();
  }

  copyMessage(): void {
    this.store.copyMessage();
  }

  record(kind: OutreachEventKind): void {
    this.store.record(kind);
  }

  onEventSort(event: Event): void {
    const parsed = parseSortToken<'created'>((event.target as HTMLSelectElement).value);
    if (parsed) this.store.setEventSort(parsed.field, parsed.dir);
  }

  onKindFilterChange(event: Event): void {
    this.store.setKindFilter((event.target as HTMLSelectElement).value as OutreachEventKind | '');
  }

  selectNudge(nudge: OutreachNudge): void {
    this.store.selectNudge(nudge);
  }

  markFollowedUp(nudge: OutreachNudge): void {
    this.store.markFollowedUp(nudge);
  }
}
