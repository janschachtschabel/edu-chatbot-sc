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
 * (`link`, `aktion`), `antworten`, `nachladen` (`zweig`, U1-h), `hochladen` (U3-2c; seit U3-3b auch
 * `ablegen`), `auftrag` (K1b). Fehlt eine,
 * passiert nichts außer einer Warnung in der Konsole (`zweig` und `hochladen` lehnen ab). `markdown`, `treffer` und `beschaeftigt` sind
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
  /** Ein Dokument lesen lassen (U3-2c, Fähigkeit `hochladen`): ohne Zug und ohne KI liest das Backend
   *  es, legt den Text an der Sitzung ab und löst mit dem Befund auf (`upload_id`, `name`, `format`,
   *  `befund`, `ueberschriften_vorschau` — nie der Text). `onFortschritt` meldet den gesendeten Anteil
   *  (0…1). Lehnt ab mit `status` und `code` (`bild`, `zu_gross`, `kein_text`, `nur_angemeldet` …). */
  hochladen(datei: File, onFortschritt?: (anteil: number) => void): Promise<Record<string, unknown>>;
  /** Ein Schritt der Ablage im persönlichen Bereich in WLO (U3-3b, Fähigkeit `hochladen`): ohne Zug
   *  und ohne KI, nur mit bestätigter Anmeldung (`/api/ui/ablage/*`). Löst mit der Antwort des Backends
   *  auf (Vorschau, Stand einer Datei, Abschluss); lehnt ab mit `status` und `code` (`nur_angemeldet`,
   *  `aus`, `kein_recht`, `neu_vorbereiten` …). Die Dateien gehen nacheinander, eine zur Zeit. */
  ablegen(schritt: AblageSchritt): Promise<Record<string, unknown>>;
  /** Ein Auftrag eines Ablaufs (K1b, Fähigkeit `auftrag`): `stand` fragt ohne Zug nach (löst mit
   *  `{ stand: 'laeuft' | 'fertig' | 'fehler' }` auf, lehnt ab mit `status` — 409: kein wartender
   *  Auftrag mehr, 403: nicht angemeldet, 503: gerade nicht abrufbar); `abholen` lässt die Shell das
   *  Ergebnis im Zug der Person holen (Direktaktion „Stand prüfen“) und löst mit `{ gesendet }` auf —
   *  `false`, solange ein anderer Zug läuft. `abbrechen` (K2b) schickt die Direktaktion „Auftrag
   *  abbrechen“; das Backend fragt erst nach, gleiche Auflösung wie `abholen`. */
  auftrag(schritt: AuftragSchritt): Promise<Record<string, unknown>>;
}

/** K1b: Ablauf und Kürzel des Auftrags stehen in den Block-Daten von `ui_fortschritt` (nie die Job-ID). */
export type AuftragSchritt =
  | { readonly schritt: 'stand'; readonly ablauf: string; readonly kuerzel: string }
  | { readonly schritt: 'abholen'; readonly ablauf: string }
  | { readonly schritt: 'abbrechen'; readonly ablauf: string };

/** U3-3b: ein Eintrag der Freigabe — nur, was das MCP dafür braucht (keine Pfade, kein Inhalt). */
export interface AblageEintrag {
  readonly titel: string;
  readonly sha256: string;
  readonly groesse: number;
  readonly art: string;
  /** W4 (MCP-Stand 2026-11-08): Strukturdokument oder Inhalt — Teil der Freigabe; Vorgabe `inhalt`. */
  readonly rolle?: AblageRolle;
}

export type AblageRolle = 'inhalt' | 'struktur';

/** U3-3b: die drei Schritte der Ablage — Freigabe vorbereiten, eine Datei, Abschluss (`vorgang.json`). */
export type AblageSchritt =
  | { readonly schritt: 'vorbereiten'; readonly ordner: string; readonly eintraege: readonly AblageEintrag[] }
  | {
    readonly schritt: 'datei'; readonly batchToken: string; readonly index: number; readonly datei: File;
    readonly onFortschritt?: (anteil: number) => void;
  }
  | { readonly schritt: 'abschluss'; readonly batchToken: string };

/** `alsEntwurf` (U2): die Sammlung `nodeId` als bearbeitbaren Strukturentwurf öffnen (Brücke im
 *  Themenbaum, Direktaktion `edit_collection_as_draft`). */
export type KartenAktion = 'volltext' | 'sammlung' | 'lernpfad' | 'alsEntwurf';

export interface TrefferUmgebung {
  readonly kontext: unknown;
  readonly kacheln: boolean;
  readonly beschaeftigt: boolean;
}

export const MODUL_HOST = new InjectionToken<ModulHost>('MODUL_HOST');
