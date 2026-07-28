/**
 * Markdown render pipeline for chat bubbles (§7 `ui/markdown`). Verbatim port of
 * ALT `chat/markdown-render.service.ts`.
 *
 * Pipeline: canvas-sentinel-strip → LaTeX-strip → `@@ICON:…@@` sentinel → marked
 * → DOMPurify → link post-process (target/_blank classification, bsid rewrite,
 * inline-card-title wrap) → SafeHtml + FIFO cache.
 *
 * Deliberately NOT an `@Injectable` singleton: the render cache is
 * component-lifetime state, and the pipeline reads LIVE widget state (sessionId,
 * trusted-host classification). Both arrive as a {@link MarkdownRenderContext}
 * of deferred arrows — the widget shell (task 8-4) provides the real context
 * (Angular `DomSanitizer.bypassSecurityTrustHtml`, the ui `isTrustedHost` /
 * `withBsid`). Behaviour pinned by markdown-renderer.spec.ts (NEU: dedicated
 * spec; ALT pinned it via chat.component.spec.ts). No logic change.
 */
import type { SafeHtml } from '@angular/platform-browser';
import DOMPurify from 'dompurify';
import { marked } from 'marked';

import { ICONS } from '../icons/icons';
import { stripLatex } from './latex';

/** Mapping vom ``@@ICON:NAME@@``-Sentinel auf das deutsche Material-Label.
 *  Wird als Hover-Tooltip auf Inline-Card-Link-Icons gesetzt, damit User
 *  sehen ob ein Inline-Treffer eine Themenseite, eine Sammlung oder ein
 *  konkreter Material-Typ (Video / Arbeitsblatt / Quiz / …) ist.
 *  Quelle der Namen: ``backend`` ``_icon_name_for_card``. */
const INLINE_ICON_LABEL: Record<string, string> = {
  topic: 'Themenseite',
  auto_stories: 'Sammlung',
  play_circle: 'Video',
  article: 'Arbeitsblatt',
  videogame_asset: 'Interaktiver Inhalt',
  headphones: 'Audio',
  quiz: 'Quiz',
  image: 'Präsentation',
  edit_note: 'Übung',
  school: 'Kurs',
  language: 'Webseite',
  menu_book: 'Material',
};

/** Live-Zustand des Widgets, den die Render-Pipeline liest — als deferred
 *  Arrows statt ``this.``-Zugriff. Die Widget-Shell (8-4) liefert die reale
 *  Implementierung. */
export interface MarkdownRenderContext {
  /** ``DomSanitizer.bypassSecurityTrustHtml`` — nach DOMPurify sicher. */
  bypassSecurityTrustHtml: (html: string) => SafeHtml;
  /** Aktuelle Session-ID — Teil des Cache-Keys (bsid in Link-hrefs). */
  sessionId: () => string;
  /** Trusted-Host-Klassifikation (ui ``isTrustedHost`` gegen die V5-Liste). */
  isHostTrusted: (host: string) => boolean;
  /** Hängt ``?bsid=<sessionId>`` an URLs zu Trusted-Hosts an (ui ``withBsid``). */
  withBsid: (url: string | null | undefined) => string;
}

export class MarkdownRenderer {
  /** Cache pro (sender|session|text) → SafeHtml. Identische Inputs liefern
   *  bei jeder Change-Detection-Auswertung dieselbe Instanz zurück, damit
   *  Angular keinen "Wert geändert"-Diff sieht und das ``innerHTML`` NICHT
   *  neu setzt. Ohne diesen Cache liefert ``bypassSecurityTrustHtml()``
   *  bei jedem CD-Tick ein neues Wrapper-Objekt — Angular ersetzt dann
   *  das DOM zwischen Mousedown und Mouseup, das Click-Event entsteht nicht,
   *  Links brauchen 2 Klicks. Map mit primitivem Key altert mit der
   *  Component-Lebenszeit (=> kein Memory-Leak über Page-Wechsel).
   */
  private readonly _renderCache = new Map<string, SafeHtml>();

  constructor(private readonly ctx: MarkdownRenderContext) {}

