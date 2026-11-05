import { NgTemplateOutlet } from '@angular/common';
import {
  afterNextRender, ChangeDetectionStrategy, Component, computed, DestroyRef, effect, ElementRef, inject, Injector,
  input, linkedSignal, signal, viewChild,
} from '@angular/core';

import { ICONS } from '@boerdi/ui/icons/icons';
import { SafeSvgPipe } from '@boerdi/ui/icons/safe-svg.pipe';

import { BaumAnsage } from '../_baum/baum-ansage';
import { flach, tastenAktion } from '../_baum/baum-tasten';
import { MODUL_HOST } from '../_vertrag/modul-host';
import type { ModulKontext } from '../_vertrag/ui-block';
import { alleMitKindern, ansicht, type EntwurfEintrag, schlagworte, vorfahren } from './entwurf-ansicht';
import { alsJson, alsMarkdown, dateiname, type EntwurfDaten } from './entwurf-export';
import {
  type Ablehnung, anzahl, ausruecken, type Baum, bereinigt, BESCHREIBUNG_ZEICHEN, einruecken, finde, hinzufuegen,
  KEYWORD_ZEICHEN, KEYWORDS, loeschen, neueKennung, setzeFelder, TITEL_ZEICHEN, verschieben,
} from './entwurf-regeln';
import { TEXTE } from './entwurf-texte';

export type { EntwurfDaten } from './entwurf-export';

/** So viele Schritte nimmt „Rückgängig“ zurück. */
const RUECK_HOECHSTENS = 20;

type Bewegung = 'hoch' | 'runter' | 'ein' | 'aus';

/**
 * Der Strukturentwurf (Paket U2, Plan 2026-11-04): eine NEUE Gliederung — von der KI erzeugt
 * (`quelle: ki`) oder aus einer WLO-Sammlung übernommen (`quelle: wlo`) —, die die Person hier
 * bearbeitet. Der Kopf sagt „Entwurf (KI)“ bzw. „Entwurf (aus WLO)“: ein Entwurf sieht nie aus wie
 * der Bestand (`ui-themenbaum`). Baum, Tasten und Ansage teilen beide über `../_baum/`.
 *
 * Bedienung nach APG „Tree View“ wie der Bestand; darunter eine Bearbeitungsleiste und das
 * Detailfeld des aktiven Punkts (Titel, Beschreibung, Schlagworte) — keine Eingabefelder im
 * Baumeintrag (T-11). Tasten im Baum: F2/Enter → Titelfeld, Entf/Rücktaste löschen,
 * Alt+Umschalt+↑/↓ verschieben, Alt+Umschalt+→/← ein-/ausrücken, Strg+Z rückgängig. Jede Aktion
 * sagt die Statuszeile an, eine unmögliche ihren Grund. Aus der Leiste bleibt der Fokus am Knopf,
 * aus dem Baum am Punkt. Deckel wie im Manifest (`entwurf-regeln.ts`).
 *
 * Abfragend (T-10): „Übernehmen“ antwortet (`host.antworten`); außerdem merkt das Modul seinen
 * Stand bei jeder Änderung vor (`host.vormerken`) — eine getippte Nachricht nimmt ihn mit.
 * Herunterladen als JSON (`wlo.sammlungsstruktur@1`) und Markdown geht auch im Nur-lesen-Zustand.
 */
@Component({
  selector: 'ui-strukturentwurf',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [SafeSvgPipe, NgTemplateOutlet],
  styleUrl: './ui-strukturentwurf.component.scss',
  templateUrl: './ui-strukturentwurf.component.html',
})
export class UiStrukturentwurf {
  readonly daten = input.required<EntwurfDaten>();
  readonly kontext = input.required<ModulKontext>();

  private readonly host = inject(MODUL_HOST);
  private readonly el = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly injector = inject(Injector);
  private readonly statusZeile = viewChild<ElementRef<HTMLElement>>('statusZeile');

  protected readonly symbol = ICONS.edit_note;
  protected readonly pfeil = ICONS.chevron_right;
  protected readonly grenzen = { titel: TITEL_ZEICHEN, beschreibung: BESCHREIBUNG_ZEICHEN };
  protected readonly texte = computed(() => TEXTE[this.kontext().sprache]);
  protected readonly nurLesen = computed(() => this.kontext().nurLesen);
  protected readonly beschaeftigt = computed(() => this.host.beschaeftigt());
  protected readonly ansage = new BaumAnsage();

