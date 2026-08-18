/**
 * E2E harness: embeds the **built** widget bundle into a synthetic host page.
 *
 * Both the host page and the backend are served by Playwright's request
 * interception, which buys three things a dev-server harness cannot:
 *   - the page URL is freely choosable, so the page-context detector can be
 *     driven by a realistic WLO URL (`/components/render/<uuid>`);
 *   - no port, no compose, no backend — the suite is deterministic and runs in
 *     CI right after `npm run build:widget`;
 *   - the artifact under test is the shipped single file, not a dev build.
 *
 * Deviation from the plan row for 8-7 ("Playwright gegen Dev-Compose"): a
 * full-stack run against compose stays a *live* check (user domain, like the
 * golden runs) — it cannot be deterministic, because the answers come from an
 * LLM. What is pinned here is the widget's half of the contract: request
 * shape out, rendering in.
 *
 * Run from `frontend/`: `npx playwright test`.
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { Page, expect } from '@playwright/test';

import { chatResponse, guideModeConfig, sseBody } from './backend-payloads';

export const HOST = 'https://host.test';
export const API = 'https://api.test';

const BUNDLE = 'dist/widget/browser/main.js';

let bundleCache: string | null = null;

function bundle(): string {
  if (bundleCache === null) {
    const path = resolve(process.cwd(), BUNDLE);
    try {
      bundleCache = readFileSync(path, 'utf8');
    } catch {
      throw new Error(
        `Widget-Bundle fehlt: ${path}\n`
        + 'Erst bauen (aus frontend/): npm run build:widget',
      );
    }
  }
  return bundleCache;
}

/** Captured `POST /api/chat/stream` body. */
export interface ChatRequest {
  session_id: string;
  message: string;
  environment: Record<string, any>;
  action?: string;
  action_params?: Record<string, any>;
}

export interface MountOptions {
  /** Page URL of the host page — drives the page-context detector. */
  url?: string;
  /** Extra attributes on `<boerdi-chat>` (kebab-case, as documented in §5.5). */
  attrs?: Record<string, string>;
  /** Response for `GET /api/config/guide-mode`; `null` = backend unreachable. */
  config?: Record<string, unknown> | null;
  /** Embed the element twice (single-instance guard). */
  duplicate?: boolean;
  /**
   * Emulated motion preference. Defaults to `reduce`, because the FAB bobs and
   * breathes forever (§5.5 "FAB+Puls") and Playwright's actionability check
   * never sees an animating element come to rest — every FAB click would time
   * out. Asking for reduced motion is honest where `force: true` would not be:
   * the widget answers with `animation: none` (WCAG 2.3.3), a real code path,
   * and embed.spec.ts pins both branches.
   */
  motion?: 'reduce' | 'no-preference';
  /**
   * Vorhandene Session-ID in den localStorage legen, BEVOR das Bundle lädt —
   * simuliert den Wiederkehrer. Der Unterschied ist verhaltensrelevant: die
   * proaktive Kontext-Begrüßung hängt am Resume-Pfad (`_afterResume`), eine
   * frische Session pingt nie (ALT chat.component.ts:738 — geprüft).
   */
  session?: string;
  /**
   * Antwort auf Kontext-Pings (`environment.page_event`). Vorgabe: LEER — das
   * Backend hat zu einer beliebigen Seite meist nichts zu sagen, und genau
   * dann fällt das Widget auf seine normale Begrüssung zurück. Wer die
   * Kontextmeldung sprechen lassen will, setzt sie hier.
   */
  pingReply?: Record<string, unknown>;
  /**
   * Rahmenloser Einbau (U1) — EIN Schalter für drei Dinge, die zusammengehören
   * und sonst auseinanderlaufen: das Attribut `embed-mode="frameless"`, die
   * Gastanwendung drumherum (eigene Kopfleiste + Flex-Platz für den Chat, wie
   * `docs/browser-plugin-einbindung.md` §2 sie beschreibt) und der Verzicht
   * auf den FAB, den es rahmenlos nicht gibt.
   *
   * Der Wirt ist nicht Zierrat: im schlichten Body wäre ein ausgebrochenes
   * Panel von einem korrekt gefüllten nicht zu unterscheiden.
   */
  frameless?: boolean;
}

