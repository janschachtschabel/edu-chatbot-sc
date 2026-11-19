/**
 * Der Ablauf „Hier im Chat“ in `<boerdi-ui-upload>` (Plan 2026-11-17, Paket U4) — löst „Lesen lassen“
 * (U3-2c, TG-3e) ab und arbeitet wie dieser ohne Angular und ohne Ansicht: er hält den Zustand
 * (`lauf`), lädt über den Host hoch, meldet den Fortschritt an Ort und Stelle und antwortet; neu
 * zeichnen und ansagen lässt er das Element.
 *
 * Jede lesbare Datei der Auswahl (Inhalt oder Strukturdokument) geht **nacheinander** mit eigenem
 * `POST /api/ui/dokumente` und ihrer Rolle hoch („Datei k von n“). Scheitert eine, hält der Ablauf an:
 * „Noch einmal versuchen“ lädt sie erneut, „Ohne diese weiter“ macht mit der nächsten weiter — die
 * schon gelesenen bleiben (das Backend hält sie an der Sitzung). Geantwortet wird einmal, mit allen
 * gelesenen (`bereitgestellt`, Ort chat); läuft gerade ein Zug, wartet die Antwort auf „Weiter“ und
 * geht vorgemerkt mit einer getippten Nachricht mit.
 *
 * Review der Oberfläche (2026-11-19): `grenze_anzahl` beendet den Lauf (jede weitere Datei scheiterte
 * ebenso), „Nach dieser Datei anhalten“ und ein entferntes Element (`trennen`) halten nach der
 * laufenden Datei an — danach antwortet „Mit den gelesenen weiter“. Dieselbe Datei in derselben Rolle
 * (`dublettenSchluessel`) geht einmal hoch und teilt die `upload_id`. Angesagt wird wie beim Übertragen
 * nur die erste, jede zehnte und die letzte Datei, dazu die erste nach einem Weitermachen (FE-5).
 * Zweites Review: 403 `ort_nicht_erlaubt` endet wie `grenze_anzahl`.
 */
import type { ElementHost } from '../_nachladen/element-vertrag';
import { chatAntwort, type ChatLauf, type ChatStelle, codeVon, type GeleseneDatei, gelesenAus } from './upload-chat';
import type { Erfassung } from './upload-erfassen';
import { dublettenSchluessel as schluessel, type LokaleDatei } from './upload-orte';
import { chatFehlerSatz, type UploadTexte } from './upload-texte';
import { ansageFaellig } from './upload-uebertragen';

export interface ChatUmgebung {
  host(): ElementHost | undefined;
  erfassung(): Erfassung<File> | null;
  /** Die lesbaren Dateien der Auswahl (`lokaleAuswahl`), in ihrer Reihenfolge. */
  dateien(): readonly LokaleDatei<File>[];
  beschaeftigt(): boolean;
  t(): UploadTexte;
  wurzel(): ShadowRoot;
  ansagen(text: string): void;
  zeichne(): void;
  /** Der Block ist nicht mehr offen — dann geht keine Antwort mehr hin. */
  nurLesen?(): boolean;
}

type Ende = Extract<ChatLauf, { readonly phase: 'fehler' | 'halt' }>;
/** Codes, nach denen jede weitere Datei ebenso scheiterte — der Lauf endet (`halt`). */
const ENDET = new Set(['grenze_anzahl', 'ort_nicht_erlaubt']);

export function sendetSatz(t: UploadTexte, prozent: number, s: ChatStelle): string {
  return t.sendetDatei(s.nr, s.von, prozent);
}

export function fehlerSatz(t: UploadTexte, code: string, s: ChatStelle): string {
  return t.fehlerBei(s.name, chatFehlerSatz(t, code));
}

export class ChatAblauf {
  lauf: ChatLauf | null = null;
  /** „Nach dieser Datei anhalten“ — oder das Element hängt nicht mehr im Dokument. */
  anhalten = false;
  private getrennt = false;
  /** Wird die laufende Datei angesagt (Hochladen und Lesen)? */
  private ansage = false;

