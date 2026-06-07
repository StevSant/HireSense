import { Component, DestroyRef, inject, output, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { ApplicationsService } from '../../../core/services/applications.service';

@Component({
  selector: 'app-application-create-dialog',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './application-create-dialog.component.html',
  styleUrl: './application-create-dialog.component.scss',
})
export class ApplicationCreateDialogComponent {
  private service = inject(ApplicationsService);
  private readonly destroyRef = inject(DestroyRef);

  closed = output<void>();
  created = output<string>();

  title = signal('');
  company = signal('');
  description = signal('');
  url = signal('');
  saving = signal(false);
  error = signal('');

  submit(): void {
    const t = this.title().trim();
    const c = this.company().trim();
    const d = this.description().trim();
    if (!t || !c || !d) {
      this.error.set('Title, company, and description are required');
      return;
    }
    this.saving.set(true);
    this.error.set('');
    this.service
      .createManual({
        title: t,
        company: c,
        description: d,
        url: this.url().trim() || undefined,
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (agg) => {
          this.saving.set(false);
          this.created.emit(agg.id);
        },
        error: (err) => {
          this.error.set(err?.error?.detail ?? 'Create failed');
          this.saving.set(false);
        },
      });
  }

  onOverlay(ev: MouseEvent): void {
    if ((ev.target as HTMLElement).classList.contains('overlay')) {
      this.closed.emit();
    }
  }

  /** Dismiss the dialog with the Escape key for keyboard accessibility. */
  onEscape(): void {
    this.closed.emit();
  }
}
