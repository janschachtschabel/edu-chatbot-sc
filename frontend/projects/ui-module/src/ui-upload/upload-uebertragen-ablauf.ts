/**
 * Der Ablauf „In den persönlichen Bereich übertragen“ in `<boerdi-ui-upload>` (Paket U3-3b, T7) — wie
 * `upload-dokument-ablauf.ts` ohne Angular und ohne Ansicht: er hält den Zustand (`lauf`, je Datei ein
 * `Ergebnis`), ruft den Host (`host.ablegen`) und lässt das Element neu zeichnen und ansagen.
 *
 * Schritte: Dateien prüfen (sha256, k von n) → Freigabe vorbereiten → Vorschau mit „Jetzt übertragen“/
 * „Abbrechen“ → je Datei senden, **nacheinander** → Ergebnis. „Anhalten“ wirkt nach der laufenden Datei
 * (eine halb gesendete Datei abzubrechen ließe offen, ob sie angekommen ist). Ein Fehler des Stapels
 * (Anmeldung, Schalter, abgelaufene Freigabe, Netz) hält an, der einer Datei nicht. Danach legt der
 * Ablauf `vorgang.json` ab, sobald nichts mehr nachzusenden ist (sonst vor dem Weiter im Chat), und
 * merkt die Antwort `uebertragen` vor — nur Zahlen.
 */
import type { ElementHost } from '../_nachladen/element-vertrag';
import { einZeiler } from './upload-antwort';
import type { Erfassung } from './upload-erfassen';
import { fehlerSatz, type UebertragenTexte } from './upload-uebertragen-texte';
import {
  ansageFaellig,
  ablageErlaubt, auswahl, codeAblage, type Ergebnis, type LetzteAblagen, letzteAus, MAX_STAPEL, maxBytesAblage, nochmalSenden, type Plan, planAus, sha256Hex,
  stapelEnde, standAus, uebertragenAntwort, zaehlung,
} from './upload-uebertragen';

export type UebertragenLauf =
  | { readonly phase: 'pruefen'; readonly fertig: number; readonly gesamt: number }
  | { readonly phase: 'vorbereiten' }
  | { readonly phase: 'vorschau'; readonly plan: Plan }
  | {
    readonly phase: 'sendet'; readonly plan: Plan; readonly aktuell: number; readonly anteil: number;
    /** Stelle in DIESER Sendung (beim Nachsenden nicht der Index) und deren Länge. */
    readonly position: number; readonly anzahl: number;
  }
  | { readonly phase: 'fertig'; readonly plan: Plan; readonly halt?: string }
  | { readonly phase: 'fehler'; readonly code: string };

export interface UebertragenUmgebung {
  host(): ElementHost | undefined;
  erfassung(): Erfassung<File> | null;
  daten(): Readonly<Record<string, unknown>>;
  beschaeftigt(): boolean;
  t(): UebertragenTexte;
  wurzel(): ShadowRoot;
  ansagen(text: string): void;
  zeichne(): void;
  /** Für Tests; sonst `sha256Hex`. */
  hashen?(datei: File): Promise<string>;
  /** Der Block ist nicht mehr offen (ein Zug kam dazwischen): der Stapel läuft weiter, eine Antwort geht
   *  nicht mehr hin (Querschnitts-Review M1/M2). */
  nurLesen?(): boolean;
}

export class UebertragenAblauf {
  lauf: UebertragenLauf | null = null;
  ergebnisse: Ergebnis[] = [];
  /** Paket M6: die eigenen letzten Ablagen, die `vorbereiten` mitbringt. */
  letzte: LetzteAblagen = { ablagen: [], gekappt: false };
  /** Aufgeklappt? Das Element zeichnet alles neu — ohne diesen Merker klappte die Liste jedes Mal zu
   *  (Review M6, Befund 4). */
  letzteOffen = false;
  ordnerVerweigert = false;
  vorgang: 'offen' | 'abgelegt' | 'fehlt' = 'offen';
  anhalten = false;
  /** „Im Chat weitermachen“ wartet auf den Abschluss (Review U3-3b, Befund 4). */
  weiterLaeuft = false;
  private dateien: File[] = [];
  /** Zählt jeden Neubeginn; ein Lauf, der nach einem `await` eine andere Nummer sieht, ist überholt
   *  (neue Auswahl, Zurücksetzen — Review U3-3b, Befund 3). */
  private nummer = 0;
  private getrennt = false;

  constructor(private readonly u: UebertragenUmgebung) {}

  laeuft(): boolean {
    const p = this.lauf?.phase;
    return p === 'pruefen' || p === 'vorbereiten' || p === 'sendet';
  }

  /** Solange es eine Vorschau oder ein Ergebnis gibt, bleibt die Auswahl fest (Rollen, Ignorieren). */
  haeltAuswahl(): boolean {
    return !!this.lauf && this.lauf.phase !== 'fehler';
  }

  zuruecksetzen(): void {
    this.nummer++;
    this.lauf = null;
    this.ergebnisse = [];
    this.letzte = { ablagen: [], gekappt: false };
    this.letzteOffen = false;
    this.dateien = [];
    this.ordnerVerweigert = false;
    this.vorgang = 'offen';
    this.anhalten = false;
    this.weiterLaeuft = false;
  }