  constructor(private readonly u: ChatUmgebung) {}

  laeuft(): boolean {
    return this.lauf?.phase === 'sendet' || this.lauf?.phase === 'liest';
  }

  /** Eine andere Rolle macht einen Fehler, ein Ende oder eine wartende Antwort gegenstandslos. */
  auswahlGeaendert(): void {
    const p = this.lauf?.phase;
    if (p === 'fehler' || p === 'halt' || p === 'fertig') this.zuruecksetzen();
  }

  zuruecksetzen(): void {
    this.lauf = null;
    this.anhalten = false;
  }

  /** Wie beim Übertragen (U3-3b): ein entferntes Element lädt nach der laufenden Datei nichts mehr
   *  hoch und antwortet nicht im Verborgenen. */
  trennen(): void {
    this.getrennt = true;
    this.anhalten = true;
  }

  verbinden(): void {
    this.getrennt = false;
  }

  /** „Hochladen“ mit Ort chat: von vorn. */
  async hochladen(): Promise<void> {
    if (this.lauf) return;
    this.anhalten = this.getrennt;
    return this.ab(0, []);
  }

  /** Nach einem Fehler dieselbe Datei noch einmal; die gelesenen bleiben. */
  async nochmal(): Promise<void> {
    const l = this.lauf;
    if (l?.phase === 'fehler') return this.ab(l.stelle.nr - 1, l.bisher, true);
  }

  /** Die gescheiterte Datei auslassen und mit der nächsten weitermachen (oder antworten). */
  async ueberspringen(): Promise<void> {
    const l = this.lauf;
    if (l?.phase === 'fehler') return this.ab(l.stelle.nr, l.bisher);
  }

  /** Nach der laufenden Datei anhalten. */
  anhaltenNachDieser(): void {
    if (!this.laeuft() || this.anhalten) return;
    this.anhalten = true;
    this.u.ansagen(this.u.t().haeltAn);
    this.u.zeichne();
  }

  /** Nach dem Ende (Grenze, Anhalten): mit den bisher gelesenen antworten. */
  mitGelesenen(): void {
    const e = this.u.erfassung();
    if (this.lauf?.phase !== 'halt' || !this.lauf.bisher.length || !e) return;
    this.fertig(e, this.lauf.bisher);
  }

  /** `wiederholt`: die erste Datei ist ein neuer Versuch — sie geht trotz „Anhalten“ noch hoch. */
  private async ab(start: number, bisher: readonly GeleseneDatei[], wiederholt = false): Promise<void> {
    const e = this.u.erfassung();
    const host = this.u.host();
    if (!e || !host || this.laeuft()) return;
    const dateien = this.u.dateien();
    const t = this.u.t();
    const gelesen = [...bisher];
    const kennungen = dublettenAus(dateien, bisher);
    for (let k = start; k < dateien.length; k++) {
      const d = dateien[k];
      const doppelt = kennungen.get(schluessel(d));
      if (doppelt) {
        gelesen.push({ i: d.i, rolle: d.rolle, upload_id: doppelt });
        continue;
      }
      if (this.anhalten && !(wiederholt && k === start)) return this.beenden({ phase: 'halt', grund: 'angehalten', bisher: gelesen });
      const stelle: ChatStelle = { nr: k + 1, von: dateien.length, name: d.name };
      this.lauf = { phase: 'sendet', anteil: 0, stelle };
      this.ansage = k === start || ansageFaellig(stelle.nr, stelle.von);
      if (this.ansage) this.u.ansagen(sendetSatz(t, 0, stelle));
      this.u.zeichne();
      try {
        const befund = await host.hochladen(d.handle, (anteil) => this.fortschritt(anteil), d.rolle);
        if (this.u.erfassung() !== e) return this.verwerfen();   // inzwischen neu gewählt
        const upload_id = gelesenAus(befund);
        if (!upload_id) throw Object.assign(new Error('Befund unbrauchbar'), { code: 'fehler' });
        gelesen.push({ i: d.i, rolle: d.rolle, upload_id });
        kennungen.set(schluessel(d), upload_id);
      } catch (fehler) {
        if (this.u.erfassung() !== e) return this.verwerfen();
        const code = codeVon(fehler);
        const satz = fehlerSatz(t, code, stelle);
        if (ENDET.has(code)) return this.beenden({ phase: 'halt', grund: 'grenze', code, stelle, bisher: gelesen }, satz);
        return this.beenden({ phase: 'fehler', code, stelle, bisher: gelesen }, satz);
      }
    }
    // Im Verborgenen keine Antwort: das Element zeigt beim Wiederkommen „Mit den gelesenen weiter“.
    if (this.getrennt) return this.beenden({ phase: 'halt', grund: 'angehalten', bisher: gelesen });
    this.fertig(e, gelesen);
  }

