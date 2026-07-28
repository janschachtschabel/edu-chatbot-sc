/**
 * BOERDi widget bootstrap — builds the single-file custom element `<boerdi-chat>`
 * embedded on any host page via:
 *
 *   <script src="/widget/boerdi-widget.js" defer></script>
 *   <boerdi-chat api-url="https://api.wlo.de"></boerdi-chat>
 *
 * NEU vs ALT: no `import 'zone.js'` — the application is bootstrapped zoneless.
 *
 * This file does exactly two things: define the element once, and give it the
 * §5.5 JavaScript API. The forwarding rule itself lives in `element-api.ts`
 * (testable without booting an app).
 */
import { provideZonelessChangeDetection } from '@angular/core';
import { createCustomElement } from '@angular/elements';
import { createApplication } from '@angular/platform-browser';

import { WidgetComponent } from './app/widget/widget.component';
import { patchElementApi } from './element-api';
import { watchSingleInstance } from './single-instance';

const ELEMENT_NAME = 'boerdi-chat';

void (async () => {
  // Double-define guard — the bundle may be included more than once on a host page.
  if (customElements.get(ELEMENT_NAME)) return;

  const app = await createApplication({
    providers: [provideZonelessChangeDetection()],
  });
  const element = createCustomElement(WidgetComponent, { injector: app.injector });
  patchElementApi(element.prototype);
  customElements.define(ELEMENT_NAME, element);

  // Doppelte *Elemente* ausblenden (der Guard oben verhindert nur doppelte
  // *Registrierung*). Grund: WordPress-Einbettungen mit dem Snippet in Theme-
  // Header UND Content-Block — siehe `single-instance.ts`.
  watchSingleInstance(ELEMENT_NAME);
})().catch((err) => console.error('[BOERDi Widget] bootstrap failed:', err));
