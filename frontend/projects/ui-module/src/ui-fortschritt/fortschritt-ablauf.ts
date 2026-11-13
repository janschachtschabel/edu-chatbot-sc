/**
 * Das Nachfragen von `ui_fortschritt` (Paket K1b) — ohne DOM, damit es sich mit falscher Uhr prüfen
 * lässt.
 *
 * - Fragt den Stand über den Host (`auftrag({ schritt: 'stand' })`, kein Zug) erst nach
 *   `ABSTAENDE_MS[0]`, dann in wachsenden Abständen; nie zwei Fragen zugleich.
 * - Während die Seite verborgen ist, fragt es nicht — sobald sie sichtbar wird, sofort.
 * - Nach `AUTOMATISCH_MS` nur noch per Knopf („manuell“): ein vergessener Tab fragt nicht ewig.
 * - `fertig`/`fehler` → einmal abholen (`auftrag({ schritt: 'abholen' })`, ein Zug der Person); läuft
 *   gerade ein Zug, wartet es auf `frei()`. Nicht gesendet → „Ergebnis abholen“ wird angeboten. Nach dem
 *   Warten wie vor „Ergebnis abholen“ wird **erst neu gefragt** (`nachpruefen`, Review K1b, Befund 1): der
 *   Zug dazwischen kann den Auftrag schon abgeholt haben (Knopf „Stand prüfen“, zweiter Tab) — dann
 *   antwortet das Backend 409 statt eines zweiten Abholens.
 * - Fehler nach Status (403 mit `code` `abgewiesen` → eigener Halt, R1-e): 409/404/400/422 → abgeschlossen (kein wartender Auftrag mehr — etwa ein alter
 *   Block im Verlauf); 401/403 → Halt; AbortError → still Schluss; alles andere → Störung, weiter.
 * - `trennen()` (Element entfernt) beendet alles; eine späte Antwort ändert nichts (Lauf-Nummer).
 * - `abbrechen()` (K2b) schickt „Auftrag abbrechen“ als Zug; das Backend fragt erst nach. Das Nachfragen
 *   läuft weiter: nach dem bestätigten Abbruch antwortet `stand` mit 409 → abgeschlossen.
 */
import type { ElementHost } from '../_nachladen/element-vertrag';

export const ABSTAENDE_MS: readonly number[] = [5_000, 10_000, 20_000, 30_000, 60_000];
export const AUTOMATISCH_MS = 30 * 60_000;

export type Phase = 'wartet' | 'prueft' | 'fertig' | 'abgeholt' | 'abgeschlossen' | 'halt' | 'abgewiesen' | 'manuell';

export interface FortschrittDaten {
  readonly ablauf: string;
  readonly kuerzel: string;
  readonly text: string;
}

export interface FortschrittUmgebung {
  host(): Pick<ElementHost, 'auftrag'>;
  /** Die geprüften Block-Daten, `null` wenn sie nicht passen. */
  daten(): FortschrittDaten | null;
  beschaeftigt(): boolean;
  sichtbar(): boolean;
  zeichne(): void;
}

const ENDGUELTIG = new Set([400, 404, 409, 422]);

/** Die Block-Daten, wenn sie die Form des Manifests haben (das Backend prüft sie auch). */
export function fortschrittDaten(roh: Record<string, unknown>): FortschrittDaten | null {
  const { ablauf, kuerzel, text } = roh;
  if (typeof ablauf !== 'string' || !/^[a-z][a-z0-9_]{0,39}$/.test(ablauf)) return null;
  if (typeof kuerzel !== 'string' || !/^[0-9a-f]{12}$/.test(kuerzel)) return null;
  return { ablauf, kuerzel, text: typeof text === 'string' ? text : '' };
}

export class FortschrittAblauf {
  phase: Phase = 'wartet';
  ergebnis: 'fertig' | 'fehler' | null = null;
  /** Zeitpunkt der letzten beantworteten Frage (ms seit 1970). */
  zuletzt: number | null = null;
  /** Die letzte Frage kam nicht an (b-api, Netz) — es wird weiter versucht. */
  stoerung = false;

  private versuch = 0;
  private start = 0;
  private uhr: ReturnType<typeof setTimeout> | null = null;
  private nummer = 0;
  private verbunden = false;
  private aufSichtbar = false;
  private holt = false;
  private nichtGesendet = false;
  /** Die Phase vor einer laufenden Frage — für `trennen` mitten in der Frage (Befund 8). */
  private vorFrage: Phase = 'wartet';

  constructor(private readonly u: FortschrittUmgebung) {}

  verbinden(): void {
    if (this.verbunden) return;
    this.verbunden = true;
    if (!this.u.daten()) {
      this.phase = 'abgeschlossen';
      this.u.zeichne();
      return;
    }
    this.start = Date.now();
    this.plane();
  }

  trennen(): void {
    this.verbunden = false;
    this.nummer++;
    this.loesche();
    // Review K1b, Befund 8: eine verworfene Antwort darf den Stand nicht festhalten — sonst fragte
    // dasselbe Element nach dem Wiedereinhängen nie mehr.
    if (this.phase === 'prueft') this.phase = this.vorFrage;
    this.holt = false;
  }

  /** Abholen anbieten? (fertig, aber nicht gesendet und gerade kein Versuch) */
  abholenAngeboten(): boolean {
    return this.phase === 'fertig' && this.nichtGesendet && !this.holt;
  }

