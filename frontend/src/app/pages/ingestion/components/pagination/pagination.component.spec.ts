import { TestBed } from '@angular/core/testing';
import { PaginationComponent } from './pagination.component';

describe('PaginationComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [PaginationComponent],
    }).compileComponents();
  });

  function mount(opts: { page: number; pageSize: number; total: number; totalPages: number }) {
    const fixture = TestBed.createComponent(PaginationComponent);
    fixture.componentRef.setInput('page', opts.page);
    fixture.componentRef.setInput('pageSize', opts.pageSize);
    fixture.componentRef.setInput('total', opts.total);
    fixture.componentRef.setInput('totalPages', opts.totalPages);
    fixture.detectChanges();
    return fixture;
  }

  function buttons(fixture: ReturnType<typeof mount>) {
    return fixture.nativeElement.querySelectorAll('button.btn-page') as NodeListOf<HTMLButtonElement>;
  }

  it('computes the showing range from page/pageSize/total', () => {
    const fixture = mount({ page: 2, pageSize: 20, total: 55, totalPages: 3 });
    expect(fixture.componentInstance.showingFrom).toBe(21);
    expect(fixture.componentInstance.showingTo).toBe(40);
  });

  it('clamps showingTo to the total on the final page', () => {
    const fixture = mount({ page: 3, pageSize: 20, total: 55, totalPages: 3 });
    expect(fixture.componentInstance.showingFrom).toBe(41);
    expect(fixture.componentInstance.showingTo).toBe(55);
  });

  it('reports a zero range when there are no results', () => {
    const fixture = mount({ page: 1, pageSize: 20, total: 0, totalPages: 1 });
    expect(fixture.componentInstance.showingFrom).toBe(0);
    expect(fixture.componentInstance.showingTo).toBe(0);
  });

  it('emits the next page on Next click', () => {
    const fixture = mount({ page: 1, pageSize: 20, total: 55, totalPages: 3 });
    let emitted: number | null = null;
    fixture.componentInstance.pageChange.subscribe((p) => (emitted = p));

    const [, next] = buttons(fixture);
    next.click();

    expect(emitted).toBe(2);
  });

  it('emits the previous page on Prev click', () => {
    const fixture = mount({ page: 2, pageSize: 20, total: 55, totalPages: 3 });
    let emitted: number | null = null;
    fixture.componentInstance.pageChange.subscribe((p) => (emitted = p));

    const [prev] = buttons(fixture);
    prev.click();

    expect(emitted).toBe(1);
  });

  it('disables Prev on the first page and does not emit', () => {
    const fixture = mount({ page: 1, pageSize: 20, total: 55, totalPages: 3 });
    let emitted = false;
    fixture.componentInstance.pageChange.subscribe(() => (emitted = true));

    const [prev] = buttons(fixture);
    expect(prev.disabled).toBe(true);
    prev.click();
    expect(emitted).toBe(false);
  });

  it('disables Next on the last page and does not emit', () => {
    const fixture = mount({ page: 3, pageSize: 20, total: 55, totalPages: 3 });
    let emitted = false;
    fixture.componentInstance.pageChange.subscribe(() => (emitted = true));

    const [, next] = buttons(fixture);
    expect(next.disabled).toBe(true);
    next.click();
    expect(emitted).toBe(false);
  });

  it('emits the chosen page size as a number on select change', () => {
    const fixture = mount({ page: 1, pageSize: 20, total: 55, totalPages: 3 });
    let emitted: number | null = null;
    fixture.componentInstance.pageSizeChange.subscribe((s) => (emitted = s));

    const select = fixture.nativeElement.querySelector('select.page-size-select') as HTMLSelectElement;
    select.value = '50';
    select.dispatchEvent(new Event('change'));

    expect(emitted).toBe(50);
  });
});
