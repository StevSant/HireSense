import { TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { Subject, of, throwError } from 'rxjs';
import { LoginComponent } from './login.component';
import { AuthService } from '../../core/services/auth.service';

function makeAuth(over: Partial<Record<string, unknown>> = {}) {
  return {
    login: () => of({ access_token: 'tok', token_type: 'bearer' }),
    setToken: () => {},
    ...over,
  };
}

describe('LoginComponent', () => {
  function mount(auth: unknown, router: unknown = { navigate: () => {} }) {
    TestBed.configureTestingModule({
      imports: [LoginComponent],
      providers: [
        { provide: AuthService, useValue: auth },
        { provide: Router, useValue: router },
      ],
    });
    const fixture = TestBed.createComponent(LoginComponent);
    fixture.detectChanges();
    return fixture;
  }

  it('clears the loading signal on successful login', () => {
    const navigate = vi.fn();
    const setToken = vi.fn();
    const fixture = mount(makeAuth({ setToken }), { navigate });
    const cmp = fixture.componentInstance;

    cmp.onSubmit();

    expect(setToken).toHaveBeenCalledWith('tok');
    expect(navigate).toHaveBeenCalledWith(['/dashboard']);
    expect(cmp.loading()).toBe(false);
  });

  it('clears the loading signal on a failed login and surfaces an error', () => {
    const fixture = mount(makeAuth({ login: () => throwError(() => new Error('nope')) }));
    const cmp = fixture.componentInstance;

    cmp.onSubmit();

    expect(cmp.loading()).toBe(false);
    expect(cmp.error()).toBe('Invalid credentials');
  });

  it('keeps loading true while the login request is in flight', () => {
    const pending = new Subject<{ access_token: string; token_type: string }>();
    const fixture = mount(makeAuth({ login: () => pending.asObservable() }));
    const cmp = fixture.componentInstance;

    cmp.onSubmit();
    expect(cmp.loading()).toBe(true);

    pending.next({ access_token: 'tok', token_type: 'bearer' });
    pending.complete();
    expect(cmp.loading()).toBe(false);
  });
});
