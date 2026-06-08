import { DatePipe } from '@angular/common';
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
import { FormsModule } from '@angular/forms';
import { CoverLetterTemplatesService } from '../../../../core/services/cover-letter-templates.service';
import { CoverLetterTemplate } from '../../models/cover-letter-template.model';
import { CoverLetterTemplateEditingState } from '../../models/cover-letter-template-editing-state.model';
import { CoverLetterTemplateUpsert } from '../../models/cover-letter-template-upsert.model';
import { createSortState } from '../../../../core/utils/sort-state';
import { sortItems } from '../../../../core/utils/sort-items';
import { parseSortToken } from '../../../../core/utils/parse-sort-token';

type TemplateSortField = 'updated' | 'name' | 'tone' | 'language';

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

  sort = createSortState<TemplateSortField>('updated', 'desc', ['name', 'tone', 'language']);
  toneFilter = signal('');
  languageFilter = signal('');

  tones = computed(() => [...new Set(this.templates().map((t) => t.tone))].sort());
  languages = computed(() => [...new Set(this.templates().map((t) => t.language))].sort());

  visibleTemplates = computed(() => {
    let rows = this.templates();
    const tone = this.toneFilter();
    if (tone) rows = rows.filter((t) => t.tone === tone);
    const lang = this.languageFilter();
    if (lang) rows = rows.filter((t) => t.language === lang);
    const field = this.sort.field();
    return sortItems(rows, (t) => this.sortValue(t, field), this.sort.dir());
  });

  private sortValue(t: CoverLetterTemplate, field: TemplateSortField): string | null {
    switch (field) {
      case 'updated': return t.updated_at;
      case 'name': return t.name;
      case 'tone': return t.tone;
      case 'language': return t.language;
    }
  }

  onSortSelect(event: Event): void {
    const parsed = parseSortToken<TemplateSortField>((event.target as HTMLSelectElement).value);
    if (parsed) this.sort.set(parsed.field, parsed.dir);
  }

  onToneFilterChange(event: Event): void {
    this.toneFilter.set((event.target as HTMLSelectElement).value);
  }

  onLanguageFilterChange(event: Event): void {
    this.languageFilter.set((event.target as HTMLSelectElement).value);
  }

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
