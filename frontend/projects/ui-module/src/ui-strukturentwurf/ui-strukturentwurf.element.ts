/**
 * `<boerdi-ui-strukturentwurf>` — der Strukturentwurf (Paket U2, Plan 2026-11-04), seit Paket BU-2
 * ein nachgeladenes, rahmenloses Custom Element (`laden: "bei_bedarf"`, Vertrag
 * `_nachladen/element-vertrag.ts`). Verhalten wie zuvor als Komponente: eine NEUE Gliederung — von
 * der KI erzeugt, aus WLO, aus Ordnern oder aus einem Dokument —, die die Person hier bearbeitet.
 * Der Kopf sagt „Entwurf (…)“: ein Entwurf sieht nie aus wie der Bestand (`ui-themenbaum`).
 *
 * Bedienung nach APG „Tree View“ wie der Bestand; darunter Bearbeitungsleiste und Detailfeld des
 * aktiven Punkts. Tasten im Baum: F2/Enter → Titelfeld, Entf/Rücktaste löschen, Alt+Umschalt+↑/↓
 * verschieben, Alt+Umschalt+→/← ein-/ausrücken, Strg+Z rückgängig. Jede Aktion sagt die
 * Statuszeile an, eine unmögliche ihren Grund. Aus der Leiste bleibt der Fokus am Knopf, aus dem
 * Baum am Punkt.
 *
 * Abfragend: „Übernehmen“ antwortet (`host.antworten`); außerdem merkt das Modul seinen Stand bei
 * jeder Änderung vor (`host.vormerken`) — eine getippte Nachricht nimmt ihn mit. Nur lesend und
 * nach dem Aushängen nimmt es die Vormerkung zurück. Herunterladen geht auch nur lesend.
 *
 * Zeichnen: nach jeder Bearbeitung neu, der Baum abgeglichen (`BaumZeichner`), die Statuszeile
 * bleibt dasselbe Element (sonst sagen Vorleser nichts an). Während ein Feld bearbeitet wird, bleibt
 * das Detailfeld stehen (Cursor, Eingabemethode). Der Fokus findet nach dem Neuzeichnen über `id`
 * bzw. `data-fokus` zurück.
 */
import { AnsageKern } from '../_baum/ansage-kern';
import { tastenAktion } from '../_baum/baum-tasten';
import type { ElementHost, NachladeElement } from '../_nachladen/element-vertrag';
import type { ModulKontext } from '../_vertrag/ui-block';
import { alsJson, alsMarkdown, dateiname } from './entwurf-export';
import { abschluss, BaumZeichner, details, el, nachDemBaum, vorDemBaum } from './entwurf-zeichnen';
import { type Bewegung, EntwurfZustand, type Feld, type Fokus } from './entwurf-zustand';
import { STIL } from './ui-strukturentwurf.stil.generated';

export const ELEMENT = 'boerdi-ui-strukturentwurf';

const P = 'ui-strukturentwurf';
const BEWEGUNG: Readonly<Record<string, Bewegung>> = { ArrowUp: 'hoch', ArrowDown: 'runter', ArrowRight: 'ein', ArrowLeft: 'aus' };

/** Ein Bereich ohne eigenes Kästchen: seine Kinder sind Glieder der Spalte (`display: contents`). */
function bereich(): HTMLDivElement {
  return el('div', 'se-teil');
}

export class UiStrukturentwurfElement extends HTMLElement implements NachladeElement {
  host!: ElementHost;
  private _daten: Record<string, unknown> = {};
  private _kontext: ModulKontext | null = null;
  private _beschaeftigt = false;
  private readonly wurzel: ShadowRoot;
  private readonly statusZeile: HTMLParagraphElement;
  private readonly ansage: AnsageKern;
  private readonly zustand: EntwurfZustand;
  private readonly baum: BaumZeichner;
  private readonly teile: { vor: HTMLDivElement; nach: HTMLDivElement; details: HTMLDivElement; ende: HTMLDivElement };
  /** Das Feld, das gerade bearbeitet wird — solange bleibt das Detailfeld stehen. */
  private feld: Feld | null = null;
  private detailsFuer = '';
  private statusFokus = false;
  private zeichnet = false;

