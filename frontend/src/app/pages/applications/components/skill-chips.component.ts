import { Component, input, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-skill-chips',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './skill-chips.component.html',
  styleUrl: './skill-chips.component.scss',
})
export class SkillChipsComponent {
  skills = input<string[]>([]);
  editable = input<boolean>(false);
  variant = input<'default' | 'matched' | 'missing'>('default');
  add = output<string>();
  remove = output<string>();

  draft = signal('');

  onAdd(): void {
    const value = this.draft().trim().toLowerCase();
    if (!value) return;
    if (this.skills().includes(value)) {
      this.draft.set('');
      return;
    }
    this.add.emit(value);
    this.draft.set('');
  }

  onRemove(skill: string): void {
    this.remove.emit(skill);
  }
}
