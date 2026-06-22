import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { NotificationsComponent } from './notifications.component';

describe('NotificationsComponent', () => {
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [NotificationsComponent],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    httpMock = TestBed.inject(HttpTestingController);
  });

  it('loads status on init', () => {
    const fixture = TestBed.createComponent(NotificationsComponent);
    fixture.detectChanges();
    const req = httpMock.expectOne('/api/notifications/status');
    req.flush({ enabled: true, recipient_masked: 'a***@x.com' });
    expect(fixture.componentInstance.status()?.enabled).toBe(true);
    httpMock.verify();
  });
});
