/**
 * Was ein Modul vom Widget bekommt — per Angular-DI statt Zugangsdaten oder DOM-Ereignissen.
 *
 * Module rufen nichts selbst im Netz auf und kennen keine Anmeldung (Plan U1, U-E7). Was nach
 * außen wirkt, geht über diesen Dienst, den die Chat-Shell bereitstellt. Er wächst mit den
 * Modulen, die ihn brauchen: Drucken kommt mit dem Inhaltsrahmen (U1-b), Antworten mit der
 * Entscheidung (U1-d).
 *
 * Seit U1-d1 hat jeder Block seinen eigenen Host: Er kennt die Block-Kennung und lässt nur die
 * Fähigkeiten aus dem Manifest (`faehigkeiten`) zu — `herunterladen`, `drucken`, `oeffnen`
 * (`link`, `aktion`), `antworten`, `nachladen` (`zweig`, U1-h). Fehlt eine, passiert nichts außer
 * einer Warnung in der Konsole (`zweig` lehnt ab). `markdown`, `treffer` und `beschaeftigt` sind
 * Darstellung und immer erlaubt.
 */
import { InjectionToken } from '@angular/core';
import type { SafeHtml } from '@angular/platform-browser';

export interface ModulHost {
  /** Bietet Text als Datei zum Speichern an (z. B. Markdown des Inhaltsrahmens). */
  herunterladen(dateiname: string, mime: string, inhalt: string): void;
  /** Öffnet die Druckansicht; daraus lässt sich auch ein PDF speichern. */
  drucken(titel: string, markdown: string): void;
  /** Markdown als bereinigtes HTML — derselbe Renderer wie für die Antworten des Bots. */
  markdown(text: string): SafeHtml;
  /** Ein Link, wie das Widget ihn setzt: `href` mit Sitzungs-Kennung bei vertrauten Seiten,
   *  `hinweis` (leer oder Warnung) bei fremden. Module bauen keine Link-Adressen selbst. */
  link(url: string): { readonly href: string; readonly hinweis: string };
  /** Umgebung der Trefferdarstellung (U1-c2): der Link- und Such-Kontext der Shell (für die
   *  Trefferboxen; Typ bewusst offen, damit der Vertrag nicht an der Shell hängt), ob gerade
   *  Kacheln statt Boxen gezeigt werden und ob ein Zug läuft. */
  treffer(): TrefferUmgebung;
  /** Eine Aktion der Shell auslösen (U1-c2): `volltext` (M17), `sammlung` (Sammlung öffnen) und
   *  `lernpfad` mit `{ nodeId, title }`; `mehrLaden` mit `{ blockId }` — die Shell lädt die nächste
   *  Seite und schreibt die neuen Karten in den Block, das Modul bekommt sie als neue Daten.
   *  `alsEntwurf` (U2) öffnet eine Sammlung als Strukturentwurf.
   *  (`themenbaum` — Unterthemen als neue Antwort, U1-e — ist seit U1-h `zweig`.) */
  aktion(name: KartenAktion, parameter: { readonly nodeId: string; readonly title: string }): void;
  aktion(name: 'mehrLaden', parameter: { readonly blockId: string }): void;
  /** Läuft gerade ein Zug? Dann darf ein abfragendes Modul nichts senden (Knopf gesperrt). */
  beschaeftigt(): boolean;
  /** Die Antwort der Person auf diesen Block (U1-d1): `daten` nach `manifest.antwort`, `text` die
   *  lesbare Fassung — sie wird die Nutzerblase. Die Shell sendet beides als nächsten Zug
   *  (`ui_antwort`) und setzt den Block danach auf `beantwortet`. */
  antworten(daten: Record<string, unknown>, text: string): void;
  /** Eine Antwort vormerken, die mit der nächsten GETIPPTEN Nachricht der Person mitgeht (U2,
   *  Fähigkeit `antworten`): solange der Block offen ist, hängt die Shell `daten` als `ui_antwort`
   *  an einen Zug aus Eingabefeld oder Schnellantwort und setzt den Block `beantwortet` statt
   *  `veraltet` — so geht der bearbeitete Strukturentwurf nie verloren. `null` nimmt die
   *  Vormerkung zurück. Karten- und Direktaktionen nehmen nichts mit. */
  vormerken(daten: Record<string, unknown> | null): void;
  /** Die Unterthemen eines Knotens im Themenbaum nachladen (U1-h, Fähigkeit `nachladen`): ohne
   *  Zug und ohne KI, nichts wird gespeichert. Löst mit Daten in der Form der Block-Daten von
   *  `ui_themenbaum` auf (`knoten`, `gekuerzt?`, `wurzel_mehr?`, …; ohne Überschrift); lehnt ab
   *  mit einem Fehler, dessen `status` (HTTP) sagt, ob ein neuer Versuch hilft (403: nein). */
  zweig(nodeId: string): Promise<Record<string, unknown>>;
}

/** `alsEntwurf` (U2): die Sammlung `nodeId` als bearbeitbaren Strukturentwurf öffnen (Brücke im
 *  Themenbaum, Direktaktion `edit_collection_as_draft`). */
export type KartenAktion = 'volltext' | 'sammlung' | 'lernpfad' | 'alsEntwurf';

export interface TrefferUmgebung {
  readonly kontext: unknown;
  readonly kacheln: boolean;
  readonly beschaeftigt: boolean;
}

export const MODUL_HOST = new InjectionToken<ModulHost>('MODUL_HOST');
