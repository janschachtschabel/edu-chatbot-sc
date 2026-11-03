import type { SafeHtml } from '@angular/platform-browser';

import type { KartenAktion, ModulHost, TrefferUmgebung } from '@boerdi/ui-module';

import type { GroupingContext } from '../grouping/result-grouping';
import type { TranslateFn } from '../i18n/i18n';
import { printMarkdownDocument } from '../print/print-utils';

/** Manche Browser lesen die Blob-Adresse erst nach dem Klick; zu frühes Freigeben bricht den Download ab. */
const FREIGABE_NACH_MS = 30_000;

/** Was der Host von der Shell braucht — als Funktionen, weil es Eingaben des Platzhalters sind. */
export interface HostSeams {
  translate(): TranslateFn;
  renderMarkdown(): (content: string) => SafeHtml;
  /** Link-Regeln der Shell: Sitzungs-Kennung bei vertrauten Seiten, Warnhinweis bei fremden. */
  verweise(): Pick<GroupingContext, 'withBsid' | 'externalLinkWarning'>;
  /** Trefferdarstellung der Shell (U1-c2): Kontext der Trefferboxen, Kacheln ja/nein, Zug läuft,
   *  Karten-Aktionen (Volltext, Sammlung, Lernpfad) und „mehr laden“. */
  treffer(): ShellTreffer;
  /** Die Nachricht, zu der die Blöcke gehören — eindeutig, anders als eine abgeleitete
   *  Block-Kennung (gleiche Daten in zwei Antworten ergeben dieselbe). */
  nachrichtId(): string;
  /** Antwort-Weg der Shell (U1-d1): sendet die Antwort als nächsten Zug mit `ui_antwort`. */
  antworten(): ShellAntworten;
}

/** Was die Shell für eine Modul-Antwort braucht (U1-d1). */
export interface ModulAntwortAuftrag {
  readonly nachrichtId: string;
  readonly blockId: string;
  readonly daten: Record<string, unknown>;
  readonly text: string;
}

export type ShellAntworten = (auftrag: ModulAntwortAuftrag) => void;

const KARTEN_AKTIONEN: ReadonlySet<string> = new Set<KartenAktion>(['volltext', 'sammlung', 'lernpfad']);

export interface ShellTreffer {
  readonly kontext: unknown;
  kacheln(): boolean;
  beschaeftigt(): boolean;
  volltext(nodeId: string, title: string): void;
  sammlung(nodeId: string, title: string): void;
  lernpfad(nodeId: string, title: string): void;
  /** U1-h: Unterthemen eines Knotens im Themenbaum laden — ohne Zug, für denselben Baum. */
  zweig(nodeId: string): Promise<Record<string, unknown>>;
  /** Nächste Seite der Sammlung laden — für diese Nachricht. */
  mehrLaden(nachrichtId: string): void;
}

/**
 * Die Umsetzung des Modul-Hosts im Widget (Paket U1). Module rufen nichts selbst nach außen;
 * Datei speichern, Drucken und Markdown-Darstellung gehen über diesen Dienst — Drucken über
 * dasselbe Druckfenster wie bisher die Dokument-Box, Markdown über den Renderer der Bot-Antworten.
 *
 * Seit U1-d1 sehen Module ihn nicht mehr direkt: Jeder Block bekommt einen `BlockModulHost`, der
 * Block-Kennung und Fähigkeiten kennt und hierher weiterreicht — darum heißt das Antworten hier
 * `antwortSenden` und nimmt die Kennung mit.
 */
export class WidgetModulHost implements Omit<ModulHost, 'antworten'> {
  constructor(private readonly seams: HostSeams) {}

  herunterladen(dateiname: string, mime: string, inhalt: string): void {
    const url = URL.createObjectURL(new Blob([inhalt], { type: mime }));
    const a = document.createElement('a');
    a.href = url;
    a.download = dateiname;
    a.rel = 'noopener';
    // Firefox folgt einem download-Anker nur, wenn er im Dokument hängt (wie `saveBlob` im Studio).
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), FREIGABE_NACH_MS);
  }

  drucken(titel: string, markdown: string): void {
    printMarkdownDocument(titel, markdown, this.seams.translate());
  }

  markdown(text: string): SafeHtml {
    return this.seams.renderMarkdown()(text);
  }

  treffer(): TrefferUmgebung {
    const t = this.seams.treffer();
    return { kontext: t.kontext, kacheln: t.kacheln(), beschaeftigt: t.beschaeftigt() };
  }

  beschaeftigt(): boolean {
    return this.seams.treffer().beschaeftigt();
  }

  zweig(nodeId: string): Promise<Record<string, unknown>> {
    return this.seams.treffer().zweig(nodeId);
  }

  antwortSenden(blockId: string, daten: Record<string, unknown>, text: string): void {
    this.seams.antworten()({ nachrichtId: this.seams.nachrichtId(), blockId, daten, text });
  }

  aktion(name: KartenAktion, parameter: { readonly nodeId: string; readonly title: string }): void;
  aktion(name: 'mehrLaden', parameter: { readonly blockId: string }): void;
  aktion(name: KartenAktion | 'mehrLaden', parameter: Record<string, string>): void {
    const t = this.seams.treffer();
    // Die Nachricht kennt der Platzhalter; die Block-Kennung des Moduls ist nicht eindeutig.
    if (name === 'mehrLaden') t.mehrLaden(this.seams.nachrichtId());
    else if (KARTEN_AKTIONEN.has(name)) t[name](parameter['nodeId'], parameter['title']);
    // Grenze für künftige Module: ein falscher Name scheitert sichtbar, nicht als Ausnahme.
    else console.warn('boerdi: unbekannte Modul-Aktion', name);
  }

  link(url: string): { href: string; hinweis: string } {
    const regeln = this.seams.verweise();
    const href = regeln.withBsid(url);
    return { href, hinweis: regeln.externalLinkWarning(href) || '' };
  }
}
