/**
 * `<boerdi-ui-upload>` — Ordner und Dateien bereitstellen (Paket U3-1a), nachgeladen als rahmenloses
 * Custom Element (`laden: "bei_bedarf"`, Vertrag `_nachladen/element-vertrag.ts`).
 *
 * Auswahl per Knopf oder Ablegen (`upload-eingabe.ts`, `upload-erfassen.ts`), Rollen je Datei oder
 * Ordner (`upload-rollen.ts`); der Befund geht als Vormerkung mit einer getippten Nachricht mit — nie
 * Inhalte. Plan 2026-11-17, Paket U4 — ein Weg: die Frage „Wo sollen sie verarbeitet werden?“
 * (`upload-orte*.ts`), dann **ein** Knopf „Hochladen“: „Hier im Chat“ (`upload-chat*.ts`,
 * `host.hochladen` mit Rolle) oder „In WLO ablegen und erschließen“ (`upload-uebertragen*.ts`,
 * `host.ablegen`, Vorschau mit „Jetzt übertragen“); daneben „Nur Namen senden (nichts hochladen)“.
 * Jede Antwort ist `aktion: "bereitgestellt"` mit `ort`. Darstellung in `upload-ansicht.ts`; hier
 * bleiben Zustand, Ereignisse und Fokus.
 */
import type { ElementHost, NachladeElement } from '../_nachladen/element-vertrag';
import type { ModulKontext } from '../_vertrag/ui-block';
import { antwortDaten } from './upload-antwort';
import { ansichtTeile, grenzenAus, nurLesenOhneStapel, type UploadSicht, wahlFuer, wegAktiv, type Zustand, zusammenfassung } from './upload-ansicht';
import { namenAntwort } from './upload-chat';
import { ChatAblauf } from './upload-chat-ablauf';
import { dateiEingaben, quellenAusAblage } from './upload-eingabe';
import { ausDateiliste, erfasse, type Erfassung, type Quelle } from './upload-erfassen';
import { lokaleAuswahl, lokaleGrenzen, type Ort, orteAus } from './upload-orte';
import { alleIgnorieren, setzeRolle, vorschlagen } from './upload-rollen';
import { UPLOAD_STIL } from './upload-stil';
import { type Sprache, texte, type UploadTexte } from './upload-texte';
import { UebertragenAblauf } from './upload-uebertragen-ablauf';
import { uebertragenTexte } from './upload-uebertragen-texte';

export const ELEMENT = 'boerdi-ui-upload';

export class UiUploadElement extends HTMLElement implements NachladeElement {
  private _daten: Record<string, unknown> = {};
  private _kontext: ModulKontext | null = null;
  private _beschaeftigt = false;
  host!: ElementHost;

  private zustand: Zustand = 'leer';
  private erfassung: Erfassung<File> | null = null;
  private offen = new Set<string>();
  /** Der Ort, den die Person angeklickt hat; `null` = die Vorauswahl des Systems gilt. */
  private ort: Ort | null = null;
  private readonly chat = new ChatAblauf({
    host: () => this.host, erfassung: () => this.erfassung, beschaeftigt: () => this._beschaeftigt,
    dateien: () => (this.erfassung ? lokaleAuswahl(this.erfassung, lokaleGrenzen(this._daten)).lesbar : []),
    t: () => this.t, wurzel: () => this.wurzel, ansagen: (text) => this.ansagen(text), zeichne: () => this.zeichne(),
    nurLesen: () => !!this._kontext?.nurLesen, texterkennung: () => orteAus(this._daten).chat.texterkennung === true,
  });
  private readonly uebertragen = new UebertragenAblauf({
    host: () => this.host, erfassung: () => this.erfassung, daten: () => this._daten,
    beschaeftigt: () => this._beschaeftigt, t: () => uebertragenTexte(this.sprache), wurzel: () => this.wurzel,
    ansagen: (text) => this.ansagen(text), zeichne: () => this.zeichne(), nurLesen: () => !!this._kontext?.nurLesen,
  });
  private readonly wurzel: ShadowRoot;
  private readonly inhalt: HTMLDivElement;
  private readonly status: HTMLParagraphElement;

