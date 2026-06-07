import { ApplicationConfig, ErrorHandler, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { routes } from './app.routes';
import { authInterceptor } from './core/interceptors/auth.interceptor';
import { errorInterceptor } from './core/interceptors/error.interceptor';
import { errorLoggingInterceptor } from './core/interceptors/error-logging.interceptor';
import { GlobalErrorHandler } from './core/error-handler';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes),
    // errorLoggingInterceptor runs LAST so auth (token attach) and error
    // (401 recovery) interceptors execute first; it only taps + rethrows.
    provideHttpClient(
      withInterceptors([authInterceptor, errorInterceptor, errorLoggingInterceptor]),
    ),
    { provide: ErrorHandler, useClass: GlobalErrorHandler },
  ],
};
