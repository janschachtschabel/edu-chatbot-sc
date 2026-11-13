/**
 * `<boerdi-ui-strukturabgleich>` — der Strukturentwurf gegen eine WLO-Sammlung (Paket U4), nachgeladen als
 * rahmenloses Custom Element (`laden: "bei_bedarf"`, Vertrag `_nachladen/element-vertrag.ts`).
 *
 * Nur Anzeige: je Punkt des Entwurfs die Art (vorhanden, ähnlich, neu bzw. nicht gefunden) als Wort und die
 * zugeordnete Sammlung mit der Zahl ihrer Inhalte; Ebene 2 als verschachtelte Liste unter ihrem Punkt
 * (Review U4, Befund 7). Darunter aufklappbar die Sammlungen, die es nur in WLO gibt — mit Ebene und
 * Elternsammlung als Text (Befund 6). Links laufen über `host.link` (nur geprüfte Ziele). Fremdtext
 * (Titel) steht immer als `textContent`.
 */
import type { ElementHost, NachladeElement } from '../_nachladen/element-vertrag';
import type { ModulKontext } from '../_vertrag/ui-block';
import { ABGLEICH_STIL } from './abgleich-stil';
import { type Art, type Sprache, texte } from './abgleich-texte';

export const ELEMENT = 'boerdi-ui-strukturabgleich';

interface Wlo { nodeId: string; titel: string; anzahl?: number; url?: string; ebene?: number; eltern_titel?: string }
interface Treffer { nodeId: string; titel: string; url?: string }
interface Abdeckung { total: number; luecke: boolean; top?: Treffer[]; geraten?: string[] }
interface Zeile {
  id: string; titel: string; ebene: number; art: Art; ungewiss?: boolean; wlo?: Wlo;
  abdeckung?: Abdeckung; abdeckung_fehlt?: string;
}

const ARTEN: readonly Art[] = ['vorhanden', 'aehnlich', 'neu'];

function liste<T>(wert: unknown): T[] {
  return Array.isArray(wert) ? (wert as T[]) : [];
}

/** R3-c: der Titel des Punkts (Ebene 1) über jeder Zeile der Ebene 2 — wie in {@link punkte}. */
function elternTitel(zeilen: Zeile[]): Map<Zeile, string> {
  const eltern = new Map<Zeile, string>();
  let punkt: Zeile | null = null;
  for (const z of zeilen) {
    if (z.ebene === 1) punkt = z;
    else if (z.ebene === 2 && punkt && text(punkt.titel)) eltern.set(z, text(punkt.titel));
  }
  return eltern;
}

function zahl(wert: unknown): number {
  return typeof wert === 'number' && Number.isFinite(wert) && wert >= 0 ? wert : 0;
}

function text(wert: unknown): string {
  return typeof wert === 'string' ? wert : '';
}

export class UiStrukturabgleichElement extends HTMLElement implements NachladeElement {
  private _daten: Record<string, unknown> = {};
  private _kontext: ModulKontext | null = null;
  private _beschaeftigt = false;
  /** Review U5, NIT 8: der Klappzustand der Lücken bleibt beim Neuzeichnen, wie die Person ihn ließ. */
  private lueckenOffen: boolean | null = null;
  host!: ElementHost;
  private readonly inhalt: HTMLDivElement;

  constructor() {
    super();
    const wurzel = this.attachShadow({ mode: 'open' });
    const stil = document.createElement('style');
    stil.textContent = ABGLEICH_STIL;
    this.inhalt = document.createElement('div');
    this.inhalt.className = 'a';
    wurzel.append(stil, this.inhalt);
  }

  set daten(d: Record<string, unknown>) {
    if (d === this._daten) return;
    this._daten = d ?? {};
    this.zeichne();
  }
  get daten(): Record<string, unknown> { return this._daten; }
  // Gelesen werden nur Sprache und nurLesen — nur deren Änderung zeichnet neu.
  set kontext(k: ModulKontext) {
    if (this._kontext && this._kontext.sprache === k.sprache && this._kontext.nurLesen === k.nurLesen) return;
    this._kontext = k;
    this.zeichne();
  }
  get kontext(): ModulKontext { return this._kontext as ModulKontext; }
  // Nur Anzeige: nichts hängt am laufenden Zug.
  set beschaeftigt(b: boolean) { this._beschaeftigt = b; }
  get beschaeftigt(): boolean { return this._beschaeftigt; }

  private get sprache(): Sprache { return this._kontext?.sprache === 'en' ? 'en' : 'de'; }

