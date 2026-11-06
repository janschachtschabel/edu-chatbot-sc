import type { SafeHtml } from '@angular/platform-browser';

import type {
  AblageSchritt, AuftragSchritt, KartenAktion, ModulFaehigkeit, ModulHost, TrefferUmgebung,
} from '@boerdi/ui-module';

import type { WidgetModulHost } from './widget-modul-host';

const OHNE_LINK = { href: '', hinweis: '' } as const;
const OHNE_ADRESSEN = { withBsid: () => '', externalLinkWarning: () => '' } as const;

/**
 * Der Host EINES Blocks (Paket U1-d1, aus U1-b1 verschoben). Der Platzhalter gibt ihn jedem Block
 * über den Injector von `NgComponentOutlet`. Er kennt die Block-Kennung — eine Antwort trägt sie,
 * ohne dass das Modul sie nennt — und lässt nur zu, was das Manifest unter `faehigkeiten` angibt:
 * `herunterladen`, `drucken`, `oeffnen` (Links und Karten-Aktionen), `antworten` (samt
 * `vormerken`, U2), `nachladen` (U1-h), `hochladen` (U3-2c) und `auftrag` (K1b). Fehlt eine, passiert nichts außer einer Warnung; `zweig` lehnt dann mit `status: 403` ab
 * (wie das Backend für „nicht angeboten“ — das Modul bietet keinen neuen Versuch an). Darstellung
 * (`markdown`, `treffer`, `beschaeftigt`) ist immer erlaubt; ohne `oeffnen` baut der Kontext von
 * `treffer` aber keine Adressen.
 */
export class BlockModulHost implements ModulHost {
  private readonly erlaubt: ReadonlySet<ModulFaehigkeit>;

  constructor(
    private readonly basis: WidgetModulHost,
    private readonly blockId: string,
    faehigkeiten: readonly ModulFaehigkeit[] | undefined,
  ) {
    this.erlaubt = new Set(faehigkeiten ?? []);
  }

  private darf(faehigkeit: ModulFaehigkeit): boolean {
    if (this.erlaubt.has(faehigkeit)) return true;
    console.warn('boerdi: Modul-Fähigkeit fehlt', faehigkeit, this.blockId);
    return false;
  }

  herunterladen(dateiname: string, mime: string, inhalt: string): void {
    if (this.darf('herunterladen')) this.basis.herunterladen(dateiname, mime, inhalt);
  }

  drucken(titel: string, markdown: string): void {
    if (this.darf('drucken')) this.basis.drucken(titel, markdown);
  }

  markdown(text: string): SafeHtml {
    return this.basis.markdown(text);
  }

  link(url: string): { readonly href: string; readonly hinweis: string } {
    return this.darf('oeffnen') ? this.basis.link(url) : OHNE_LINK;
  }

  /** Darstellung ist immer erlaubt; die Adressen der Trefferboxen baut der Kontext der Shell aber
   *  nur mit `oeffnen` (Review U1 gesamt) — sonst liefern `withBsid` und `externalLinkWarning` leer. */
  treffer(): TrefferUmgebung {
    const umgebung = this.basis.treffer();
    if (this.erlaubt.has('oeffnen')) return umgebung;
    return { ...umgebung, kontext: { ...(umgebung.kontext as object), ...OHNE_ADRESSEN } };
  }

  beschaeftigt(): boolean {
    return this.basis.beschaeftigt();
  }

  aktion(name: KartenAktion, parameter: { readonly nodeId: string; readonly title: string }): void;
  aktion(name: 'mehrLaden', parameter: { readonly blockId: string }): void;
  aktion(name: KartenAktion | 'mehrLaden', parameter: Record<string, string>): void {
    if (!this.darf('oeffnen')) return;
    if (name === 'mehrLaden') this.basis.aktion(name, { blockId: parameter['blockId'] });
    else this.basis.aktion(name, { nodeId: parameter['nodeId'], title: parameter['title'] });
  }

  zweig(nodeId: string): Promise<Record<string, unknown>> {
    if (!this.darf('nachladen')) {
      return Promise.reject(Object.assign(new Error('boerdi: Fähigkeit nachladen fehlt'), { status: 403 }));
    }
    return this.basis.zweig(nodeId);
  }

  /** U3-2c: wie `zweig` an eine Fähigkeit gebunden (`hochladen`); die Block-Kennung kennt nur der Host. */
  hochladen(datei: File, onFortschritt?: (anteil: number) => void): Promise<Record<string, unknown>> {
    if (!this.darf('hochladen')) {
      return Promise.reject(Object.assign(new Error('boerdi: Fähigkeit hochladen fehlt'), { status: 403, code: 'aus' }));
    }
    return this.basis.hochladen(this.blockId, datei, onFortschritt);
  }

  /** U3-3b: die Ablage gehört zur Fähigkeit `hochladen` — wie das Dokument geht sie ohne Zug. */
  ablegen(schritt: AblageSchritt): Promise<Record<string, unknown>> {
    if (!this.darf('hochladen')) {
      return Promise.reject(Object.assign(new Error('boerdi: Fähigkeit hochladen fehlt'), { status: 403, code: 'aus' }));
    }
    return this.basis.ablegen(this.blockId, schritt);
  }

  /** K1b: Stand und Abholen eines Ablauf-Auftrags an die Fähigkeit `auftrag` gebunden. */
  auftrag(schritt: AuftragSchritt): Promise<Record<string, unknown>> {
    if (!this.darf('auftrag')) {
      return Promise.reject(Object.assign(new Error('boerdi: Fähigkeit auftrag fehlt'), { status: 403, code: 'aus' }));
    }
    return this.basis.auftrag(schritt);
  }

  antworten(daten: Record<string, unknown>, text: string): void {
    if (this.darf('antworten')) this.basis.antwortSenden(this.blockId, daten, text);
  }

  /** U2: wie `antworten` an die Fähigkeit gebunden — eine Vormerkung ist eine Antwort auf Abruf. */
  vormerken(daten: Record<string, unknown> | null): void {
    if (this.darf('antworten')) this.basis.vormerken(this.blockId, daten);
  }
}
