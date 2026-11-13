/**
 * `<boerdi-ui-fortschritt>` — der Stand eines Ablauf-Auftrags (Paket K1b), nachgeladen als rahmenloses
 * Custom Element (`laden: "bei_bedarf"`, Vertrag `_nachladen/element-vertrag.ts`).
 *
 * Der Ablauf-Treiber zeigt das Modul, sobald ein `auftrag`-Schritt einen b-api-Auftrag gestartet hat.
 * Es fragt selbst nach (`fortschritt-ablauf.ts`, ohne Zug) und lässt das Ergebnis im Zug der Person
 * abholen, sobald es fertig ist — derselbe Weg wie der Knopf „Stand prüfen“, der daneben bleibt.
 *
 * Den Satz des Schritts (`daten.text`) zeigt die Blase darüber; im Modul stünde er doppelt (Review K1b,
 * Befund 7) — er bleibt die Textfassung, wo das Bündel nicht lädt.
 *
 * Das Gerüst entsteht einmal; `zeichne()` setzt nur Texte und `hidden` — so bleibt der Fokus stehen.
 * Verschwindet ein fokussierter Knopf, geht der Fokus auf den Rahmen (nie auf `body`).
 */
import type { ElementHost, NachladeElement } from '../_nachladen/element-vertrag';
import type { ModulKontext } from '../_vertrag/ui-block';
import { FortschrittAblauf, fortschrittDaten, type Phase } from './fortschritt-ablauf';
import { FORTSCHRITT_STIL } from './fortschritt-stil';
import { type Sprache, texte, uhrzeit } from './fortschritt-texte';

export const ELEMENT = 'boerdi-ui-fortschritt';

/** Wechsel, die ein Screenreader hören soll — nicht jedes „wird geprüft“; eine Störung immer (Befund 3). */
const ANSAGEN: ReadonlySet<Phase> = new Set<Phase>(['fertig', 'abgeholt', 'abgeschlossen', 'halt', 'abgewiesen', 'manuell']);

export class UiFortschrittElement extends HTMLElement implements NachladeElement {
  private _daten: Record<string, unknown> = {};
  private _kontext: ModulKontext | null = null;
  private _beschaeftigt = false;
  host!: ElementHost;

  private readonly ablauf = new FortschrittAblauf({
    host: () => this.host, daten: () => fortschrittDaten(this._daten), beschaeftigt: () => this._beschaeftigt,
    sichtbar: () => document.visibilityState !== 'hidden', zeichne: () => this.zeichne(),
  });
  private readonly wurzel: ShadowRoot;
  private readonly rahmen: HTMLDivElement;
  private readonly titel: HTMLHeadingElement;
  private readonly balken: HTMLProgressElement;
  private readonly stand: HTMLParagraphElement;
  private readonly zeit: HTMLParagraphElement;
  private readonly jetzt: HTMLButtonElement;
  private readonly abholen: HTMLButtonElement;
  private readonly abbruch: HTMLButtonElement;
  private readonly status: HTMLParagraphElement;
  private angesagt = '';
  private readonly beiSichtbarkeit = () => this.ablauf.sichtbarGeworden();

  constructor() {
    super();
    this.wurzel = this.attachShadow({ mode: 'open' });
    const stil = document.createElement('style');
    stil.textContent = FORTSCHRITT_STIL;
    this.rahmen = this.knoten('div', 'f');
    this.rahmen.tabIndex = -1;
    this.rahmen.setAttribute('role', 'group');
    this.titel = this.knoten('h3', 'f__titel');
    this.titel.id = 'f-titel';
    this.rahmen.setAttribute('aria-labelledby', 'f-titel');
    this.balken = this.knoten('progress');
    this.stand = this.knoten('p', 'f__stand');
    this.zeit = this.knoten('p', 'f__zeit');
    const knoepfe = this.knoten('div', 'f__knoepfe');
    this.jetzt = this.knoten('button');
    this.jetzt.type = 'button';
    this.abholen = this.knoten('button');
    this.abholen.type = 'button';
    this.abbruch = this.knoten('button', 'f__abbruch');
    this.abbruch.type = 'button';
    knoepfe.append(this.jetzt, this.abholen, this.abbruch);
    this.rahmen.append(this.titel, this.balken, this.stand, this.zeit, knoepfe);
    // Bleibt über alle Zeichnungen stehen, sonst sagt ein Screenreader die Änderung nicht an.
    this.status = this.knoten('p', 'f__unsichtbar');
    this.status.setAttribute('aria-live', 'polite');
    this.wurzel.append(stil, this.rahmen, this.status);
    this.jetzt.addEventListener('click', () => {
      if (this.jetzt.getAttribute('aria-disabled') !== 'true') void this.ablauf.pruefen();
    });
    this.abholen.addEventListener('click', () => void this.ablauf.nachpruefen());
    this.abbruch.addEventListener('click', () => void this.ablauf.abbrechen());
  }

