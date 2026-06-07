import { DatePipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  OnInit,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { CoverLetterTemplatesService } from '../../../../core/services/cover-letter-templates.service';
import { CoverLetterTemplate } from '../../models/cover-letter-template.model';
import { CoverLetterTemplateEditingState } from '../../models/cover-letter-template-editing-state.model';
import { CoverLetterTemplateUpsert } from '../../models/cover-letter-template-upsert.model';

const BLANK_FORM = {
  name: '',
  tone: 'professional',
  language: 'en',
  opening: '',
  body: '',
  signature: '',
};

@Component({
  selector: 'app-cover-letter-templates',
  standalone: true,
  imports: [FormsModule, DatePipe],
  templateUrl: './cover-letter-templates.component.html',
  styleUrl: './cover-letter-templates.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CoverLetterTemplatesComponent implements OnInit {
  private service = inject(CoverLetterTemplatesService);
  private readonly destroyRef = inject(DestroyRef);

  templates = signal<CoverLetterTemplate[]>([]);
  loading = signal(true);
  error = signal('');
  editing = signal<CoverLetterTemplateEditingState>({ mode: 'closed' });
  form = signal({ ...BLANK_FORM });
  saving = signal(false);
  deletingId = signal<string | null>(null);

  ngOnInit(): void {
    this.refresh();
  }

  refresh(): void {
    this.loading.set(true);
    this.service.list().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (list) => {
        this.templates.set(list);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(err?.error?.detail ?? 'Could not load templates');
        this.loading.set(false);
      },
    });
  }

  startNew(): void {
    this.form.set({ ...BLANK_FORM });
    this.error.set('');
    this.editing.set({ mode: 'new' });
  }

  startEdit(template: CoverLetterTemplate): void {
    this.form.set({
      name: template.name,
      tone: template.tone,
      language: template.language,
      opening: template.opening,
      body: template.body,
      signature: template.signature,
    });
    this.error.set('');
    this.editing.set({ mode: 'edit', id: template.id });
  }

  cancel(): void {
    this.editing.set({ mode: 'closed' });
    this.error.set('');
  }

  setField<K extends keyof typeof BLANK_FORM>(key: K, value: string): void {
    this.form.update((current) => ({ ...current, [key]: value }));
  }

  save(): void {
    const state = this.editing();
    if (state.mode === 'closed') return;
    const current = this.form();
    if (!current.name.trim()) {
      this.error.set('Name is required.');
      return;
    }
    this.saving.set(true);
    this.error.set('');
    const payload: CoverLetterTemplateUpsert = {
      name: current.name.trim(),
      tone: current.tone,
      language: current.language,
      opening: current.opening,
      body: current.body,
      signature: current.signature,
    };
    const obs =
      state.mode === 'new'
        ? this.service.create(payload)
        : this.service.update(state.id, payload);
    obs.pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: () => {
        this.saving.set(false);
        this.editing.set({ mode: 'closed' });
        this.refresh();
      },
      error: (err) => {
        this.saving.set(false);
        this.error.set(err?.error?.detail ?? 'Failed to save template');
      },
    });
  }

  remove(template: CoverLetterTemplate): void {
    const ok = window.confirm(`Delete template "${template.name}"?`);
    if (!ok) return;
    this.deletingId.set(template.id);
    this.service.remove(template.id).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: () => {
        this.deletingId.set(null);
        this.refresh();
      },
      error: (err) => {
        this.deletingId.set(null);
        this.error.set(err?.error?.detail ?? 'Failed to delete template');
      },
    });
  }

  isEditing(id: string): boolean {
    const state = this.editing();
    return state.mode === 'edit' && state.id === id;
  }
}