  constructor() {
    super();
    this.wurzel = this.attachShadow({ mode: 'open' });
    const stil = document.createElement('style');
    stil.textContent = UPLOAD_STIL;
    this.inhalt = document.createElement('div');
    this.inhalt.className = 'u';
    // Bleibt über alle Neuzeichnungen stehen, sonst sagt ein Screenreader die Änderung nicht an.
    this.status = document.createElement('p');
    this.status.className = 'u__unsichtbar';
    this.status.setAttribute('aria-live', 'polite');
    // Die Datei-Eingaben einmal und außerhalb des neu gezeichneten Inhalts (Querschnitts-Review FE-4).
    this.wurzel.append(stil, this.inhalt, this.status, ...dateiEingaben());
    this.wurzel.addEventListener('click', (e) => this.beiKlick(e));
    this.wurzel.addEventListener('change', (e) => this.beiAenderung(e));
    this.wurzel.addEventListener('dragover', (e) => this.beiZiehen(e, true));
    this.wurzel.addEventListener('dragleave', (e) => this.beiZiehen(e, false));
    this.wurzel.addEventListener('drop', (e) => void this.beiAblage(e as DragEvent));
  }

  /** U3-3b: ein entferntes Element (Widget geschlossen) überträgt nicht im Verborgenen weiter — und lädt
   *  „Hier im Chat“ nach der laufenden Datei nichts mehr hoch (Review der Oberfläche, 2). */
  connectedCallback(): void {
    this.uebertragen.verbinden();
    this.chat.verbinden();
  }

  disconnectedCallback(): void {
    this.uebertragen.trennen();
    this.chat.trennen();
  }

  // Nur bei echter Änderung neu zeichnen: der Platzhalter setzt alle drei bei jedem Zugbeginn und -ende,
  // und `kontext` kommt dabei jedes Mal als neues Objekt (Review 2026-11-07, Befund 2).
  set daten(d: Record<string, unknown>) {
    if (d === this._daten) return;
    this._daten = d ?? {};
    this.zeichne();
  }
  get daten(): Record<string, unknown> { return this._daten; }
  set kontext(k: ModulKontext) {
    if (this._kontext && gleicherKontext(this._kontext, k)) return;
    this._kontext = k;
    this.zeichne();
  }
  get kontext(): ModulKontext { return this._kontext as ModulKontext; }
  set beschaeftigt(b: boolean) {
    if (b === this._beschaeftigt) return;
    this._beschaeftigt = b;
    this.zeichne();
  }
  get beschaeftigt(): boolean { return this._beschaeftigt; }

  private get sprache(): Sprache { return this._kontext?.sprache === 'en' ? 'en' : 'de'; }
  private get t(): UploadTexte { return texte(this.sprache); }

  // ── Ereignisse ───────────────────────────────────────────────────────────────

  private beiKlick(e: Event): void {
    const ziel = (e.target as HTMLElement).closest('button');
    if (!ziel || ziel.disabled) return;
    const d = ziel.dataset;
    if (d['waehle']) (this.wurzel.querySelector(`input[data-quelle="${d['waehle']}"]`) as HTMLInputElement | null)?.click();
    else if (d['ordner'] !== undefined) this.umschalten(d['ordner']);
    else if (d['ignorieren'] !== undefined && this.erfassung && !this.auswahlFest()) this.neu(alleIgnorieren(this.erfassung, d['ignorieren'], d['an'] === 'true'));
    else if (d['hochladen']) this.hochladen(d['hochladen']);
    else if (d['namen']) this.namenSenden();
    else if (d['chat']) this.beiChat(d['chat']);
    else if (d['uebertragen']) this.beiUebertragen(d['uebertragen']);
    else if (d['zurueck']) this.zuruecksetzen();
  }

  private beiAenderung(e: Event): void {
    const ziel = e.target as HTMLElement;
    if (ziel instanceof HTMLInputElement && ziel.type === 'file') {
      const quellen = ausDateiliste(ziel.files ?? []);
      ziel.value = '';
      this.uebernimm(quellen);
    } else if (ziel instanceof HTMLInputElement && ziel.type === 'radio' && ziel.dataset['ort']) {
      this.ort = ziel.dataset['ort'] as Ort;
      this.zeichne();
    } else if (ziel instanceof HTMLSelectElement && ziel.dataset['datei'] && this.erfassung && !this.auswahlFest()) {
      const rolle = ziel.value as 'inhalt' | 'struktur' | 'ignorieren';
      this.neu(setzeRolle(this.erfassung, Number(ziel.dataset['datei']), rolle));
    }
  }