  constructor() {
    super();
    this.wurzel = this.attachShadow({ mode: 'open' });
    const stil = el('style');
    stil.textContent = STIL;
    const section = el('section', P);
    const baum = el('ul', `${P}__baum`);
    baum.setAttribute('role', 'tree');
    this.baum = new BaumZeichner(baum);
    this.teile = { vor: bereich(), nach: bereich(), details: bereich(), ende: bereich() };
    this.statusZeile = el('p', `${P}__ansage`);
    this.statusZeile.setAttribute('role', 'status');
    this.statusZeile.setAttribute('aria-live', 'polite');
    this.ansage = new AnsageKern((t) => { this.statusZeile.textContent = t; });
    this.zustand = new EntwurfZustand((t) => this.ansage.sagen(t));
    section.append(this.teile.vor, baum, this.teile.nach, this.teile.details, this.teile.ende, this.statusZeile);
    this.wurzel.append(stil, section);
    section.addEventListener('click', (e) => this.klick(e));
    section.addEventListener('keydown', (e) => this.taste(e));
    // Im Einfangen: `focus`/`blur` steigen nicht auf, und ein von Skript ausgelöstes `input` (etwa von
    // einer Eingabehilfe) auch nicht immer — so hört der Abschnitt sie trotzdem.
    section.addEventListener('input', (e) => this.eingabe(e), true);
    section.addEventListener('focus', (e) => this.fokus(e), true);
    section.addEventListener('blur', (e) => this.verlassen(e), true);
  }

  set daten(d: Record<string, unknown>) {
    if (d === this._daten) return;
    this._daten = d ?? {};
    this.eingaben();
  }
  get daten(): Record<string, unknown> { return this._daten; }

  set kontext(k: ModulKontext) {
    if (k === this._kontext) return;
    this._kontext = k;
    this.eingaben();
    // Review BU-2, Befund 2: der Fokuswunsch nach „Übernehmen“ gilt nur dem nächsten Kontext — hat die
    // Shell die Antwort abgelehnt, holt eine spätere Statuszeile (veraltet) nicht den Fokus.
    this.statusFokus = false;
  }
  get kontext(): ModulKontext { return this._kontext as ModulKontext; }

  /** Nur der Übernehmen-Knopf hängt daran — kein Neuzeichnen (ein Feld bliebe sonst nicht stehen). */
  set beschaeftigt(b: boolean) {
    this._beschaeftigt = b;
    const haupt = this.wurzel.querySelector('[data-tat="uebernehmen"]');
    if (b) haupt?.setAttribute('aria-disabled', 'true');
    else haupt?.removeAttribute('aria-disabled');
  }
  get beschaeftigt(): boolean { return this._beschaeftigt; }

  connectedCallback(): void {
    this.zeichne();
  }

  /** Nach dem Aushängen gilt keine Vormerkung mehr (Review U2, Befund 12). */
  disconnectedCallback(): void {
    this.ansage.aufraeumen();
    this.host?.vormerken(null);
  }

  private kennung(teil: string): string {
    return `se-${this._kontext?.blockId ?? ''}-${teil}`;
  }

  private eingaben(): void {
    if (!this._kontext) return;
    const vorher = this.zustand.struktur;
    this.zustand.eingaben(this._daten, this._kontext);
    // Der Platzhalter setzt Daten und Kontext auch ohne Änderung neu — bleibt der Stand derselbe,
    // bleibt auch ein Feld stehen, in dem gerade getippt wird (Cursor, Eingabemethode).
    this.zeichne(null, this.zustand.struktur === vorher);
  }

  // ── Zeichnen ──────────────────────────────────────────────────────────────

  /** `feldStehen`: nur aus dem eigenen Tippen oder einem neuen Setzen ohne neuen Stand — dann bleibt
   *  ein bearbeitetes Detailfeld stehen; sonst zeigt es neu den Stand (Review BU-2, Befund 1). */
  private zeichne(fokus: Fokus = null, feldStehen = false): void {
    if (!this._kontext) return;
    const z = this.zustand;
    const k = (t: string) => this.kennung(t);
    const vorher = this.wurzel.activeElement as HTMLElement | null;
    const schluessel = vorher ? (vorher.id ? `#${vorher.id}` : vorher.dataset['fokus'] ? `[data-fokus="${vorher.dataset['fokus']}"]` : '') : '';
    this.zeichnet = true;
    try {
      this.teile.vor.replaceChildren(...vorDemBaum(z, k));
      this.baum.wurzel.setAttribute('aria-labelledby', k('kopf'));
      this.baum.wurzel.hidden = !z.struktur.length;
      this.baum.zeichne(z, k);
      this.teile.nach.replaceChildren(...nachDemBaum(z, k));
      this.zeichneDetails(feldStehen);
      this.teile.ende.replaceChildren(...abschluss(z, this._beschaeftigt));
      // Ersetzt oder verschoben (auch ein verschobener Eintrag verliert den Fokus): zurückholen.
      if (vorher && this.wurzel.activeElement !== vorher && schluessel) this.wurzel.querySelector<HTMLElement>(schluessel)?.focus();
      this.fokussiere(fokus);
      const status = this.teile.nach.querySelector<HTMLElement>('[data-fokus="status"]');
      if (this.statusFokus && status) {
        this.statusFokus = false;
        status.focus();                                    // Review U2, Befund 4
      }
    } finally {
      this.zeichnet = false;
    }
    this.merkeVor();
  }