  /** Beantwortet: die Antwort der Person zeigen, sonst die Daten des Blocks. */
  private readonly quelle = computed<EntwurfDaten>(() => {
    const a = this.kontext().antwort;
    return a && Array.isArray(a['knoten']) ? { ...this.daten(), ...(a as Partial<EntwurfDaten>) } : this.daten();
  });
  /** Der Stand der Person. Wird der Block nach dem Senden wieder offen (der Zug kam nicht an,
   *  `wiederOffen`), bleibt der gesendete Stand — sonst gingen alle Bearbeitungen still verloren
   *  (Review U2, Befund 1). Nur lesend zeigt er die Quelle. */
  protected readonly struktur = linkedSignal<{ knoten: Baum; nurLesen: boolean }, Baum>({
    source: () => ({ knoten: this.quelle().knoten, nurLesen: this.nurLesen() }),
    computation: (quelle, vorher) => (!quelle.nurLesen && vorher ? vorher.value : quelle.knoten),
  });
  private readonly rueck = signal<readonly Baum[]>([]);
  /** Hat die Person etwas geändert? Ein eigener Merker, kein Vergleich der Referenz: nach
   *  beantwortet → wieder offen ist der Stand eine Kopie, auch ohne Änderung (Gegenreview U2,
   *  Befund 2). Rückgängig bis zum Anfang macht ihn wieder falsch — außer ältere Schritte
   *  fielen schon aus dem Stapel (`abgeschnitten`). */
  private readonly geaendert = signal(false);
  private abgeschnitten = false;
  private readonly offen = signal<ReadonlySet<string>>(new Set());
  private readonly aktivId = signal<string | null>(null);
  /** Das Schlagwort-Feld, solange es den Fokus hat (sonst sprängen Komma und Leerzeichen weg). */
  protected readonly kwText = signal<string | null>(null);
  private vorFeld: Baum | null = null;
  private kwGekuerzt = false;

  protected readonly baum = computed(() => ansicht(this.struktur(), this.offen()));
  private readonly sichtbar = computed(() => flach(this.baum()));
  /** Der aktive Punkt; ist er zugeklappt verborgen, sein nächster sichtbarer Vorfahr — nie still
   *  der erste Punkt, sonst träfe die Leiste etwas anderes (drittes Review U2, Befund 4). */
  protected readonly aktiv = computed<EntwurfEintrag | null>(() => {
    const sichtbar = this.sichtbar();
    const id = this.aktivId();
    const kette = id ? [id, ...[...(vorfahren(this.struktur(), id) ?? [])].reverse()] : [];
    for (const k of kette) {
      const e = sichtbar.find((s) => s.knoten.id === k);
      if (e) return e;
    }
    return sichtbar[0] ?? null;
  });
  protected readonly zahl = computed(() => anzahl(this.struktur()));
  protected readonly bearbeitet = computed(() => this.geaendert());
  protected readonly allesOffen = computed(() => alleMitKindern(this.struktur()).every((id) => this.offen().has(id)));
  protected readonly hatKinder = computed(() => alleMitKindern(this.struktur()).length > 0);
  protected readonly status = computed(() => {
    const k = this.kontext();
    if (!k.nurLesen) return '';
    if (!k.antwort) return this.texte().status.veraltet;
    return this.texte().status[k.antwort['uebernommen'] === true ? 'uebernommen' : 'mitgeschickt'];
  });

  constructor() {
    // T-10: der aktuelle Stand geht mit der nächsten getippten Nachricht mit; nur lesend und beim
    // Zerstören nicht mehr (Review U2, Befund 12).
    effect(() => this.host.vormerken(this.nurLesen() ? null : this.antwortDaten(false)));
    inject(DestroyRef).onDestroy(() => {
      this.ansage.aufraeumen();
      this.host.vormerken(null);
    });
  }

  protected kennung(teil: string): string {
    return `se-${this.kontext().blockId}-${teil}`;
  }

  protected istOffen(e: EntwurfEintrag): boolean {
    return this.offen().has(e.knoten.id);
  }

