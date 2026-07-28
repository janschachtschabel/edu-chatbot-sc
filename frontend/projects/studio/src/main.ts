import { bootstrapApplication } from '@angular/platform-browser';

import { AppComponent } from './app/app.component';
import { appConfig } from './app/app.config';

bootstrapApplication(AppComponent, appConfig).catch((err: unknown) => {
  // Nothing has rendered yet at this point, so the only honest channel is the
  // console plus a bare message in the host element.
  console.error('Studio konnte nicht starten:', err);
  const host = document.querySelector('studio-root');
  if (host) host.textContent = 'Studio konnte nicht starten. Bitte Seite neu laden.';
});
