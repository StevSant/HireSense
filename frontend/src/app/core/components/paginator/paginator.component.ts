import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';
import { DecimalPipe } from '@angular/common';

// Page sizes offered when a host does not narrow them. Hosts whose endpoint
// caps the page lower (or whose rows are expensive to render) pass their own.
const DEFAULT_PAGE_SIZE_OPTIONS: readonly number[] = [20, 50, 100];

@Component({
  selector: 'app-paginator',
  standalone: true,
  imports: [DecimalPipe],
  templateUrl: './paginator.component.html',
  styleUrl: './paginator.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PaginatorComponent {
  page = input.required<number>();
  pageSize = input.required<number>();
  total = input.required<number>();
  totalPages = input.required<number>();
  itemLabel = input<string>('jobs');
  pageSizeOptions = input<readonly number[]>(DEFAULT_PAGE_SIZE_OPTIONS);

  pageChange = output<number>();
  pageSizeChange = output<number>();

  get showingFrom(): number {
    return this.total() === 0 ? 0 : (this.page() - 1) * this.pageSize() + 1;
  }

  get showingTo(): number {
    return Math.min(this.page() * this.pageSize(), this.total());
  }

  onPrev(): void {
    if (this.page() > 1) {
      this.pageChange.emit(this.page() - 1);
    }
  }

  onNext(): void {
    if (this.page() < this.totalPages()) {
      this.pageChange.emit(this.page() + 1);
    }
  }

  onPageSizeChange(event: Event): void {
    const select = event.target as HTMLSelectElement;
    this.pageSizeChange.emit(Number(select.value));
  }
}