  /* Im ganzen Modul abgefangen (Review U3-1, Befund 9): sonst öffnete der Browser eine Datei, die
   * neben der Fläche landet — und das Chat-Fenster wäre weg. Ausgewertet wird nur auf der Fläche. */
  private beiZiehen(e: Event, ueber: boolean): void {
    e.preventDefault();
    const zone = (e.target as HTMLElement).closest?.('[data-ablage]');
    if (zone && !this._kontext?.nurLesen) zone.classList.toggle('u__ablage--ueber', ueber);
  }

  private async beiAblage(e: DragEvent): Promise<void> {
    e.preventDefault();
    const zone = (e.target as HTMLElement).closest?.('[data-ablage]');
    if (!zone || this._kontext?.nurLesen || this.zustand === 'liest') return;
    const transfer = e.dataTransfer;
    if (!transfer) return;
    // Die Einträge liest `quellenAusAblage` noch in diesem Takt — nach dem Ereignis sind sie leer.
    const quellen = quellenAusAblage(transfer, grenzenAus(this._daten).maxDateien);
    this.zustand = 'liest';
    this.ansagen(this.t.liest);
    this.zeichne();
    try {
      this.uebernimm(await quellen);
    } catch {
      this.erfassung = null;
      this.zustand = 'fehler';
      this.ansagen(this.t.leseFehler);
      this.zeichne();
    }
  }

  // ── Zustand ──────────────────────────────────────────────────────────────────

  /** „Hochladen“: nur mit dem Ort, der gerade gilt, und wenn nichts anderes läuft. */
  private hochladen(ort: string): void {
    if (this._beschaeftigt || wegAktiv(this.sicht()) || ort !== wahlFuer(this.sicht())) return;
    if (ort === 'chat') {
      // Ein Fehler der Übertragung stünde sonst neben dem Fortschritt und zöge den Fokus (Review der Oberfläche, 4)
      if (this.uebertragen.lauf?.phase === 'fehler') this.uebertragen.zuruecksetzen();
      void this.chat.hochladen();
    } else {
      void this.uebertragen.vorbereiten();
    }
  }

  private beiChat(was: string): void {
    if (was === 'nochmal') void this.chat.nochmal();
    else if (was === 'ohne') void this.chat.ueberspringen();
    else if (was === 'weiter') this.chat.senden();
    else if (was === 'anhalten') this.chat.anhaltenNachDieser();
    else if (was === 'gelesene') this.chat.mitGelesenen();
  }

  /** U3-3b: die Knöpfe des Übertragens (`data-uebertragen`). */
  private beiUebertragen(was: string): void {
    if (was === 'los' || was === 'nochmal') void this.uebertragen.senden();
    else if (was === 'abbrechen') this.uebertragen.abbrechen();
    else if (was === 'anhalten') this.uebertragen.anhaltenNachDieser();
    else if (was === 'weiter') void this.uebertragen.weiter();
  }

  /** Rollen und „Ignorieren“ ruhen, solange hochgeladen wird oder eine Freigabe besteht. */
  private auswahlFest(): boolean {
    return this.chat.laeuft() || this.uebertragen.haeltAuswahl();
  }

  private uebernimm(quellen: readonly Quelle<File>[]): void {
    // Während des Hochladens bleibt die Auswahl, wie sie ist (Review U3-3b, Befund 3).
    if (this.uebertragen.laeuft() || this.chat.laeuft()) return;
    this.uebertragen.zuruecksetzen();
    this.chat.zuruecksetzen();
    const e = vorschlagen(erfasse(quellen, grenzenAus(this._daten)),
      this._daten['einzeldatei_als_struktur'] === true);
    this.offen = new Set([e.wurzel.pfad]);
    this.zustand = e.dateien.length ? 'erfasst' : 'fehler';
    this.neu(e);
  }

  private neu(e: Erfassung<File>): void {
    this.erfassung = e;
    // Eine andere Rolle macht einen Fehler oder eine wartende Antwort gegenstandslos.
    this.chat.auswahlGeaendert();
    if (this.zustand === 'erfasst') {
      const a = antwortDaten(e, 'erfasst', this.t.dateiOhneName);
      this.host?.vormerken(a as unknown as Record<string, unknown>);
      this.ansagen(zusammenfassung(this.t, a));
    } else {
      this.ansagen(this.t.nichtsGefunden);
    }
    this.zeichne();
  }

  private umschalten(pfad: string): void {
    if (this.offen.has(pfad)) this.offen.delete(pfad);
    else this.offen.add(pfad);
    this.zeichne();
  }