  private setzeOffen(ids: readonly string[], auf: boolean): void {
    this.offen.update((alt) => {
      const neu = new Set(alt);
      ids.forEach((id) => (auf ? neu.add(id) : neu.delete(id)));
      return neu;
    });
  }

  protected allesUmschalten(): void {
    if (this.allesOffen()) this.offen.set(new Set());
    else this.setzeOffen(alleMitKindern(this.struktur()), true);
  }

  private antwortDaten(uebernommen: boolean): Record<string, unknown> {
    const { titel, quelle, thema, fach, bildungsstufe, wurzel_wlo_id, gekuerzt } = this.daten();
    return {
      titel, quelle, thema, fach, bildungsstufe, wurzel_wlo_id, gekuerzt,
      knoten: bereinigt(this.struktur(), this.texte().neuerPunkt), uebernommen, bearbeitet: this.bearbeitet(),
    };
  }

  // ── Bearbeiten ───────────────────────────────────────────────────────────

  /** Einen neuen Stand übernehmen (mit Rückgängig-Schritt) oder den Grund der Ablehnung ansagen. */
  private uebernehmeStand(neu: Baum | Ablehnung, meldung: string): boolean {
    if ('grund' in neu) {
      this.ansage.sagen(this.texte().grund[neu.grund]);
      return false;
    }
    this.merkeSchritt(this.struktur());
    this.struktur.set(neu);
    this.ansage.sagen(meldung);
    return true;
  }

  private merkeSchritt(vorher: Baum): void {
    this.rueck.update((r) => {
      if (r.length >= RUECK_HOECHSTENS) this.abgeschnitten = true;
      return [...r, vorher].slice(-RUECK_HOECHSTENS);
    });
    this.geaendert.set(true);
  }

  protected hinzufuegen(wo: 'kind' | 'danach'): void {
    if (this.nurLesen()) return;
    const a = this.aktiv();
    const neu = { id: neueKennung(this.struktur()), titel: this.texte().neuerPunkt };
    const r = hinzufuegen(this.struktur(), a?.knoten.id ?? null, a ? wo : 'danach', neu);
    const eltern = wo === 'kind' ? a?.knoten.titel : null;
    const meldung = eltern ? this.texte().getan.neu(eltern) : this.texte().getan.neuOben;
    if (!this.uebernehmeStand('grund' in r ? r : r.baum, meldung)) return;
    if (wo === 'kind' && a) this.setzeOffen([a.knoten.id], true);
    this.aktivId.set(neu.id);
    this.fokussiere(this.kennung('titel'), true);
  }

  /** `ausLeiste`: der Knopf behält den Fokus (Review U2, Befund 10) — aus dem Baum der Punkt. */
  protected loeschen(ausLeiste = false): void {
    const a = this.aktiv();
    if (!a || this.nurLesen()) return;
    const r = loeschen(this.struktur(), a.knoten.id);
    if (!this.uebernehmeStand('grund' in r ? r : r.baum, this.texte().getan.geloescht(a.knoten.titel))) return;
    if (!('grund' in r)) this.aktivId.set(r.fokus);
    // Befund 15: ohne Punkte bleibt nur „Punkt hinzufügen“ — dorthin.
    if (!this.struktur().length) this.fokussiere(this.kennung('erster'), false);
    else if (!ausLeiste) this.fokusImBaum();
  }

  protected bewegen(art: Bewegung, ausLeiste = false): void {
    const a = this.aktiv();
    if (!a || this.nurLesen()) return;
    const id = a.knoten.id;
    const s = this.struktur();
    const neu = art === 'hoch' ? verschieben(s, id, -1) : art === 'runter' ? verschieben(s, id, 1)
      : art === 'ein' ? einruecken(s, id) : ausruecken(s, id);
    const ebene = 'grund' in neu ? 0 : finde(neu, id)?.ebene ?? 0;
    const t = this.texte().getan;
    const meldung = art === 'ein' || art === 'aus' ? t[art](a.knoten.titel, ebene) : t[art](a.knoten.titel);
    if (!this.uebernehmeStand(neu, meldung)) return;
    this.setzeOffen(vorfahren(this.struktur(), id) ?? [], true);   // der Punkt bleibt sichtbar
    if (!ausLeiste) this.fokusImBaum();
  }