  private el<K extends keyof HTMLElementTagNameMap>(tag: K, klasse = '', inhalt = ''): HTMLElementTagNameMap[K] {
    const e = document.createElement(tag);
    if (klasse) e.className = klasse;
    if (inhalt) e.textContent = inhalt;
    return e;
  }

  /** Ein Link nur über den Host (geprüfte Ziele) — sonst der Titel als Text. */
  private link(titel: string, url: string | undefined): HTMLElement {
    const ziel = url && this.host ? this.host.link(url) : null;
    if (!ziel?.href) return this.el('span', '', titel);
    const a = this.el('a', '', titel);
    a.href = ziel.href;
    a.target = '_blank';
    a.rel = 'noopener noreferrer';
    a.setAttribute('aria-label', `${titel} (${ziel.hinweis || texte(this.sprache).oeffnet})`);
    return a;
  }

  private wloZeile(w: Wlo): HTMLElement {
    const t = texte(this.sprache);
    const p = this.el('p', 'a__wlo', `${t.inWlo} `);
    p.append(this.link(text(w.titel), w.url));
    if (typeof w.anzahl === 'number') p.append(` · ${t.inhalte(zahl(w.anzahl))}`);
    return p;
  }

  private zeile(z: Zeile): HTMLLIElement {
    const t = texte(this.sprache);
    const li = this.el('li', 'a__eintrag');
    const kopf = this.el('div', 'a__zeile');
    const ungewiss = z.art === 'neu' && z.ungewiss === true;
    kopf.append(this.el('span', `a__art a__art--${ungewiss ? 'ungewiss' : z.art}`, ungewiss ? t.nichtGefunden : t.art[z.art]),
      this.el('span', 'a__name', text(z.titel)));
    if (z.wlo && z.art !== 'neu') kopf.append(this.wloZeile(z.wlo));
    if (this.mitAbdeckung) kopf.append(this.abdeckungZeile(z));
    li.append(kopf);
    return li;
  }

  /** Paket U5: Treffer in ganz WLO; eine Lücke steht als Wort im Etikett. */
  private abdeckungZeile(z: Zeile): HTMLElement {
    const t = texte(this.sprache);
    const p = this.el('p', 'a__wlo');
    if (z.abdeckung) {
      if (z.abdeckung.luecke) p.append(this.el('span', 'a__art a__art--luecke', t.luecke), ' ');
      p.append(t.treffer(zahl(z.abdeckung.total)));
      if (z.abdeckung.geraten?.length) p.append(` ${t.geraten}`);
    } else {
      p.append(t.nichtGezaehlt);
    }
    return p;
  }

  private get mitAbdeckung(): boolean {
    return typeof this._daten['abdeckung'] === 'object' && this._daten['abdeckung'] !== null;
  }

  private lueckenAbschnitt(zeilen: Zeile[]): HTMLElement {
    const t = texte(this.sprache);
    const ab = this._daten['abdeckung'] as Record<string, unknown>;
    const luecken = zeilen.filter((z) => z.abdeckung?.luecke === true);
    const details = this.el('details');
    details.open = this.lueckenOffen ?? luecken.length > 0;
    details.addEventListener('toggle', () => { this.lueckenOffen = details.open; });
    details.append(this.el('summary', '', t.luecken(luecken.length)));
    const gezaehlt = zahl(ab['gezaehlt']);
    if (ab['filter_unaufgeloest'] === true) {
      details.append(this.el('p', 'a__hinweis', t.filterUnbekannt));
      return details;
    }
    if (ab['gesperrt'] === true) {
      details.append(this.el('p', 'a__hinweis', t.gesperrt));
      return details;
    }
    if (!gezaehlt) {
      // Review U5, Befund 1: nichts gezählt heißt nicht „keine Lücken“
      details.append(this.el('p', 'a__hinweis', t.nichtZustande));
      return details;
    }
    details.append(this.el('p', 'a__hinweis', t.lueckenHinweis(zahl(ab['luecke_bis']) || 2)));
    if (zahl(ab['ungezaehlt'])) {
      details.append(this.el('p', 'a__hinweis', t.gezaehltVon(gezaehlt, gezaehlt + zahl(ab['ungezaehlt']))));
    }
    if (!luecken.length) {
      details.append(this.el('p', 'a__hinweis', t.keineLuecken));
      return details;
    }
    const ul = this.el('ul', 'a__liste');
    const eltern = elternTitel(zeilen);
    for (const z of luecken) {
      const li = this.el('li', 'a__eintrag');
      const kopf = this.el('div', 'a__zeile');
      // R3-c: ohne seinen Punkt ist ein Unterpunkt („Grundlagen“) in der Liste nicht zuzuordnen
      const name = eltern.has(z) ? `${eltern.get(z)} › ${text(z.titel)}` : text(z.titel);
      kopf.append(this.el('span', 'a__art a__art--luecke', t.trefferKurz(zahl(z.abdeckung?.total))),
        this.el('span', 'a__name', name));
      const top = liste<Treffer>(z.abdeckung?.top).filter((x) => text(x?.titel));
      if (top.length) {
        const p = this.el('p', 'a__wlo', `${t.beispiele} `);
        top.forEach((x, i) => {
          if (i) p.append(', ');
          p.append(this.link(text(x.titel), x.url));
        });
        kopf.append(p);
      }
      li.append(kopf);
      ul.append(li);
    }
    details.append(ul);
    return details;
  }

