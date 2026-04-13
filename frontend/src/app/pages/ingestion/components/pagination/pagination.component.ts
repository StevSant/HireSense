import { Component, input, output } from '@angular/core';
import { DecimalPipe } from '@angular/common';

@Component({
  selector: 'app-pagination',
  standalone: true,
  imports: [DecimalPipe],
  templateUrl: './pagination.component.html',
  styleUrl: './pagination.component.scss',
})
export class PaginationComponent {
  page = input.required<number>();
  pageSize = input.required<number>();
  total = input.required<number>();
  totalPages = input.required<number>();

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