  /** Review U2, Befund 3: der aktive Punkt bleibt — fehlt er im alten Stand, sein Geschwister
   *  oder Elternpunkt; seine Vorfahren werden aufgeklappt, und stand der Fokus im Baum, bleibt er dort. */
  protected rueckgaengig(): void {
    if (this.nurLesen()) return;
    const r = this.rueck();
    if (!r.length) {
      this.ansage.sagen(this.texte().getan.nichtsZuruecknehmen);
      return;
    }
    const imBaum = this.fokusInBaum();
    const jetzt = this.struktur();
    const alt = r[r.length - 1];
    const id = this.aktiv()?.knoten.id ?? null;
    const fund = id ? finde(jetzt, id) : null;
    const kandidaten = [id, fund?.geschwister[fund.index - 1]?.id, fund?.geschwister[fund.index + 1]?.id, fund?.eltern];
    const ziel = kandidaten.find((k): k is string => !!k && !!finde(alt, k)) ?? alt[0]?.id ?? null;
    this.struktur.set(alt);
    this.rueck.set(r.slice(0, -1));
    this.geaendert.set(r.length > 1 || this.abgeschnitten);
    this.aktivId.set(ziel);
    if (ziel) this.setzeOffen(vorfahren(alt, ziel) ?? [], true);
    this.ansage.sagen(this.texte().getan.rueckgaengig);
    if (imBaum) this.fokusImBaum();
  }

  /** Beim Betreten eines Felds den Stand merken: die erste Änderung darin wird EIN Rückgängig-Schritt. */
  protected feldBetreten(feld: 'titel' | 'beschreibung' | 'keywords'): void {
    this.vorFeld = this.struktur();
    if (feld === 'keywords') this.kwText.set(this.aktiv()?.knoten.keywords?.join(', ') ?? '');
  }

  protected feldAendern(feld: 'titel' | 'beschreibung' | 'keywords', ereignis: Event): void {
    const a = this.aktiv();
    if (!a || this.nurLesen()) return;
    const wert = (ereignis.target as HTMLInputElement | HTMLTextAreaElement).value;
    if (this.vorFeld) {
      this.merkeSchritt(this.vorFeld);
      this.vorFeld = null;
    }
    let felder: { titel?: string; beschreibung?: string; keywords?: readonly string[] } = { [feld]: wert };
    if (feld === 'keywords') {
      this.kwText.set(wert);
      const liste = schlagworte(wert, KEYWORDS, KEYWORD_ZEICHEN);
      felder = { keywords: liste };
      // Review U2, Befund 8: was wegfällt, wird gesagt — einmal je Überschreiten, nicht je Taste.
      const roh = wert.split(',').map((w) => w.trim()).filter(Boolean);
      const gekuerzt = roh.length > KEYWORDS || roh.some((w) => w.length > KEYWORD_ZEICHEN);
      if (gekuerzt && !this.kwGekuerzt) this.ansage.sagen(this.texte().kwGekuerzt);
      this.kwGekuerzt = gekuerzt;
    }
    const neu = setzeFelder(this.struktur(), a.knoten.id, felder);
    if (!('grund' in neu)) this.struktur.set(neu);
  }

  protected feldGeschlossen(): void {
    this.kwText.set(null);
    this.vorFeld = null;
    this.kwGekuerzt = false;
  }

  /** Esc oder Enter im Feld: zurück in den Baum. Die Taste endet hier — Esc schlösse sonst das
   *  ganze Chat-Fenster (`widget.component.ts`, Review U2, Befund 2). */
  protected zurueckInDenBaum(ereignis: Event): void {
    ereignis.preventDefault();
    ereignis.stopPropagation();
    this.fokusImBaum();
  }

  protected uebernehmen(): void {
    if (this.beschaeftigt() || this.nurLesen()) return;
    this.host.antworten(this.antwortDaten(true), this.texte().uebernommenText(this.daten().titel, this.zahl()));
    // Review U2, Befund 4 (wie `ui-entscheidung`): der Knopf verschwindet, die Statuszeile erscheint.
    afterNextRender(() => this.statusZeile()?.nativeElement.focus(), { injector: this.injector });
  }

