import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ApplicationsService } from '../../../../core/services/applications.service';
import { CoverLetterLibraryItem } from '../../../applications/models/cover-letter-library-item.model';

@Component({
  selector: 'app-cover-letter-library',
  standalone: true,
  imports: [FormsModule, RouterLink, DatePipe],
  templateUrl: './cover-letter-library.component.html',
  styleUrl: './cover-letter-library.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CoverLetterLibraryComponent implements OnInit {
  private service = inject(ApplicationsService);

  letters = signal<CoverLetterLibraryItem[]>([]);
  loading = signal(true);
  error = signal('');
  query = signal('');
  expandedId = signal<string | null>(null);
  copiedId = signal<string | null>(null);

  filtered = computed(() => {
    const q = this.query().trim().toLowerCase();
    const all = this.letters();
    if (!q) return all;
    return all.filter(
      (l) =>
        l.company.toLowerCase().includes(q) ||
        l.title.toLowerCase().includes(q) ||
        l.body.toLowerCase().includes(q),
    );
  });

  ngOnInit(): void {
    this.service.listAllCoverLetters().subscribe({
      next: (list) => {
        this.letters.set(list);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(err?.error?.detail ?? 'Could not load cover letters');
        this.loading.set(false);
      },
    });
  }

  toggle(id: string): void {
    this.expandedId.update((current) => (current === id ? null : id));
  }

  preview(body: string): string {
    const flat = body.replace(/\s+/g, ' ').trim();
    return flat.length > 220 ? `${flat.slice(0, 220)}…` : flat;
  }

  async copy(item: CoverLetterLibraryItem, event: Event): Promise<void> {
    event.stopPropagation();
    try {
      await navigator.clipboard.writeText(item.body);
      this.copiedId.set(item.id);
      setTimeout(() => {
        if (this.copiedId() === item.id) this.copiedId.set(null);
      }, 1800);
    } catch {
      this.error.set('Clipboard access denied — copy manually.');
    }
  }
}
