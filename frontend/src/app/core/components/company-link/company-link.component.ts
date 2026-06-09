import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { RouterLink } from '@angular/router';

// Renders a company name as a link to its company detail page. Inherits the
// surrounding text style (color/font) so it drops into tables, headings and
// panels without restyling, and stops click propagation so it can sit inside
// clickable rows. Falls back to an em dash when no company is set.
@Component({
  selector: 'app-company-link',
  standalone: true,
  imports: [RouterLink],
  template: `@if (name()) {
      <a class="company-link" [routerLink]="['/dashboard/company', name()]" (click)="$event.stopPropagation()">{{ name() }}</a>
    } @else {
      <span class="company-link-empty">—</span>
    }`,
  styles: `
    .company-link {
      color: inherit;
      text-decoration: none;
      cursor: pointer;
    }
    .company-link:hover {
      color: var(--accent);
      text-decoration: underline;
    }
    .company-link-empty { color: var(--text-muted); }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CompanyLinkComponent {
  name = input<string | null | undefined>(null);
}
