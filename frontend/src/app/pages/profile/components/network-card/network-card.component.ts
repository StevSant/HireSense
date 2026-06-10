import { ChangeDetectionStrategy, Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { DatePipe } from '@angular/common';
import { NetworkService } from '../../../../core/services/network.service';
import { NetworkImportResult } from '../../models/network-import-result.model';

@Component({
  selector: 'app-network-card',
  imports: [DatePipe],
  templateUrl: './network-card.component.html',
  styleUrl: './network-card.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class NetworkCardComponent {
  private service = inject(NetworkService);
  private destroyRef = inject(DestroyRef);

  readonly importing = signal(false);
  readonly result = signal<NetworkImportResult | null>(null);
  readonly error = signal('');

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    this.importFile(file);
  }

  private importFile(file: File): void {
    if (this.importing()) return;
    this.importing.set(true);
    this.error.set('');
    this.service
      .import(file)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.result.set(res);
          this.importing.set(false);
        },
        error: (err) => {
          this.error.set(err?.error?.detail ?? 'Import failed. Please try again.');
          this.importing.set(false);
        },
      });
  }
}
