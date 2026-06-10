import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { NetworkCardComponent } from './network-card.component';
import { environment } from '../../../../../environments/environment';

describe('NetworkCardComponent', () => {
  let fixture: ComponentFixture<NetworkCardComponent>;
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [NetworkCardComponent],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    fixture = TestBed.createComponent(NetworkCardComponent);
    httpMock = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
  });

  afterEach(() => httpMock.verify());

  it('renders the upload hint', () => {
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain("Upload LinkedIn's data-export ZIP or Connections.csv");
    expect(text).toContain('never enter AI prompts');
  });

  it('shows import count and date on successful import', () => {
    const comp = fixture.componentInstance;
    const file = new File(['a,b'], 'Connections.csv', { type: 'text/csv' });

    // Trigger import by calling onFileSelected with a fake event
    const input = fixture.nativeElement.querySelector('input[type="file"]') as HTMLInputElement;
    Object.defineProperty(input, 'files', {
      value: { 0: file, length: 1, item: () => file },
      configurable: true,
    });
    comp.onFileSelected({ target: input } as unknown as Event);

    httpMock
      .expectOne(`${environment.apiUrl}/network/import`)
      .flush({ contacts: 150, imported_at: '2026-06-09T00:00:00Z' });

    fixture.detectChanges();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('150 contacts imported');
  });

  it('shows detail in the alert on failed import', () => {
    const comp = fixture.componentInstance;
    const file = new File(['a,b'], 'Connections.csv', { type: 'text/csv' });

    const input = fixture.nativeElement.querySelector('input[type="file"]') as HTMLInputElement;
    Object.defineProperty(input, 'files', {
      value: { 0: file, length: 1, item: () => file },
      configurable: true,
    });
    comp.onFileSelected({ target: input } as unknown as Event);

    httpMock
      .expectOne(`${environment.apiUrl}/network/import`)
      .flush({ detail: 'File too large' }, { status: 413, statusText: 'Payload Too Large' });

    fixture.detectChanges();
    const alert = (fixture.nativeElement as HTMLElement).querySelector('[role="alert"]');
    expect(alert).toBeTruthy();
    expect(alert!.textContent).toContain('File too large');
  });
});