export interface Harness {
  /** Klickt den FAB und wartet, bis das Panel bedienbar ist. Rahmenlos entfällt
   *  der Klick — dort gibt es keinen FAB und der Chat steht schon; die Zusage
   *  „danach ist die Eingabe da" gilt aber in beiden Modi. */
  open(): Promise<void>;
  /** Queue results for the next turns (FIFO); default is a plain text answer.
   *  Kontext-Pings bedienen sich hier NICHT — siehe `pingReply`. */
  enqueue(...responses: Record<string, unknown>[]): void;
  /** Chat requests captured so far, in order — Pings eingeschlossen. */
  chatRequests(): ChatRequest[];
  /** Nur die echten Züge: Pings (`page_event`) herausgefiltert. Seit der
   *  Seitenkontext-Erweiterung pingt jede frische Sitzung, ein `[0]` auf
   *  `chatRequests()` träfe also den Ping statt den gemeinten Zug. */
  turnRequests(): ChatRequest[];
  /** Wait until at least `n` chat requests have arrived. */
  waitForChatRequests(n: number, timeout?: number): Promise<void>;
  /** Wie `waitForChatRequests`, aber ohne Pings mitzuzählen. */
  waitForTurns(n: number, timeout?: number): Promise<void>;
}

/** Ein Kontext-Ping trägt `page_event`; ein getippter/geklickter Zug nicht. */
function istPing(r: ChatRequest): boolean {
  return !!r.environment?.['page_event'];
}

/** Der Wirt für den rahmenlosen Einbau. Bewusst NUR in diesem Zweig: die
 *  schlichte Seite ist die Grundlage von rund einem Dutzend Tests, und eine
 *  global gesetzte Höhe/Randlosigkeit hätte deren Messungen mitverändert. */
const WIRT_STIL = `<style>
      html, body { margin: 0; height: 100%; }
      .wirt { display: flex; flex-direction: column; height: 100%; }
      .wirt-kopf { flex: none; height: 44px; background: #eef1f5; }
      /* Der Platz ist ABSICHTLICH auf beiden Achsen kleiner als der Viewport:
         die Kopfleiste versetzt ihn senkrecht, der Seitenabstand waagerecht.
         Ohne den Abstand wäre er genau so breit wie das Fenster, und ein
         durchgeschlagenes 100vw bliebe unsichtbar — die Zusicherung hätte dann
         keine Zähne. (Keine Backticks hier: dieser Block steht in einem
         Template-Literal.) */
      .wirt-platz { flex: 1; min-height: 0; margin-inline: 12px; }
    </style>`;

function harnessHtml(opts: MountOptions): string {
  const attrs = Object.entries({
    'api-url': API,
    ...(opts.frameless ? { 'embed-mode': 'frameless' } : {}),
    ...(opts.attrs ?? {}),
  })
    .map(([k, v]) => `${k}="${v}"`)
    .join(' ');
  const element = `<boerdi-chat ${attrs}></boerdi-chat>`;
  const koerper = opts.frameless
    ? `<div class="wirt">
      <header class="wirt-kopf">Leiste der Gastanwendung</header>
      <main class="wirt-platz">${element}</main>
    </div>`
    : `<h1>Host-Seite</h1>
    ${element}
    ${opts.duplicate ? element : ''}`;
  return `<!doctype html>
<html lang="de">
  <head><meta charset="utf-8" /><title>Host-Seite</title>${opts.frameless ? WIRT_STIL : ''}</head>
  <body>
    ${koerper}
    <script src="/boerdi-widget.js"></script>
  </body>
</html>`;
}