  protected herunterladen(art: 'json' | 'md'): void {
    const daten = { ...this.daten(), knoten: bereinigt(this.struktur(), this.texte().neuerPunkt) };
    const t = this.texte();
    this.host.herunterladen(dateiname(daten.titel, art), art === 'json' ? 'application/json' : 'text/markdown;charset=utf-8',
      art === 'json' ? alsJson(daten) : alsMarkdown(daten, { fach: t.fach, stufe: t.stufe, schlagworte: t.schlagworte }));
  }

  // ── Baum ──────────────────────────────────────────────────────────────────

  protected klick(ereignis: Event, e: EntwurfEintrag): void {
    ereignis.stopPropagation();               // ein Kind-Eintrag liegt im Eltern-Eintrag
    this.aktivId.set(e.knoten.id);
    if (e.aufklappbar) this.setzeOffen([e.knoten.id], !this.istOffen(e));
  }

  protected fokusErhalten(e: EntwurfEintrag): void {
    this.aktivId.set(e.knoten.id);
  }

  protected taste(ereignis: KeyboardEvent): void {
    if (!this.bearbeitungsTaste(ereignis)) {
      const aktion = tastenAktion(ereignis.key, this.sichtbar(), this.aktiv()?.pfad ?? '0', (e) => this.istOffen(e));
      if (!aktion) return;                     // Tab und alles andere: Verhalten des Browsers
      switch (aktion.art) {
        case 'fokus': this.fokusAufPfad(aktion.pfad); break;
        case 'aufklappen': this.setzeOffen([aktion.eintrag.knoten.id], true); break;
        case 'zuklappen': this.setzeOffen([aktion.eintrag.knoten.id], false); break;
        case 'umschalten': this.setzeOffen([aktion.eintrag.knoten.id], !this.istOffen(aktion.eintrag)); break;
        // Enter auf einem Blatt: umbenennen — die Standardaktion eines Entwurfs.
        case 'inhalte': if (!this.nurLesen()) this.fokussiere(this.kennung('titel'), true); break;
        case 'nichts': break;
      }
    }
    ereignis.preventDefault();
    ereignis.stopPropagation();                // ein Kind-Eintrag liegt im Eltern-Eintrag
  }

  private bearbeitungsTaste(e: KeyboardEvent): boolean {
    if (this.nurLesen()) return false;
    const bewegung: Record<string, Bewegung> = { ArrowUp: 'hoch', ArrowDown: 'runter', ArrowRight: 'ein', ArrowLeft: 'aus' };
    if (e.altKey && e.shiftKey && bewegung[e.key]) this.bewegen(bewegung[e.key]);
    else if (e.key === 'F2') this.fokussiere(this.kennung('titel'), true);
    // Rücktaste wie Entf: Mac-Tastaturen haben kein Entf (Review U2, Befund 14).
    else if (e.key === 'Delete' || e.key === 'Backspace') this.loeschen();
    else if ((e.ctrlKey || e.metaKey) && !e.shiftKey && e.key.toLowerCase() === 'z') this.rueckgaengig();
    else return false;
    return true;
  }

  private fokusAufPfad(pfad: string): void {
    const e = this.sichtbar().find((s) => s.pfad === pfad);
    if (e) this.aktivId.set(e.knoten.id);
    this.fokusImBaum();
  }

  /** Steht der Fokus im Baum? Im Shadow-DOM des Widgets über dessen Wurzel gefragt. */
  private fokusInBaum(): boolean {
    const fokussiert = (this.el.nativeElement.getRootNode() as Document | ShadowRoot).activeElement;
    const baum = this.el.nativeElement.querySelector('[role="tree"]');
    return !!fokussiert && !!baum && baum.contains(fokussiert);
  }

  private fokusImBaum(): void {
    afterNextRender(() => {
      const id = this.aktiv()?.knoten.id;
      if (id) this.fokussiere(this.kennung(`k-${id}`), false, true);
    }, { injector: this.injector });
  }

  /** Nach dem nächsten Zeichnen fokussieren (ein neues Feld oder ein verschobener Eintrag steht
   *  erst dann im DOM); `markieren` wählt den Text eines Eingabefelds aus. */
  private fokussiere(elementId: string, markieren: boolean, sofort = false): void {
    const los = () => {
      const el = this.el.nativeElement.querySelector<HTMLElement>(`#${elementId}`);
      el?.focus();
      if (markieren && el instanceof HTMLInputElement) el.select();
    };
    if (sofort) los();
    else afterNextRender(los, { injector: this.injector });
  }
}
