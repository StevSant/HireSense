import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { NotificationService } from './notification.service';

describe('NotificationService', () => {
  let service: NotificationService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [NotificationService, provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(NotificationService);
    httpMock = TestBed.inject(HttpTestingController);
  });
  afterEach(() => httpMock.verify());

  it('gets status', () => {
    let result: unknown;
    service.status().subscribe((r) => (result = r));
    const req = httpMock.expectOne('/api/notifications/status');
    expect(req.request.method).toBe('GET');
    req.flush({ enabled: true, recipient_masked: 'a***@x.com' });
    expect((result as { enabled: boolean }).enabled).toBe(true);
  });

  it('sends a test', () => {
    service.sendTest().subscribe();
    const req = httpMock.expectOne('/api/notifications/test');
    expect(req.request.method).toBe('POST');
    req.flush({ sent: true });
  });
});