  connectedCallback(): void {
    document.addEventListener('visibilitychange', this.beiSichtbarkeit);
    if (!this._kontext?.nurLesen) this.ablauf.verbinden();
    this.zeichne();
  }

  /** Ein entferntes Element (Widget geschlossen, Verlauf neu) fragt nicht im Verborgenen weiter. */
  disconnectedCallback(): void {
    document.removeEventListener('visibilitychange', this.beiSichtbarkeit);
    this.ablauf.trennen();
  }

  set daten(d: Record<string, unknown>) { this._daten = d ?? {}; this.zeichne(); }
  get daten(): Record<string, unknown> { return this._daten; }
  set kontext(k: ModulKontext) { this._kontext = k; this.zeichne(); }
  get kontext(): ModulKontext { return this._kontext as ModulKontext; }
  set beschaeftigt(b: boolean) {
    const warBeschaeftigt = this._beschaeftigt;
    this._beschaeftigt = b;
    if (warBeschaeftigt && !b) this.ablauf.frei();
    this.zeichne();
  }
  get beschaeftigt(): boolean { return this._beschaeftigt; }

  private get sprache(): Sprache { return this._kontext?.sprache === 'en' ? 'en' : 'de'; }

  private zeichne(): void {
    if (!this._kontext) return;
    const t = texte(this.sprache);
    const nurLesen = this._kontext.nurLesen;
    const a = this.ablauf;
    this.titel.textContent = t.titel;
    const laeuft = !nurLesen && (a.phase === 'wartet' || a.phase === 'prueft' || a.phase === 'fertig');
    this.balken.hidden = !laeuft;
    this.balken.setAttribute('aria-label', t.balken);
    this.stand.textContent = nurLesen ? t.nurLesen : this.standText(a.phase);
    this.zeit.hidden = a.zuletzt === null || (!laeuft && a.phase !== 'manuell');
    this.zeit.textContent = a.zuletzt === null ? '' : t.zuletzt(uhrzeit(this.sprache, a.zuletzt));
    this.jetzt.textContent = t.jetzt;
    this.abholen.textContent = t.abholen;
    this.abbruch.textContent = t.abbrechen;
    this.sichtbar(this.jetzt, !nurLesen && (a.phase === 'wartet' || a.phase === 'prueft' || a.phase === 'manuell'));
    this.jetzt.setAttribute('aria-disabled', String(a.phase === 'prueft'));
    this.sichtbar(this.abholen, !nurLesen && a.abholenAngeboten() && !this._beschaeftigt);
    this.sichtbar(this.abbruch, !nurLesen && a.abbrechenAngeboten() && !this._beschaeftigt);
    const schluessel = `${a.phase}:${a.stoerung}`;
    if ((ANSAGEN.has(a.phase) || a.stoerung) && a.phase !== 'prueft' && this.angesagt !== schluessel) {
      this.angesagt = schluessel;
      this.status.textContent = this.stand.textContent;
    }
  }

  private standText(phase: Phase): string {
    const t = texte(this.sprache);
    switch (phase) {
      case 'prueft': return t.prueft;
      case 'fertig': return this.ablauf.ergebnis === 'fehler' ? t.fehlerAuftrag : t.fertig;
      case 'abgeholt': return t.abgeholt;
      case 'abgeschlossen': return t.abgeschlossen;
      case 'halt': return t.halt;
      case 'abgewiesen': return t.abgewiesen;
      case 'manuell': return this.ablauf.stoerung ? t.stoerungManuell : t.manuell;
      default: return this.ablauf.stoerung ? t.stoerung : t.laeuft;
    }
  }

  /** `hidden` setzen — hatte der Knopf den Fokus, geht er auf den Rahmen statt auf `body`. */
  private sichtbar(knopf: HTMLButtonElement, zeigen: boolean): void {
    if (!zeigen && !knopf.hidden && this.wurzel.activeElement === knopf) this.rahmen.focus();
    knopf.hidden = !zeigen;
  }

  private knoten<K extends keyof HTMLElementTagNameMap>(tag: K, klasse?: string): HTMLElementTagNameMap[K] {
    const e = document.createElement(tag);
    if (klasse) e.className = klasse;
    return e;
  }
}

/** Pflicht aus dem Element-Vertrag: ein zweites Laden des Bündels definiert nicht noch einmal. */
export function definiere(): void {
  if (!customElements.get(ELEMENT)) customElements.define(ELEMENT, UiFortschrittElement);
}

definiere();