  /** Das Detailfeld bleibt stehen, solange in ihm getippt wird und es demselben Punkt gilt. Jede andere
   *  Änderung (Rückgängig, Leiste bei fokussiertem Feld) baut es aus dem Stand neu. */
  private zeichneDetails(feldStehen: boolean): void {
    const z = this.zustand;
    const a = z.aktiv;
    const fuer = `${a?.knoten.id ?? ''}|${z.nurLesen}|${this._kontext?.sprache}|${this._kontext?.blockId}`;
    const box = this.teile.details.firstElementChild;
    if (feldStehen && this.feld && fuer === this.detailsFuer && box) {
      if (a) box.setAttribute('aria-label', z.texte.details(a.knoten.titel));
      return;
    }
    this.detailsFuer = fuer;
    z.kwText = null;                                       // der Rohtext gälte dem alten Stand
    this.teile.details.replaceChildren(...details(z, (t) => this.kennung(t)));
  }

  private merkeVor(): void {
    if (!this.isConnected || !this.host) return;
    this.host.vormerken(this.zustand.nurLesen ? null : this.zustand.antwortDaten(false));
  }

  private fokussiere(fokus: Fokus): void {
    if (fokus === 'baum') {
      const id = this.zustand.aktiv?.knoten.id;
      if (id) this.wurzel.getElementById(this.kennung(`k-${id}`))?.focus();
    } else if (fokus === 'titel') {
      const feld = this.wurzel.getElementById(this.kennung('titel')) as HTMLInputElement | null;
      feld?.focus();
      feld?.select();
    } else if (fokus === 'erster') {
      this.wurzel.getElementById(this.kennung('erster'))?.focus();
    }
  }

  private fokusInBaum(): boolean {
    const f = this.wurzel.activeElement;
    return !!f && this.baum.wurzel.contains(f);
  }

  // ── Ereignisse ────────────────────────────────────────────────────────────

  private klick(e: Event): void {
    const ziel = e.target as HTMLElement;
    const tat = ziel.closest<HTMLElement>('[data-tat]')?.dataset['tat'];
    if (tat) {
      this.tat(tat);
      return;
    }
    const li = ziel.closest<HTMLElement>('[role="treeitem"]');
    const id = li?.dataset['id'];
    if (!id) return;
    const eintrag = this.zustand.sichtbar.find((s) => s.knoten.id === id);
    this.zustand.aktivieren(id);
    if (eintrag?.aufklappbar) this.zustand.setzeOffen([id], !this.zustand.istOffen(eintrag));
    this.zeichne();
  }

  private tat(tat: string): void {
    const z = this.zustand;
    switch (tat) {
      case 'alles': z.allesUmschalten(); return this.zeichne();
      case 'kind': return this.zeichne(z.hinzufuegen('kind'));
      case 'danach': case 'erster': return this.zeichne(z.hinzufuegen('danach'));
      case 'hoch': case 'runter': case 'ein': case 'aus': return this.zeichne(z.bewegen(tat, true));
      case 'loeschen': return this.zeichne(z.loeschen(true));
      case 'rueckgaengig': return this.zeichne(z.rueckgaengig(this.fokusInBaum()));
      case 'uebernehmen': return this.uebernehmen();
      case 'json': case 'md': return this.herunterladen(tat);
    }
  }

  private uebernehmen(): void {
    const z = this.zustand;
    // Live am Host wie zuvor — der Spiegel `beschaeftigt` kommt erst mit dem Effekt des Platzhalters.
    if (this._beschaeftigt || this.host.beschaeftigt() || z.nurLesen) return;
    // Review U2, Befund 4 (wie `ui-entscheidung`): der Knopf verschwindet mit dem neuen Kontext,
    // die Statuszeile erscheint — und bekommt dann den Fokus.
    this.statusFokus = true;
    this.host.antworten(z.antwortDaten(true), z.texte.uebernommenText(z.daten.titel, z.zahl));
  }

  private herunterladen(art: 'json' | 'md'): void {
    const daten = this.zustand.herunterladDaten();
    const t = this.zustand.texte;
    this.host.herunterladen(dateiname(daten.titel, art), art === 'json' ? 'application/json' : 'text/markdown;charset=utf-8',
      art === 'json' ? alsJson(daten) : alsMarkdown(daten, { fach: t.fach, stufe: t.stufe, schlagworte: t.schlagworte }));
  }

