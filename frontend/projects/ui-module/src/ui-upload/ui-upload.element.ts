/**
 * `<boerdi-ui-upload>` — Ordner und Dateien erfassen (Paket U3-1a), nachgeladen als rahmenloses Custom
 * Element (`laden: "bei_bedarf"`, Vertrag `_nachladen/element-vertrag.ts`).
 *
 * Die Person wählt einen Ordner (oder Dateien) per Knopf oder legt ihn ab; daraus entsteht im Browser
 * der Ordnerbaum mit Dateizahlen (`upload-erfassen.ts`). Rollen setzt sie je Datei oder je Ordner
 * (`upload-rollen.ts`). Der Befund geht als Vormerkung mit der nächsten getippten Nachricht oder per
 * Knopf als Antwort (`upload-antwort.ts`) — nur Ordnernamen und Zahlen, keine Dateinamen.
 *
 * Seit U3-2c lässt sich ein markiertes Strukturdokument lesen: nur dieses wird hochgeladen
 * (`host.hochladen`), das Backend gibt den Befund zurück, und das Modul antwortet mit dem Ziel der
 * Person (`upload-dokument.ts`) — etwa „Themenbaum aus dem Strukturdokument erstellen“.
 *
 * Seit U3-3b lassen sich die erfassten Dateien per Klick in den persönlichen Bereich in WLO übertragen
 * (`upload-uebertragen*.ts`, `host.ablegen`) — nur, wenn das System es im Block erlaubt (Studio und
 * Anmeldung), und erst nach einer Vorschau mit „Jetzt übertragen“.
 *
 * Die Darstellung liegt in `upload-ansicht.ts` (Querschnitts-Review 2026-11-06, Q4); hier bleiben Zustand,
 * Ereignisse und Fokus.
 */