  /** Das Element hängt nicht mehr im Dokument (Widget geschlossen): nach der laufenden Datei anhalten,
   *  ein Prüfen bricht ab (Review U3-3b, Befund 2). */
  trennen(): void {
    this.getrennt = true;
    this.anhalten = true;
  }

  verbinden(): void {
    this.getrennt = false;
  }

  /** Prüfen und die Freigabe vorbereiten; endet in der Vorschau oder mit einem Fehler. */
  async vorbereiten(): Promise<void> {
    const e = this.u.erfassung();
    const host = this.u.host();
    if (!e || !host || this.laeuft() || !ablageErlaubt(this.u.daten())) return;
    const { kandidaten } = auswahl(e, maxBytesAblage(this.u.daten()));
    if (!kandidaten.length || kandidaten.length > MAX_STAPEL) return;
    const t = this.u.t();
    this.zuruecksetzen();
    const nr = this.nummer;
    const ueberholt = () => nr !== this.nummer || this.u.erfassung() !== e || this.getrennt;
    this.lauf = { phase: 'pruefen', fertig: 0, gesamt: kandidaten.length };
    this.u.ansagen(t.prueft(0, kandidaten.length));
    this.u.zeichne();
    try {
      const eintraege = [];
      for (const [i, k] of kandidaten.entries()) {
        const sha256 = await (this.u.hashen ?? ((d: File) => sha256Hex(d)))(k.handle);
        if (ueberholt()) return this.verwerfen(nr);
        eintraege.push({ titel: k.titel, sha256, groesse: k.groesse, art: k.art });
        this.lauf = { phase: 'pruefen', fertig: i + 1, gesamt: kandidaten.length };
        this.anOrt(t.prueft(i + 1, kandidaten.length), (i + 1) / kandidaten.length);
      }
      this.lauf = { phase: 'vorbereiten' };
      this.u.ansagen(t.bereitet);
      this.u.zeichne();
      // Das Backend nimmt höchstens 120 Zeichen in einer Zeile (Review U3-3b, Befund 8).
      const ordner = einZeiler(e.wurzel.name) || t.auswahl;
      const roh = await host.ablegen({ schritt: 'vorbereiten', ordner, eintraege });
      if (ueberholt()) return this.verwerfen(nr);
      const plan = planAus(roh, eintraege.length);
      if (!plan) throw Object.assign(new Error('Plan unbrauchbar'), { code: 'fehler' });
      this.dateien = kandidaten.map((k) => k.handle);
      this.ergebnisse = plan.eintraege.map(() => ({ stand: 'wartet' }));
      this.letzte = letzteAus(roh);
      this.lauf = { phase: 'vorschau', plan };
      this.u.ansagen(plan.layout === 'ordner' ? t.zielOrdner(plan.ordner) : t.zielFlach);
    } catch (fehler) {
      if (ueberholt()) return this.verwerfen(nr);
      const code = codeAblage(fehler);
      this.lauf = { phase: 'fehler', code };
      this.u.ansagen(fehlerSatz(t, code));
    }
    this.u.zeichne();
  }

  /** In der Vorschau: nichts wird gesendet; die Freigabe verfällt im MCP von selbst. */
  abbrechen(): void {
    if (this.lauf?.phase !== 'vorschau') return;
    this.zuruecksetzen();
    this.u.zeichne();
  }

  /** Nach der laufenden Datei anhalten. */
  anhaltenNachDieser(): void {
    if (this.lauf?.phase !== 'sendet') return;
    this.anhalten = true;
    this.u.ansagen(this.u.t().haeltAn);
    this.u.zeichne();
  }

