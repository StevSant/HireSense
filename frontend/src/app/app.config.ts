import { ApplicationConfig, ErrorHandler, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { routes } from './app.routes';
import { credentialsInterceptor } from './core/interceptors/credentials.interceptor';
import { timeoutInterceptor } from './core/interceptors/timeout.interceptor';
import { errorInterceptor } from './core/interceptors/error.interceptor';
import { errorLoggingInterceptor } from './core/interceptors/error-logging.interceptor';
import { GlobalErrorHandler } from './core/error-handler';
import { environment } from '../environments/environment';
import { demoApiInterceptor } from './demo/demo-api.interceptor';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes),
    // timeoutInterceptor runs LAST (closest to the backend) so its timeout()
    // wraps only the raw HTTP call — the abort itself is unaffected by
    // position, but the synthetic 408 it throws on expiry must still flow
    // back UP through errorLoggingInterceptor and errorInterceptor's
    // catchError (interceptors "wrap" the ones after them, seeing whatever
    // error the inner one produces or synthesizes). Registering it any
    // earlier — e.g. right after credentials — puts it OUTSIDE errorLogging,
    // so a client-side timeout would never reach ErrorReportingService/
    // telemetry: errorLogging only observes errors that surface from what it
    // wraps. errorLoggingInterceptor itself still runs after credentials
    // (withCredentials) and error (401 recovery); it only taps + rethrows.
    provideHttpClient(
      withInterceptors([
        ...(environment.demo ? [demoApiInterceptor] : []),
        credentialsInterceptor,
        errorInterceptor,
        errorLoggingInterceptor,
        timeoutInterceptor,
      ]),
    ),
    { provide: ErrorHandler, useClass: GlobalErrorHandler },
  ],
};