import type { ElementHost, NachladeElement } from '../_nachladen/element-vertrag';
import type { ModulKontext } from '../_vertrag/ui-block';
import { ansichtTeile, grenzenAus, nurLesenOhneStapel, type UploadSicht, type Zustand, zusammenfassung } from './upload-ansicht';
import { antwortDaten, type AntwortAktion } from './upload-antwort';
import type { DokumentZiel } from './upload-dokument';
import { DokumentAblauf } from './upload-dokument-ablauf';
import { ausDateiliste, ausEintraegen, erfasse, type Erfassung, type Quelle } from './upload-erfassen';
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
  private readonly dokument = new DokumentAblauf({
    host: () => this.host, erfassung: () => this.erfassung, daten: () => this._daten,
    beschaeftigt: () => this._beschaeftigt, t: () => this.t, wurzel: () => this.wurzel,
    ansagen: (text) => this.ansagen(text), zeichne: () => this.zeichne(), nurLesen: () => !!this._kontext?.nurLesen,
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
    // Die Datei-Eingaben einmal und außerhalb des neu gezeichneten Inhalts (Querschnitts-Review FE-4):
    // sonst hinge ein offener Dateidialog an einem entfernten Element, wenn ein Zug kommt oder geht.
    this.wurzel.append(stil, this.inhalt, this.status, ...this.eingaben());
    this.wurzel.addEventListener('click', (e) => this.beiKlick(e));
    this.wurzel.addEventListener('change', (e) => void this.beiAenderung(e));
    this.wurzel.addEventListener('dragover', (e) => this.beiZiehen(e, true));
    this.wurzel.addEventListener('dragleave', (e) => this.beiZiehen(e, false));
    this.wurzel.addEventListener('drop', (e) => void this.beiAblage(e as DragEvent));
  }

  /** U3-3b: ein entferntes Element (Widget geschlossen) überträgt nicht im Verborgenen weiter. */
  connectedCallback(): void { this.uebertragen.verbinden(); }
  disconnectedCallback(): void { this.uebertragen.trennen(); }

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
    else if (d['antwort']) this.antworten(d['antwort'] as AntwortAktion);
    else if (d['uebertragen']) this.beiUebertragen(d['uebertragen']);
    else if (d['dokument'] && !this.uebertragen.laeuft()) void this.dokument.lesen(d['dokument'] as DokumentZiel);
    else if (d['weiter']) this.dokument.senden();
    else if (d['zurueck']) this.zuruecksetzen();
  }

  private async beiAenderung(e: Event): Promise<void> {
    const ziel = e.target as HTMLElement;
    if (ziel instanceof HTMLInputElement && ziel.type === 'file') {
      const quellen = ausDateiliste(ziel.files ?? []);
      ziel.value = '';
      this.uebernimm(quellen);
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
    const eintraege = [...(transfer.items ?? [])]
      .filter((i) => i.kind === 'file')
      .map((i) => (i as DataTransferItem & { webkitGetAsEntry?: () => unknown }).webkitGetAsEntry?.())
      .filter((x): x is NonNullable<typeof x> => !!x);
    this.zustand = 'liest';
    this.ansagen(this.t.liest);
    this.zeichne();
    try {
      const g = grenzenAus(this._daten);
      const quellen = eintraege.length
        ? await ausEintraegen(eintraege as never, g.maxDateien + 1)
        : ausDateiliste(transfer.files ?? []);
      this.uebernimm(quellen);
    } catch {
      this.erfassung = null;
      this.zustand = 'fehler';
      this.ansagen(this.t.leseFehler);
      this.zeichne();
    }
  }

  // ── Zustand ──────────────────────────────────────────────────────────────────

  /** U3-3b: die Knöpfe des Übertragens (`data-uebertragen`). */
  private beiUebertragen(was: string): void {
    if (was === 'pruefen' && !this.dokument.laeuft()) void this.uebertragen.vorbereiten();
    else if (was === 'los' || was === 'nochmal') void this.uebertragen.senden();
    else if (was === 'abbrechen') this.uebertragen.abbrechen();
    else if (was === 'anhalten') this.uebertragen.anhaltenNachDieser();
    else if (was === 'weiter') void this.uebertragen.weiter();
  }

  /** Rollen und „Ignorieren“ ruhen, solange ein Dokument gelesen wird oder eine Freigabe besteht. */
  private auswahlFest(): boolean {
    return this.dokument.laeuft() || this.uebertragen.haeltAuswahl();
  }

  private uebernimm(quellen: readonly Quelle<File>[]): void {
    // Während einer Übertragung bleibt die Auswahl, wie sie ist (Review U3-3b, Befund 3).
    if (this.uebertragen.laeuft()) return;
    this.uebertragen.zuruecksetzen();
    const e = vorschlagen(erfasse(quellen, grenzenAus(this._daten)),
      this._daten['einzeldatei_als_struktur'] === true);
    this.offen = new Set([e.wurzel.pfad]);
    this.zustand = e.dateien.length ? 'erfasst' : 'fehler';
    this.neu(e);
  }

  private neu(e: Erfassung<File>): void {
    this.erfassung = e;
    // Eine andere Rolle macht einen Fehler oder einen wartenden Befund gegenstandslos.
    this.dokument.auswahlGeaendert();
    if (this.zustand === 'erfasst') {
      const a = antwortDaten(e, 'erfasst');
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

  private antworten(aktion: AntwortAktion): void {
    if (!this.erfassung || this._beschaeftigt || this.uebertragen.laeuft()) return;
    const a = antwortDaten(this.erfassung, aktion);
    const name = a.struktur.name || this.t.auswahl;
    const text = aktion === 'ordner_als_entwurf'
      ? this.t.blaseEntwurf(name)
      : this.t.blaseErfasst(name, this.t.ordner(a.zahlen.ordner), this.t.dateien(a.zahlen.inhalte + a.zahlen.strukturdokumente));
    this.host?.antworten(a as unknown as Record<string, unknown>, text);
  }

  private zuruecksetzen(): void {
    if (this.dokument.laeuft() || this.uebertragen.laeuft()) return;
    this.dokument.zuruecksetzen();
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
    // Verschwand das fokussierte Element (Auswahl, Zurücksetzen), geht der Fokus auf das neue Ergebnis
    // bzw. den Anfang — nie auf `body` (Review U3-1, Befund 2). Lag der Fokus nicht im Modul, bleibt er.
    const ersatz = nurLesenOhneStapel(sicht) ? 's:nurlesen' : this.uebertragen.lauf ? 's:ablage' : this.dokument.lauf ? 's:dokument'
      : this.zustand === 'erfasst' ? 's:befund' : this.zustand === 'fehler' ? 's:fehler' : 'k:waehle=ordner';
    // Ein gesperrter Knopf nimmt keinen Fokus — dann das Ersatzziel (Review U3-3b, Befund 5).
    const frei = (x: HTMLElement) => !(x instanceof HTMLButtonElement && x.disabled);
    (alle.find((x) => x.dataset['fokus'] === fokus && frei(x)) ?? alle.find((x) => x.dataset['fokus'] === ersatz))?.focus();
  }

  /** Das Abbild des Zustands für die Darstellung (`upload-ansicht.ts`). */
  private sicht(): UploadSicht {
    return {
      t: this.t, sprache: this.sprache, daten: this._daten, kontext: this._kontext, zustand: this.zustand,
      erfassung: this.erfassung, offen: this.offen, beschaeftigt: this._beschaeftigt, auswahlFest: this.auswahlFest(),
      dokument: this.dokument, uebertragen: this.uebertragen,
      link: (url) => this.host?.link(url) ?? { href: '', hinweis: '' },
    };
  }

  private eingaben(): HTMLInputElement[] {
    return (['ordner', 'dateien'] as const).map((quelle) => {
      const input = document.createElement('input');
      input.type = 'file';
      input.multiple = true;
      input.hidden = true;
      input.dataset['quelle'] = quelle;
      if (quelle === 'ordner') input.setAttribute('webkitdirectory', '');
      return input;
    });
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
