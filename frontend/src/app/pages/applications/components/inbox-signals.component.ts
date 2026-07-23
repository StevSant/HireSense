import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { DatePipe, DecimalPipe, TitleCasePipe } from '@angular/common';
import { Observable } from 'rxjs';
import { InboxSignalsService } from '../../../core/services/inbox-signals.service';
import { InboxSignal } from '../models/inbox-signal.model';

@Component({
  selector: 'app-inbox-signals',
  standalone: true,
  imports: [DatePipe, DecimalPipe, TitleCasePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './inbox-signals.component.html',
  styleUrl: './inbox-signals.component.scss',
})
export class InboxSignalsComponent implements OnInit {
  private readonly service = inject(InboxSignalsService);

  readonly signals = signal<InboxSignal[]>([]);
  readonly loading = signal(true);
  readonly error = signal('');
  readonly reviewingId = signal<string | null>(null);

  ngOnInit(): void {
    this.load();
  }

  confirm(id: string): void {
    this.review(id, () => this.service.confirm(id));
  }

  dismiss(id: string): void {
    this.review(id, () => this.service.dismiss(id));
  }

  private load(): void {
    this.loading.set(true);
    this.error.set('');
    this.service.listPending().subscribe({
      next: (signals) => {
        this.signals.set(signals);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(err?.error?.detail ?? 'Could not load inbox signals.');
        this.loading.set(false);
      },
    });
  }

  private review(id: string, request: () => Observable<InboxSignal>): void {
    if (this.reviewingId() !== null) return;
    this.reviewingId.set(id);
    this.error.set('');
    request().subscribe({
      next: () => {
        this.signals.update((signals) => signals.filter((signal) => signal.id !== id));
        this.reviewingId.set(null);
      },
      error: (err) => {
        this.error.set(err?.error?.detail ?? 'Could not update this inbox signal.');
        this.reviewingId.set(null);
      },
    });
  }
}
