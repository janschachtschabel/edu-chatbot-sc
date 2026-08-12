/**
 * Render-/Link-Kontext der Chat-Shell (8-4S-f2) — alles, was Nachrichtentext
 * und Links in darstellbaren Output verwandelt: die MarkdownRenderer-Instanz
 * samt Cache, die drei Trust-/bsid-Wrapper der Instanz und die daraus gebauten
 * Kontext-Objekte, die die 8-2-Renderer als `[ctx]` erwarten.
 *
 * EINE Verantwortung, eigenes Modul: die Komponente ist der Verdrahtungs-
 * Integrator, dieses Modul die Render-Sicht. In ALT liegen dieselben Bausteine
 * als Instanz-Delegates im 1480-Z.-Monolithen (`_markdownRenderer` 1469-1479,
 * `_groupingCtx` 970-973, `isHostTrusted` 254-256, `externalLinkWarning`
 * 1221-1223, `_withBsid` 1228-1230, `displayContent` 1021-1023); Bodies
 * unverändert, nur hinter einem `ShellRenderContext`-Seam statt `this.`.
 *
 * Kein Modul-Global-State: jede Instanz hält ihren eigenen Renderer/Cache.
 */
import { SafeHtml } from '@angular/platform-browser';

import { ChatMessage } from '../grouping/message-types';
import { displayContent, GroupingContext, ResultGroupsContext } from '../grouping/result-grouping';
import type { TranslateFn } from '../i18n/i18n';
import { MarkdownRenderer } from '../markdown/markdown-renderer';
import { externalLinkWarning, isTrustedHost, withBsid } from '../session/trusted-host';

/** Live-Zustand, den die Render-Sicht liest — deferred Arrows (Muster
 *  `ShellHost`/`LifecycleContext`), damit jeder Zugriff frisch ist. */
export interface ShellRenderContext {
  /** `DomSanitizer.bypassSecurityTrustHtml` — nach DOMPurify sicher. */
  bypassSecurityTrustHtml: (html: string) => SafeHtml;
  /** Aktuelle Session-ID (bsid in Link-hrefs + Teil des Render-Cache-Keys). */
  sessionId: () => string;
  /** Effektive Trusted-Domains (Kern-WLO-Liste + `[trustedHosts]` des Hosts). */
  trustedDomains: () => readonly string[];
  /** ALT `inlineResultGroupingBool` — steuert das Bullet-Link-Stripping. */
  inlineResultGrouping: () => boolean;
  /** Übersetzer der Shell (C1-b2) — wandert in die Renderer-Kontexte. Deferred
   *  wie die übrigen Zugriffe: die Shell bekommt ihn als Input, der bei der
   *  Konstruktion des `ShellRender` noch nicht gesetzt sein muss. */
  t: TranslateFn;
}

export class ShellRender {
  private readonly _markdown: MarkdownRenderer;

  constructor(private readonly ctx: ShellRenderContext) {
    this._markdown = new MarkdownRenderer({
      bypassSecurityTrustHtml: (html) => this.ctx.bypassSecurityTrustHtml(html),
      sessionId: () => this.ctx.sessionId(),
      isHostTrusted: (host) => this.isHostTrusted(host),
      withBsid: (url) => this.withBsid(url),
      t: (key, params) => this.ctx.t(key, params),
    });
  }

  /** Markdown → sanitisiertes SafeHtml (mit Render-Cache). ALT `renderMarkdown`. */
  markdown(text: string, sender: 'bot' | 'user' = 'bot'): SafeHtml {
    return this._markdown.render(text, sender);
  }

  /** Render-Cache verwerfen — Aufrufer: die Shell, wenn die Trusted-Hosts-Liste
   *  (async vom Host/Backend) ankommt oder sich ändert. Ohne Reset behielten
   *  gecachte Bubbles ihr `target="_blank"` für jetzt vertraute Hosts. */
  clearCache(): void {
    this._markdown.clearCache();
  }

  /** Hostname auf der effektiven Trusted-Liste? ALT 254-256. */
  isHostTrusted(host: string): boolean {
    return isTrustedHost(host, this.ctx.trustedDomains());
  }

  /** `?bsid=<sessionId>` an Trusted-URLs anhängen. ALT 1228-1230. */
  withBsid(url: string | null | undefined): string {
    return withBsid(url, this.ctx.sessionId(), this.ctx.trustedDomains());
  }

  /** Warntooltip für Hosts außerhalb der Trusted-Liste. ALT 1221-1223. */
  externalLinkWarning(url: string | null | undefined): string {
    return externalLinkWarning(url, this.ctx.trustedDomains(), (k, p) => this.ctx.t(k, p));
  }

  /** Kontext der 8-2g-Grouping-Utils (Swimlanes-Renderer). ALT 970-973. */
  readonly groupingCtx: GroupingContext = {
    withBsid: (url) => this.withBsid(url),
    externalLinkWarning: (url) => this.externalLinkWarning(url),
    t: (key, params) => this.ctx.t(key, params),
  };

  /** Kontext des ResultGroups-Renderers = GroupingContext + Host-Trust-Abfrage
   *  für die Such-CTA-Target-Entscheidung (`_self` vs. `_blank`). */
  readonly resultGroupsCtx: ResultGroupsContext = {
    withBsid: (url) => this.withBsid(url),
    externalLinkWarning: (url) => this.externalLinkWarning(url),
    isTrustedHost: (host) => this.isHostTrusted(host),
    t: (key, params) => this.ctx.t(key, params),
  };

  /** Anzuzeigender Bubble-Text: bei aktivem Inline-Grouping werden die Bullet-
   *  Markdown-Links rausgestrippt, die schon in der Webseiten-Inhalte-Box
   *  stehen (keine Doppelung). ALT 1021-1023. */
  displayContent(msg: ChatMessage): string {
    return displayContent(msg, this.ctx.inlineResultGrouping(), this.groupingCtx);
  }
}