  /** Aus der Vorschau alle Dateien senden — oder nach dem Ergebnis die, die noch einmal gehen können. */
  async senden(): Promise<void> {
    const host = this.u.host();
    const lauf = this.lauf;
    if (!host || (lauf?.phase !== 'vorschau' && lauf?.phase !== 'fertig')) return;
    const plan = lauf.plan;
    const liste = lauf.phase === 'vorschau' ? plan.eintraege.map((x) => x.index) : nochmalSenden(this.ergebnisse);
    if (!liste.length) return;
    const t = this.u.t();
    const nr = this.nummer;
    this.anhalten = false;
    let halt: string | undefined;
    for (const [n, i] of liste.entries()) {
      if (this.anhalten || halt) {
        for (const rest of liste.slice(n)) this.ergebnisse[rest] = { stand: 'abgebrochen' };
        break;
      }
      this.ergebnisse[i] = { stand: 'sendet' };
      this.lauf = { phase: 'sendet', plan, aktuell: i, anteil: 0, position: n + 1, anzahl: liste.length };
      if (ansageFaellig(n + 1, liste.length)) this.u.ansagen(t.sendet(n + 1, liste.length, 0));
      this.u.zeichne();
      let ergebnis: Ergebnis;
      try {
        const roh = await host.ablegen({
          schritt: 'datei', batchToken: plan.token, index: i, datei: this.dateien[i],
          onFortschritt: (anteil) => this.fortschritt(i, anteil),
        });
        ergebnis = standAus(roh) ?? { stand: 'unverified' };
        if (roh['ordner_verweigert'] === true) this.ordnerVerweigert = true;
      } catch (fehler) {
        const code = codeAblage(fehler);
        // Ohne Antwort (Frist, MCP weg) KANN die Datei abgelegt sein — wie das Backend: „unklar“.
        const stand = code === 'zu_langsam' || code === 'nicht_erreichbar' ? 'unverified'
          : code === 'abgebrochen' ? 'abgebrochen' : 'failed';
        ergebnis = { stand, code };
        if (stapelEnde(code)) halt = code;
      }
      if (nr !== this.nummer) return;          // inzwischen neu gewählt oder zurückgesetzt
      this.ergebnisse[i] = ergebnis;
    }
    this.lauf = { phase: 'fertig', plan, ...(halt ? { halt } : {}) };
    // Ohne Antwortknopf („nur lesen“) schlösse sonst niemand den Stapel ab — ein offener Stapel sperrt
    // ein neues Vorbereiten bis zu 30 Minuten (Review Q1, Befund 4).
    if (!halt && (!nochmalSenden(this.ergebnisse).length || this.u.nurLesen?.())) await this.abschliessen();
    if (nr !== this.nummer) return;
    this.vormerken();
    const z = zaehlung(this.ergebnisse);
    this.u.ansagen(halt ? fehlerSatz(t, halt) : t.fertig(z.abgelegt, this.ergebnisse.length));
    this.u.zeichne();
  }

  /** „Im Chat weitermachen“: zuerst `vorgang.json` (falls noch offen), dann die Antwort mit den Zahlen. */
  async weiter(): Promise<void> {
    if (this.lauf?.phase !== 'fertig' || this.u.beschaeftigt() || this.weiterLaeuft || this.u.nurLesen?.()) return;
    const plan = this.lauf.plan;
    const nr = this.nummer;
    if (this.vorgang === 'offen' && !this.lauf.halt) {
      this.weiterLaeuft = true;
      this.u.zeichne();
      try {
        await this.abschliessen();
      } finally {
        this.weiterLaeuft = false;
      }
      if (nr !== this.nummer) return;
      this.u.zeichne();
    }
    const e = this.u.erfassung();
    if (!e) return;
    const z = zaehlung(this.ergebnisse);
    const antwort = uebertragenAntwort(e, plan, this.ergebnisse, this.optionen());
    this.u.host()?.antworten(antwort as unknown as Record<string, unknown>, this.u.t().blase(z.abgelegt, this.ergebnisse.length));
  }

  private async abschliessen(): Promise<void> {
    const host = this.u.host();
    if (this.lauf?.phase !== 'fertig' || !host || this.vorgang === 'abgelegt') return;
    if (!zaehlung(this.ergebnisse).abgelegt) return;
    try {
      const roh = await host.ablegen({ schritt: 'abschluss', batchToken: this.lauf.plan.token });
      this.vorgang = roh['stand'] === 'stored' ? 'abgelegt' : 'fehlt';
    } catch {
      this.vorgang = 'fehlt';
    }
  }

  private optionen() {
    return { ordnerVerweigert: this.ordnerVerweigert, vorgangAbgelegt: this.vorgang === 'abgelegt' };
  }

  /** Die Zahlen gehen auch mit einer GETIPPTEN Nachricht mit (wie der Befund des Erfassens). */
  private vormerken(): void {
    const e = this.u.erfassung();
    if (this.lauf?.phase !== 'fertig' || !e || this.u.nurLesen?.()) return;
    const antwort = uebertragenAntwort(e, this.lauf.plan, this.ergebnisse, this.optionen());
    this.u.host()?.vormerken(antwort as unknown as Record<string, unknown>);
  }

  private fortschritt(i: number, anteil: number): void {
    const lauf = this.lauf;
    if (lauf?.phase !== 'sendet' || lauf.aktuell !== i) return;
    this.lauf = { ...lauf, anteil };
    this.anOrt(this.u.t().sendet(lauf.position, lauf.anzahl, Math.round(anteil * 100)), anteil);
  }

  /** Ein Fortschrittsschritt nur an Ort und Stelle — Balken und Satz, ohne neu zu zeichnen. */
  private anOrt(satz: string, anteil: number): void {
    const balken = this.u.wurzel().querySelector<HTMLProgressElement>('progress[data-ablage-balken]');
    const zeile = this.u.wurzel().querySelector<HTMLElement>('[data-fokus="s:ablage"]');
    if (balken) {
      balken.value = Math.round(anteil * 100);
      balken.setAttribute('aria-label', satz);
    }
    if (zeile) zeile.textContent = satz;
  }

  /** Ein überholter Lauf: nur zurücksetzen, wenn kein neuerer begonnen hat. */
  private verwerfen(nr: number): void {
    if (nr !== this.nummer) return;
    this.zuruecksetzen();
    this.u.zeichne();
  }
}
