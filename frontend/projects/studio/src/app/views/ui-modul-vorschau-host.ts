/**
 * Der Modul-Host der Studio-Vorschau (Paket U1-f, Plan §16 F-7).
 *
 * Module wirken nach außen nur über ihren Host (`MODUL_HOST`, Plan U-E7). Hier tut keine Methode
 * etwas außerhalb der Seite: Herunterladen, Drucken, Aktionen und Antworten werden über `melde`
 * angesagt. Links bekommen ihre echte Adresse (zum Ansehen); das Öffnen fängt die Vorschau-
 * Komponente beim Klick ab. Darstellung (`markdown`, `treffer`) läuft wie im Widget. Nachladen im
 * Themenbaum (U1-h, `zweig`) ruft kein Backend: angesagt, mit zwei Beispiel-Unterthemen.
 */
import type { SafeHtml } from '@angular/platform-browser';

import type { KartenAktion, ModulHost, TrefferUmgebung } from '@boerdi/ui-module';

/** Was die Vorschau ansagt: Katalog-Schlüssel und Werte. */
export type Melden = (key: string, params: Readonly<Record<string, string>>) => void;

export class VorschauModulHost implements ModulHost {
  constructor(
    private readonly melde: Melden,
    private readonly render: (text: string) => SafeHtml,
    private readonly umgebung: () => TrefferUmgebung,
  ) {}

  herunterladen(dateiname: string): void {
    this.melde('uiModule.vorschau.herunterladen', { datei: dateiname });
  }

  drucken(titel: string): void {
    this.melde('uiModule.vorschau.drucken', { titel });
  }

  markdown(text: string): SafeHtml {
    return this.render(text);
  }

  link(url: string): { readonly href: string; readonly hinweis: string } {
    return { href: url, hinweis: '' };
  }

  treffer(): TrefferUmgebung {
    return this.umgebung();
  }

  aktion(name: KartenAktion, parameter: { readonly nodeId: string; readonly title: string }): void;
  aktion(name: 'mehrLaden', parameter: { readonly blockId: string }): void;
  aktion(name: KartenAktion | 'mehrLaden'): void {
    this.melde('uiModule.vorschau.aktion', { aktion: name });
  }

  beschaeftigt(): boolean {
    return false;
  }

  zweig(nodeId: string): Promise<Record<string, unknown>> {
    this.melde('uiModule.vorschau.zweig', { knoten: nodeId });
    return Promise.resolve({
      knoten: [1, 2].map((n) => ({ id: `vorschau-${nodeId}-${n}`.slice(0, 80), titel: `Beispiel-Unterthema ${n}` })),
    });
  }

  antworten(_daten: Record<string, unknown>, text: string): void {
    this.melde('uiModule.vorschau.antworten', { text });
  }

  /** U2: die Vormerkung des Strukturentwurfs ändert sich bei jeder Bearbeitung — keine Ansage. */
  vormerken(): void {
    // In der Vorschau gibt es keine nächste Nachricht.
  }
}