  private taste(e: KeyboardEvent): void {
    const ziel = e.target as HTMLElement;
    const feld = ziel.dataset['feld'];
    if (feld) {
      // Esc oder Enter (im Titel) führt zurück in den Baum. Die Taste endet hier — Esc schlösse
      // sonst das ganze Chat-Fenster (`widget.component.ts`, Review U2, Befund 2).
      if (e.key === 'Escape' || (e.key === 'Enter' && feld === 'titel')) {
        e.preventDefault();
        e.stopPropagation();
        this.fokussiere('baum');
      }
      return;
    }
    if (ziel.getAttribute('role') !== 'treeitem') return;
    if (!this.bearbeitungsTaste(e)) {
      const z = this.zustand;
      const aktion = tastenAktion(e.key, z.sichtbar, z.aktiv?.pfad ?? '0', (x) => z.istOffen(x));
      if (!aktion) return;                                 // Tab und alles andere: Verhalten des Browsers
      switch (aktion.art) {
        case 'fokus': {
          const neu = z.sichtbar.find((s) => s.pfad === aktion.pfad);
          if (neu) z.aktivieren(neu.knoten.id);
          this.fokussiere('baum');                         // der Fokus-Handler setzt Markierung und Leiste
          break;
        }
        case 'aufklappen': z.setzeOffen([aktion.eintrag.knoten.id], true); this.zeichne(); break;
        case 'zuklappen': z.setzeOffen([aktion.eintrag.knoten.id], false); this.zeichne(); break;
        case 'umschalten': z.setzeOffen([aktion.eintrag.knoten.id], !z.istOffen(aktion.eintrag)); this.zeichne(); break;
        // Enter auf einem Blatt: umbenennen — die Standardaktion eines Entwurfs.
        case 'inhalte': if (!z.nurLesen) this.fokussiere('titel'); break;
        case 'nichts': break;
      }
    }
    e.preventDefault();
    e.stopPropagation();
  }

  private bearbeitungsTaste(e: KeyboardEvent): boolean {
    const z = this.zustand;
    if (z.nurLesen) return false;
    if (e.altKey && e.shiftKey && BEWEGUNG[e.key]) this.zeichne(z.bewegen(BEWEGUNG[e.key], false));
    else if (e.key === 'F2') this.fokussiere('titel');
    // Rücktaste wie Entf: Mac-Tastaturen haben kein Entf (Review U2, Befund 14).
    else if (e.key === 'Delete' || e.key === 'Backspace') this.zeichne(z.loeschen(false));
    else if ((e.ctrlKey || e.metaKey) && !e.shiftKey && e.key.toLowerCase() === 'z') this.zeichne(z.rueckgaengig(this.fokusInBaum()));
    else return false;
    return true;
  }

  private eingabe(e: Event): void {
    const ziel = e.target as HTMLInputElement | HTMLTextAreaElement;
    const feld = ziel.dataset['feld'] as Feld | undefined;
    if (!feld) return;
    this.feld ??= feld;
    this.zustand.feldAendern(feld, ziel.value);
    this.zeichne(null, true);
  }

  private fokus(e: Event): void {
    const ziel = e.target as HTMLElement;
    const feld = ziel.dataset?.['feld'] as Feld | undefined;
    if (feld) {
      this.feld = feld;
      this.zustand.feldBetreten(feld);
      return;
    }
    // Ein Eintrag bekommt den Fokus (Pfeiltaste, Tab, Mausdruck): nur die Markierung und die
    // Leiste — der Eintrag selbst bleibt, damit ein folgender Klick ihn trifft.
    const id = ziel.getAttribute?.('role') === 'treeitem' ? ziel.dataset['id'] : undefined;
    if (!id || this.zeichnet) return;
    this.zustand.aktivieren(id);
    this.baum.markiere(this.zustand.aktiv?.knoten.id ?? null);
    this.teile.nach.replaceChildren(...nachDemBaum(this.zustand, (t) => this.kennung(t)));
    this.zeichneDetails(false);
  }

  private verlassen(e: Event): void {
    const feld = (e.target as HTMLElement).dataset?.['feld'];
    if (!feld) return;
    const z = this.zustand;
    const warSchlagworte = z.kwText !== null;
    z.feldGeschlossen();
    this.feld = null;
    // Die Schlagworte zeigen wieder die bereinigte Liste (ohne leere und doppelte).
    if (warSchlagworte && feld === 'keywords') {
      (e.target as HTMLInputElement).value = (z.aktiv?.knoten.keywords ?? []).join(', ');
    }
  }
}

/** Pflicht aus dem Element-Vertrag: ein zweites Laden des Bündels definiert nicht noch einmal. */
export function definiere(): void {
  if (!customElements.get(ELEMENT)) customElements.define(ELEMENT, UiStrukturentwurfElement);
}

definiere();