  private beenden(lauf: Ende, satz?: string): void {
    const t = this.u.t();
    this.lauf = lauf;
    this.u.ansagen(satz ?? t.angehalten(t.dateien(lauf.bisher.length)));
    this.u.zeichne();
  }

  private fertig(e: Erfassung<File>, gelesen: readonly GeleseneDatei[]): void {
    this.lauf = { phase: 'fertig', antwort: chatAntwort(e, gelesen, this.u.t().dateiOhneName) };
    if (!this.u.nurLesen?.()) this.u.host()?.vormerken(this.lauf.antwort as unknown as Record<string, unknown>);
    this.senden();
  }

  /** Die Antwort schicken — läuft gerade ein Zug, bleibt sie bis zum Knopf „Weiter“ stehen. */
  senden(): void {
    if (this.lauf?.phase !== 'fertig' || this.u.nurLesen?.()) return;
    const { antwort } = this.lauf;
    const t = this.u.t();
    const n = antwort.dateien?.length ?? 0;
    if (this.u.beschaeftigt()) {
      this.u.ansagen(t.gelesenWartet(n));
      this.u.zeichne();
      return;
    }
    this.u.host()?.antworten(antwort as unknown as Record<string, unknown>, t.blaseChat(t.dateien(n)));
  }

  /** Ein Fortschrittsschritt: nur Wert des Balkens und Satz an Ort und Stelle (das Label des Balkens
   *  bleibt „Datei k von n“, den Wert meldet das Element selbst); neu gezeichnet wird nur beim Wechsel
   *  zu „wird gelesen“, angesagt wie das Hochladen dieser Datei. */
  private fortschritt(anteil: number): void {
    if (this.lauf?.phase !== 'sendet') return;
    const t = this.u.t();
    const { stelle } = this.lauf;
    if (anteil >= 1) {
      this.lauf = { phase: 'liest', stelle };
      if (this.ansage) this.u.ansagen(t.liestDatei(stelle.nr, stelle.von));
      this.u.zeichne();
      return;
    }
    this.lauf = { phase: 'sendet', anteil, stelle };
    const prozent = Math.round(anteil * 100);
    const balken = this.u.wurzel().querySelector<HTMLProgressElement>('progress[data-chat-balken]');
    const zeile = this.u.wurzel().querySelector<HTMLElement>('[data-fokus="s:chat"]');
    if (balken) balken.value = prozent;
    if (zeile) zeile.textContent = sendetSatz(t, prozent, stelle);
  }

  /** Antwort oder Fehler kamen für eine Auswahl, die es nicht mehr gibt — das Modul bleibt bedienbar. */
  private verwerfen(): void {
    this.zuruecksetzen();
    this.u.zeichne();
  }
}

/** Die Kennungen schon gelesener Dateien je Schlüssel — auch ein Weitermachen lädt keine Dublette. */
function dublettenAus(dateien: readonly LokaleDatei<File>[], bisher: readonly GeleseneDatei[]): Map<string, string> {
  const kennungen = new Map<string, string>();
  for (const g of bisher) {
    const d = dateien.find((x) => x.i === g.i);
    if (d) kennungen.set(schluessel(d), g.upload_id);
  }
  return kennungen;
}