  /** Ebene 2 als verschachtelte Liste unter ihrem Punkt; ohne Punkt davor (kaputte Daten) oben. */
  private punkte(zeilen: Zeile[]): HTMLUListElement {
    const ul = this.el('ul', 'a__liste');
    let unter: HTMLUListElement | null = null;
    for (const z of zeilen) {
      const li = this.zeile(z);
      const letztes = ul.lastElementChild;
      if (z.ebene === 2 && letztes) {
        if (!unter) {
          unter = this.el('ul', 'a__liste a__liste--e2');
          letztes.append(unter);
        }
        unter.append(li);
      } else {
        ul.append(li);
        unter = null;
      }
    }
    return ul;
  }

  private zeichne(): void {
    const t = texte(this.sprache);
    const d = this._daten;
    const sammlung = (d['sammlung'] ?? {}) as Partial<Wlo>;
    const zahlen = (d['zahlen'] ?? {}) as Record<string, unknown>;
    const zeilen = liste<Zeile>(d['zeilen']).filter((z) => ARTEN.includes(z?.art));
    const nur = liste<Wlo>(d['nur_in_wlo']);
    const nurGesamt = Math.max(zahl(zahlen['nur_in_wlo']), nur.length);
    this.inhalt.replaceChildren();

    this.inhalt.append(this.el('h3', 'a__titel', t.titel(text(d['titel']))));
    const unter = this.el('p', 'a__unter', `${t.mit} `);
    unter.append(this.link(text(sammlung.titel) || t.ohneTitel, sammlung.url));
    this.inhalt.append(unter);
    this.inhalt.append(this.el('p', 'a__zahlen', t.zusammenfassung({
      vorhanden: zahl(zahlen['vorhanden']), aehnlich: zahl(zahlen['aehnlich']), neu: zahl(zahlen['neu']),
      nurInWlo: nurGesamt,
    })));

    this.inhalt.append(zeilen.length ? this.punkte(zeilen) : this.el('p', 'a__hinweis', t.leer));
    if (this.mitAbdeckung) this.inhalt.append(this.lueckenAbschnitt(zeilen));

    const details = this.el('details');
    details.append(this.el('summary', '', t.nurInWlo(nur.length, nurGesamt)));
    if (!nur.length) {
      details.append(this.el('p', 'a__hinweis', t.nurInWloLeer));
    } else {
      const ul = this.el('ul', 'a__liste');
      for (const w of nur) {
        const li = this.el('li', 'a__eintrag');
        const kopf = this.el('div', 'a__zeile');
        const name = this.el('span', 'a__name');
        name.append(this.link(text(w.titel), w.url));
        kopf.append(this.el('span', 'a__art', t.ebene(w.ebene === 2 ? 2 : 1)), name);
        const mehr = [w.ebene === 2 && text(w.eltern_titel) ? t.unter(text(w.eltern_titel)) : '',
          typeof w.anzahl === 'number' ? t.inhalte(zahl(w.anzahl)) : ''].filter(Boolean).join(' · ');
        if (mehr) kopf.append(this.el('p', 'a__wlo', mehr));
        li.append(kopf);
        ul.append(li);
      }
      details.append(ul);
    }
    this.inhalt.append(details);
    if (d['gekuerzt'] === true) this.inhalt.append(this.el('p', 'a__hinweis', t.gekuerzt));
    this.inhalt.append(this.el('p', 'a__hinweis', t.direkt));
  }
}

/** Pflicht aus dem Element-Vertrag: ein zweites Laden des Bündels definiert nicht noch einmal. */
export function definiere(): void {
  if (!customElements.get(ELEMENT)) customElements.define(ELEMENT, UiStrukturabgleichElement);
}

definiere();