  /** „Jetzt prüfen“ und der fällige Zeitgeber. */
  async pruefen(): Promise<void> {
    const daten = this.u.daten();
    if (!this.verbunden || !daten || (this.phase !== 'wartet' && this.phase !== 'manuell')) return;
    this.loesche();
    const nr = this.nummer;
    const vorher = this.phase;
    this.vorFrage = vorher;
    this.phase = 'prueft';
    this.u.zeichne();
    let antwort: Record<string, unknown>;
    try {
      antwort = await this.u.host().auftrag({ schritt: 'stand', ablauf: daten.ablauf, kuerzel: daten.kuerzel });
    } catch (fehler) {
      if (nr === this.nummer) this.fehlgeschlagen(fehler, vorher);
      return;
    }
    if (nr !== this.nummer) return;
    this.zuletzt = Date.now();
    this.stoerung = false;
    this.versuch++;
    const stand = antwort['stand'];
    if (stand === 'fertig' || stand === 'fehler') {
      this.ergebnis = stand;
      this.phase = 'fertig';
      this.u.zeichne();
      await this.abholen();
      return;
    }
    this.weiterWarten(vorher);
  }

  /** Die Shell ist wieder frei (kein Zug): wartet ein fertiger Auftrag aufs Abholen, erst neu fragen. */
  frei(): void {
    if (this.phase === 'fertig' && !this.holt && !this.nichtGesendet) void this.nachpruefen();
  }

  /** Vor einem späteren Abholen („frei“, „Ergebnis abholen“) den Stand neu fragen (Befund 1). */
  async nachpruefen(): Promise<void> {
    if (this.phase !== 'fertig' || this.holt) return;
    this.phase = 'wartet';
    this.nichtGesendet = false;
    await this.pruefen();
  }

  /** K2b: solange der Auftrag läuft (nicht fertig, nicht beendet) und die Seite verbunden ist. */
  abbrechenAngeboten(): boolean {
    return this.verbunden && (this.phase === 'wartet' || this.phase === 'prueft' || this.phase === 'manuell');
  }

  /** K2b: „Auftrag abbrechen“ — `true`, wenn der Zug ging (die Shell war frei). */
  async abbrechen(): Promise<boolean> {
    const daten = this.u.daten();
    if (!daten || !this.abbrechenAngeboten() || this.u.beschaeftigt()) return false;
    try {
      return (await this.u.host().auftrag({ schritt: 'abbrechen', ablauf: daten.ablauf }))['gesendet'] === true;
    } catch {
      return false;
    }
  }

  sichtbarGeworden(): void {
    if (!this.aufSichtbar) return;
    this.aufSichtbar = false;
    void this.pruefen();
  }

  async abholen(): Promise<void> {
    const daten = this.u.daten();
    if (!this.verbunden || !daten || this.phase !== 'fertig' || this.holt || this.u.beschaeftigt()) return;
    const nr = this.nummer;
    this.holt = true;
    this.nichtGesendet = false;
    this.u.zeichne();
    let gesendet = false;
    try {
      gesendet = (await this.u.host().auftrag({ schritt: 'abholen', ablauf: daten.ablauf }))['gesendet'] === true;
    } catch {
      gesendet = false;
    }
    if (nr !== this.nummer) return;
    this.holt = false;
    if (gesendet) this.phase = 'abgeholt';
    else this.nichtGesendet = true;
    this.u.zeichne();
  }

  private fehlgeschlagen(fehler: unknown, vorher: Phase): void {
    if ((fehler as { name?: unknown } | null)?.name === 'AbortError') {
      this.phase = vorher;
      return;
    }
    const status = (fehler as { status?: unknown } | null)?.status;
    if (typeof status === 'number' && ENDGUELTIG.has(status)) {
      this.phase = 'abgeschlossen';
    } else if (status === 403 && (fehler as { code?: unknown }).code === 'abgewiesen') {
      // R1-e: die B-API weist den Schlüssel ab — „nur angemeldet“ wäre hier falsch
      this.phase = 'abgewiesen';
    } else if (status === 401 || status === 403) {
      this.phase = 'halt';
    } else {
      this.stoerung = true;
      this.versuch++;
      this.weiterWarten(vorher);
      return;
    }
    this.u.zeichne();
  }

  private weiterWarten(vorher: Phase): void {
    this.phase = vorher === 'manuell' || Date.now() - this.start >= AUTOMATISCH_MS ? 'manuell' : 'wartet';
    this.plane();
    this.u.zeichne();
  }

  private plane(): void {
    if (!this.verbunden || this.phase !== 'wartet') return;
    const abstand = ABSTAENDE_MS[Math.min(this.versuch, ABSTAENDE_MS.length - 1)];
    if (Date.now() + abstand - this.start > AUTOMATISCH_MS) {
      this.phase = 'manuell';
      this.u.zeichne();
      return;
    }
    this.uhr = setTimeout(() => this.faellig(), abstand);
  }

  private faellig(): void {
    this.uhr = null;
    if (!this.u.sichtbar()) {
      this.aufSichtbar = true;
      return;
    }
    void this.pruefen();
  }

  private loesche(): void {
    if (this.uhr !== null) clearTimeout(this.uhr);
    this.uhr = null;
    this.aufSichtbar = false;
  }
}