/** Install the routes, load the host page, return the harness handle. */
export async function mount(page: Page, opts: MountOptions = {}): Promise<Harness> {
  const queue: Record<string, unknown>[] = [];
  const requests: ChatRequest[] = [];
  const config = opts.config === undefined ? guideModeConfig() : opts.config;

  /**
   * Antwort auf EINEN Request. Ein Kontext-Ping bekommt die (vorgabegemäss
   * leere) `pingReply` und nimmt der Warteschlange **nichts** weg: sonst
   * schnappte er die Antwort weg, die ein Test für seinen eigenen Zug
   * hinterlegt hat — ein reines Testartefakt.
   */
  const antwortAuf = (r: ChatRequest): Record<string, unknown> => (
    istPing(r)
      ? (opts.pingReply ?? chatResponse({ content: '', quick_replies: [] }))
      : (queue.shift() ?? chatResponse())
  );

  await page.emulateMedia({ reducedMotion: opts.motion ?? 'reduce' });

  if (opts.session) {
    await page.addInitScript(
      (id) => localStorage.setItem('boerdi_session_id', id),
      opts.session,
    );
  }

  await page.route((url) => url.host === 'host.test', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('.js')) {
      return route.fulfill({ contentType: 'text/javascript; charset=utf-8', body: bundle() });
    }
    return route.fulfill({ contentType: 'text/html; charset=utf-8', body: harnessHtml(opts) });
  });

  await page.route((url) => url.host === 'api.test', async (route) => {
    const req = route.request();
    const path = new URL(req.url()).pathname;

    if (path === '/api/config/guide-mode') {
      if (config === null) return route.abort('failed');
      return route.fulfill({ json: config });
    }
    // Speech off keeps the run deterministic: no mic permission prompt, no
    // audio element. The provider-split path (#122) does exactly this.
    if (path === '/api/speech/status') {
      return route.fulfill({ json: { enabled: false } });
    }
    if (path === '/api/chat/stream') {
      const payload = req.postDataJSON() as ChatRequest;
      requests.push(payload);
      return route.fulfill({ contentType: 'text/event-stream', body: sseBody(antwortAuf(payload)) });
    }
    // Hintergrund-Turns (Tour-Start/-Tick, Kontext-Ping) laufen wie in ALT
    // non-streaming über POST /api/chat — beide Wege werden erfasst, damit
    // `chatRequests()` die echte Reihenfolge zeigt.
    if (path === '/api/chat') {
      const payload = req.postDataJSON() as ChatRequest;
      requests.push(payload);
      return route.fulfill({ json: antwortAuf(payload) });
    }
    if (path.startsWith('/api/sessions/')) {
      return route.fulfill({ json: [] });
    }
    return route.fulfill({ status: 404, json: { detail: `nicht gestubbt: ${path}` } });
  });

  await page.goto(opts.url ?? `${HOST}/`);
  // Rahmenlos gibt es keinen FAB, auf den zu warten wäre — der Chat steht dort
  // sofort (`chatMounted()` in widget.component.ts).
  await expect(
    page.locator(opts.frameless ? 'boerdi-chat .chat-input' : 'boerdi-chat .boerdi-fab').first(),
  ).toBeVisible();

  return {
    async open() {
      if (!opts.frameless) await page.locator('.boerdi-fab').first().click();
      await expect(page.locator('.chat-input')).toBeVisible();
    },
    enqueue(...responses) {
      queue.push(...responses);
    },
    chatRequests() {
      return requests;
    },
    turnRequests() {
      return requests.filter((r) => !istPing(r));
    },
    async waitForChatRequests(n, timeout) {
      await expect.poll(() => requests.length, { message: `${n} Chat-Requests erwartet`, timeout })
        .toBeGreaterThanOrEqual(n);
    },
    async waitForTurns(n, timeout) {
      await expect
        .poll(() => requests.filter((r) => !istPing(r)).length,
          { message: `${n} echte Züge erwartet`, timeout })
        .toBeGreaterThanOrEqual(n);
    },
  };
}
