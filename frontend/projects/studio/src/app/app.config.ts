/**
 * Studio application providers (P9-2). Zoneless like the widget — no zone.js in
 * either bundle (§7).
 */
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { ApplicationConfig, provideZonelessChangeDetection } from '@angular/core';
import { provideRouter, withComponentInputBinding, withInMemoryScrolling } from '@angular/router';

import { routes } from './app.routes';
import { authErrorInterceptor } from './core/auth-error.interceptor';

export const appConfig: ApplicationConfig = {
  providers: [
    provideZonelessChangeDetection(),
    provideHttpClient(withInterceptors([authErrorInterceptor])),
    provideRouter(
      routes,
      withComponentInputBinding(),
      // Jumping to the top on a view change matches the mental model of
      // "opening a different page"; an in-page anchor keeps its position.
      withInMemoryScrolling({ scrollPositionRestoration: 'top', anchorScrolling: 'enabled' }),
    ),
  ],
};