  /** Explizite Cache-Invalidierung — Aufrufer: Widget-Shell wenn die
   *  Trusted-Hosts-Liste (async vom Backend) ankommt/sich ändert. Ohne Reset
   *  würden gecachte Bubbles Links zu Trusted-Hosts weiter mit
   *  ``target="_blank"`` zeigen, weil der Cache-Hit das Re-Rendering
   *  überspringt. */
  clearCache(): void {
    this._renderCache.clear();
  }

  render(text: string, sender: 'bot' | 'user' = 'bot'): SafeHtml {
    if (!text) return this.ctx.bypassSecurityTrustHtml('');
    // sessionId Teil des Cache-Keys: nach resetSession() ändert sich die
    // bsid, die ``withBsid`` in die Link-hrefs einbaut — ohne sessionId im
    // Key würde eine gecachte Bubble mit ALTER bsid wiederverwendet.
    const cacheKey = sender + '|' + (this.ctx.sessionId() || '') + '|' + text;
    const cached = this._renderCache.get(cacheKey);
    if (cached) return cached;
    // Backend-Sentinel ``<!-- boerdi:printable-canvas|... -->`` strippen,
    // bevor marked parsed wird. Diese Marker signalisieren dem Frontend, dass
    // das angehängte Markdown via Print-Button als PDF abgreifbar ist. Im
    // Render-Output sind sie nicht erwünscht — DOMPurify würde HTML-Kommentare
    // zwar abräumen, aber sicherer ist sie hier schon vor marked zu entfernen.
    const withoutCanvasSentinel = text.replace(
      /<!--\s*boerdi:printable-canvas\|[^|]*\|[^>]*?\s*-->\s*/g,
      '',
    );
    // LaTeX-Stripping via gemeinsamen Helper — wandelt ``\frac12``,
    // ``\frac{1}{2}``, ``\sqrt{2}`` und ``$x$`` in lesbaren Text.
    const withoutLatex = stripLatex(withoutCanvasSentinel);
    // Backend-Sentinel ``@@ICON:NAME@@`` durch Inline-SVG-Span ersetzen,
    // bevor marked parsed. Ersatz passiert VOR marked, damit das Span IN den
    // ``<a>``-Tag wandert (Sentinel steht innerhalb der Link-Klammern beim
    // Backend). ``data-bb-type`` trägt das deutsche Label, aus dem der
    // ``<a>``-Post-Process einen ``title``-Tooltip baut.
    const withIcons = withoutLatex.replace(/@@ICON:([a-z_]+)@@/g, (_match, name) => {
      const key = name as keyof typeof ICONS;
      const svg = ICONS[key];
      if (!svg) return '';
      const label = INLINE_ICON_LABEL[name] || '';
      const attr = label ? ` data-bb-type="${label}"` : '';
      return `<span class="bb-inline-icon"${attr}>${svg}</span>`;
    });
    // Use marked to parse Markdown to HTML, then DOMPurify to defang any
    // injected HTML/JS coming from bot output, persisted history, or tool
    // results. NEVER bypass sanitization on raw text — replace-based regex
    // builders are not safe against `<script>` / `onerror=` injection.
    //
    // For USER messages we use ``parseInline`` instead of ``parse``: users
    // type plain text (no headings/lists/codeblocks), and ``parse`` would
    // wrap the message in a block-level ``<p>`` which adds unwanted vertical
    // padding to user bubbles. ``parseInline`` returns inline markup only.
    let html: string;
    if (sender === 'user') {
      html = marked.parseInline(withIcons, { async: false, gfm: true, breaks: true }) as string;
    } else {
      html = marked.parse(withIcons, { async: false, gfm: true, breaks: true }) as string;
    }
    // Inline-SVG-Icons aus Backend-Sentinels müssen die DOMPurify-Sanitization
    // überleben — das ``svg``-Profile erlaubt die nötigen Tags + Attribute.
    // Sicherheit: Skript-Tags, on*-Attribute usw. werden trotzdem gestripped,
    // weil HTML+SVG-Profile additiv sind.
    const clean = DOMPurify.sanitize(html, {
      ADD_ATTR: ['target', 'rel', 'data-bb-type'],
      USE_PROFILES: { html: true, svg: true, svgFilters: true },
    });
    // Post-Process: (1) Externe Links (NICHT auf der Trusted-Hosts-Liste)
    // in neuem Tab öffnen — Tabnabbing-sicher via ``rel="noopener noreferrer"``.
    // Trusted-Hosts bleiben same-tab, damit das Outgoing-Link-Rewrite des
    // Widgets ``?bsid=<sid>`` anhängen kann und die Session über die TLD-Grenze
    // erhalten bleibt. (2) Inline-Card-Title-Wrap für korrektes Icon-Title-CSS.
    let final = clean;
    if (clean.includes('<a ')) {
      try {
        const tmp = document.createElement('div');
        tmp.innerHTML = clean;
        tmp.querySelectorAll('a').forEach(a => {
          // (1) Target-Klassifikation + bsid-Rewrite. Anker (#frag), Mailto,
          // Tel, javascript: und same-origin-Pfad-Links unangetastet lassen.
          const href = a.getAttribute('href') || '';
          if (href && !href.startsWith('#') && !href.startsWith('javascript:')
              && !href.startsWith('mailto:') && !href.startsWith('tel:')) {
            let hostname = '';
            try {
              hostname = new URL(href, window.location.href).hostname.toLowerCase();
            } catch { hostname = ''; }
            const sameOrigin = hostname && hostname === window.location.hostname.toLowerCase();
            const trusted = !!hostname && this.ctx.isHostTrusted(hostname);
            // Externe + nicht-vertrauenswürdige Hosts → neuer Tab + Warntooltip.
            // Same-origin und trusted hosts → same tab (für ?bsid=-Handoff).
            if (hostname && !sameOrigin && !trusted) {
              if (!a.hasAttribute('target')) a.setAttribute('target', '_blank');
              if (!a.hasAttribute('rel')) a.setAttribute('rel', 'noopener noreferrer');
              // Warntooltip nur setzen wenn kein anderer (z.B. Material-Typ-
              // Label vom Inline-Card-Link) bereits einen ``title`` gesetzt hat.
              const existingTitle = a.getAttribute('title') || '';
              const warn = 'Achtung! Externe URL.';
              if (!existingTitle) {
                a.setAttribute('title', warn);
              } else if (!existingTitle.includes(warn)) {
                a.setAttribute('title', `${existingTitle} — ${warn}`);
              }
            }
            // Bei trusted-Hosts ``?bsid=`` schon im href verankern — dann
            // funktionieren auch Right-Click→Copy-Link, Middle-Click und
            // Screen-Reader, nicht nur Plain-Left-Click via document-handler.
            if (trusted) {
              const rewritten = this.ctx.withBsid(href);
              if (rewritten !== href) a.setAttribute('href', rewritten);
            }
          }

          // (2) Inline-Card-Title-Wrap (nur wenn Backend-Inline-Icon-Span
          // als erstes Child vorhanden ist).
          const iconSpan = a.querySelector(':scope > .bb-inline-icon');
          if (!iconSpan) return;
          // (2a) Material-Typ-Label vom Icon-Span auf Parent-<a> als
          // ``title``-Tooltip durchreichen.
          const typeLabel = iconSpan.getAttribute('data-bb-type') || '';
          if (typeLabel && !a.hasAttribute('title')) {
            a.setAttribute('title', typeLabel);
            iconSpan.setAttribute('title', typeLabel);
          }
          const titleSpan = document.createElement('span');
          titleSpan.className = 'bb-link-title';
          let node = iconSpan.nextSibling;
          while (node) {
            const next = node.nextSibling;
            titleSpan.appendChild(node);
            node = next;
          }
          if (titleSpan.firstChild?.nodeType === 3) {
            const t = titleSpan.firstChild as Text;
            t.textContent = (t.textContent ?? '').replace(/^\s+/, '');
          }
          a.appendChild(titleSpan);
        });
        final = tmp.innerHTML;
      } catch { /* fall back to unprocessed clean */ }
    }
    const safe = this.ctx.bypassSecurityTrustHtml(final);
    // FIFO-Cap — die Map wuchs sonst unbegrenzt (ein Eintrag pro einzigartiger
    // Nachricht, Widget lebt die ganze Seiten-Session). 300 deckt sehr lange
    // Chats; Älteste fliegen raus.
    if (this._renderCache.size >= 300) {
      const oldest = this._renderCache.keys().next().value;
      if (oldest !== undefined) this._renderCache.delete(oldest);
    }
    this._renderCache.set(cacheKey, safe);
    return safe;
  }
}
