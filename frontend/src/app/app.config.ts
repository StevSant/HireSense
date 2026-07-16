import { ApplicationConfig, ErrorHandler, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { routes } from './app.routes';
import { authInterceptor } from './core/interceptors/auth.interceptor';
import { timeoutInterceptor } from './core/interceptors/timeout.interceptor';
import { errorInterceptor } from './core/interceptors/error.interceptor';
import { errorLoggingInterceptor } from './core/interceptors/error-logging.interceptor';
import { GlobalErrorHandler } from './core/error-handler';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes),
    // timeoutInterceptor runs right after auth so its timeout() wraps the
    // entire downstream chain (error + errorLogging + backend) — a hung
    // request gets aborted there instead of waiting on it. errorLoggingInterceptor
    // runs LAST so auth (token attach) and error (401 recovery) interceptors
    // execute first; it only taps + rethrows.
    provideHttpClient(
      withInterceptors([
        authInterceptor,
        timeoutInterceptor,
        errorInterceptor,
        errorLoggingInterceptor,
      ]),
    ),
    { provide: ErrorHandler, useClass: GlobalErrorHandler },
  ],
};