  /** „Nur Namen senden (nichts hochladen)“: die Auswahl mit Ort namen — auch nach dem Ende von „Hier im Chat“. */
  private namenSenden(): void {
    if (!this.erfassung || this._beschaeftigt || (wegAktiv(this.sicht()) && this.chat.lauf?.phase !== 'halt')) return;
    const a = namenAntwort(this.erfassung, this.t.dateiOhneName);
    const text = this.t.blaseNamen(a.struktur.name || this.t.auswahl, this.t.ordner(a.zahlen.ordner),
      this.t.dateien(a.zahlen.inhalte + a.zahlen.strukturdokumente));
    this.host?.antworten(a as unknown as Record<string, unknown>, text);
  }

  private zuruecksetzen(): void {
    if (this.chat.laeuft() || this.uebertragen.laeuft()) return;
    this.chat.zuruecksetzen();
    this.uebertragen.zuruecksetzen();
    this.erfassung = null;
    this.zustand = 'leer';
    this.host?.vormerken(null);
    this.zeichne();
  }

  private ansagen(text: string): void {
    this.status.textContent = text;
  }

  // ── Darstellung ──────────────────────────────────────────────────────────────

  private zeichne(): void {
    if (!this._kontext) return;
    const fokus = (this.wurzel.activeElement as HTMLElement | null)?.dataset?.['fokus'];
    // Die Ergebnisliste rollt per Tastatur und Maus; neu gebaut stünde sie wieder oben (Review 2026-11-07).
    const rollen = this.inhalt.querySelector<HTMLElement>('.u__ergebnis')?.scrollTop ?? 0;
    const sicht = this.sicht();
    this.inhalt.replaceChildren(...ansichtTeile(sicht));
    this.fokusZurueck(fokus, sicht);
    const liste = this.inhalt.querySelector<HTMLElement>('.u__ergebnis');
    if (liste && rollen) liste.scrollTop = rollen;
  }

  private fokusZurueck(fokus: string | undefined, sicht: UploadSicht): void {
    if (!fokus) return;
    // Vergleich statt Selektor: der Schlüssel enthält Ordnernamen (beliebige Zeichen).
    const alle = [...this.inhalt.querySelectorAll<HTMLElement>('[data-fokus]')];
    // Verschwand das fokussierte Element (Auswahl, Hochladen, Zurücksetzen), geht der Fokus auf den
    // neuen Stand bzw. den Anfang — nie auf `body` (Review U3-1, Befund 2). Lag er nicht im Modul, bleibt er.
    const ersatz = nurLesenOhneStapel(sicht) ? 's:nurlesen' : this.uebertragen.lauf ? 's:ablage' : this.chat.lauf ? 's:chat'
      : this.zustand === 'erfasst' ? 's:befund' : this.zustand === 'fehler' ? 's:fehler' : 'k:waehle=ordner';
    // Ein gesperrtes Bedienelement nimmt keinen Fokus — dann das Ersatzziel (Review U3-3b, Befund 5).
    const frei = (x: HTMLElement) => !((x instanceof HTMLButtonElement || x instanceof HTMLInputElement) && x.disabled);
    (alle.find((x) => x.dataset['fokus'] === fokus && frei(x)) ?? alle.find((x) => x.dataset['fokus'] === ersatz))?.focus();
  }

  /** Das Abbild des Zustands für die Darstellung (`upload-ansicht.ts`). */
  private sicht(): UploadSicht {
    return {
      t: this.t, sprache: this.sprache, daten: this._daten, kontext: this._kontext, zustand: this.zustand,
      erfassung: this.erfassung, offen: this.offen, beschaeftigt: this._beschaeftigt, auswahlFest: this.auswahlFest(),
      ort: this.ort, chat: this.chat, uebertragen: this.uebertragen,
      link: (url) => this.host?.link(url) ?? { href: '', hinweis: '' },
    };
  }
}

/** Flach verglichen: dieselben Werte heißen derselbe Kontext, auch als neues Objekt. */
function gleicherKontext(a: ModulKontext, b: ModulKontext): boolean {
  const ka = Object.keys(a) as (keyof ModulKontext)[];
  return ka.length === Object.keys(b).length && ka.every((k) => a[k] === b[k]);
}

/** Pflicht aus dem Element-Vertrag: ein zweites Laden des Bündels definiert nicht noch einmal. */
export function definiere(): void {
  if (!customElements.get(ELEMENT)) customElements.define(ELEMENT, UiUploadElement);
}

definiere();
