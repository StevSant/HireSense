import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  OnInit,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { AutopilotService } from '../../../core/services/autopilot.service';
import { AutopilotDraft } from '@core/contracts/autopilot.model';

@Component({
  selector: 'app-autopilot-drafts',
  standalone: true,
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './drafts.component.html',
  styleUrl: './drafts.component.scss',
})
export class DraftsComponent implements OnInit {
  private readonly service = inject(AutopilotService);
  private readonly destroyRef = inject(DestroyRef);
  readonly drafts = signal<AutopilotDraft[]>([]);
  readonly loading = signal(false);
  readonly preparing = signal(false);
  readonly error = signal('');
  readonly notice = signal('');

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set('');
    this.service
      .listDrafts()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (drafts) => {
          this.drafts.set(drafts);
          this.loading.set(false);
        },
        error: (err) => {
          this.loading.set(false);
          this.error.set(err?.error?.detail ?? 'Could not load application drafts.');
        },
      });
  }

  prepare(): void {
    this.preparing.set(true);
    this.error.set('');
    this.notice.set('');
    this.service
      .run()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (response) => {
          this.preparing.set(false);
          this.notice.set(
            response.status === 'started'
              ? 'Preparation started. Drafts will appear here when they are ready.'
              : 'A preparation run is already in progress. Refresh shortly.',
          );
          this.load();
        },
        error: (err) => {
          this.preparing.set(false);
          this.error.set(
            err?.status === 409 || err?.error?.status === 'already_running'
              ? 'A preparation run is already in progress. Refresh shortly.'
              : (err?.error?.detail ?? 'Could not start draft preparation.'),
          );
        },
      });
  }
}
