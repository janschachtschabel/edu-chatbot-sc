import { NgTemplateOutlet } from '@angular/common';
import {
  afterNextRender, ChangeDetectionStrategy, Component, computed, DestroyRef, ElementRef, inject, Injector, input,
  signal,
} from '@angular/core';

import { ICONS } from '@boerdi/ui/icons/icons';
import { SafeSvgPipe } from '@boerdi/ui/icons/safe-svg.pipe';

import { BaumAnsage } from '../_baum/baum-ansage';
import { tastenAktion } from '../_baum/baum-tasten';
import { MODUL_HOST } from '../_vertrag/modul-host';
import type { ModulKontext } from '../_vertrag/ui-block';
import { TEXTE } from './themenbaum-texte';
import {
  type Eintrag, ebenen, flach, type ThemenbaumBlatt, type ThemenbaumKnoten, type ZweigZustand, zweigKnoten,
} from './themenbaum-zweige';

export type { ThemenbaumBlatt, ThemenbaumKnoten } from './themenbaum-zweige';

/** Eingabe laut manifest.json (`eingabe`). */
export interface UiThemenbaumDaten {
  readonly titel?: string;
  readonly wurzel_id?: string;
  readonly wurzel_url?: string;
  readonly gekuerzt?: boolean;
  readonly wurzel_mehr?: boolean;
  /** U2 (Review, Befund 9): das Backend erlaubt „Als Entwurf bearbeiten“ (Entwurf im Studio aktiv). */
  readonly entwurf_moeglich?: boolean;
  readonly knoten: readonly ThemenbaumKnoten[];
}

/** Wofür die Aktionsleiste gilt. */
interface Ziel {
  readonly id: string;
  readonly titel: string;
  readonly href: string;
  readonly hinweis: string;
  /** U1-h: der Eintrag, dessen Unterthemen sich nicht laden ließen (Knopf „Erneut laden“). */
  readonly erneut: Eintrag | null;
}

/**
 * Der Themenbaum (Paket U1-e): Unterthemen eines Fachportals oder einer Sammlung, Logik aus dem
 * MCP-Widget `browse` übertragen (Kinder aus den mitgelieferten Daten, gekürzte Zweige markiert).
 * Die Daten holt das Backend über die Datenquelle `browse_collection_tree`; die KI sieht die
 * Knoten nicht.
 *
 * **Seit U1-h im selben Baum tiefer:** Knoten, deren Unterthemen fehlen (zweite Ebene eines
 * Abrufs, „weitere“), lädt das Aufklappen über `host.zweig` nach — ohne Zug, ohne KI — und hängt
 * sie hier ein (Regeln in `themenbaum-zweige.ts`). Nachgeladenes gilt bis zum Neuladen der Seite;
 * der Verlauf zeigt den ursprünglichen Baum. Während des Ladens trägt der Eintrag `aria-busy` und
 * „lädt …“, ein Fehler steht am Eintrag („nicht geladen“, bei 429 „zu viele Anfragen“; Knopf
 * „Erneut laden“ in der Leiste) und schließt einen Eintrag ohne bekannte Kinder wieder — dann
 * versuchen →, Enter und Klick es direkt neu. Das Ergebnis sagt eine höfliche Statuszeile an
 * (derselbe Text zweimal wird zweimal angesagt). Stand der Fokus im Baum, bleibt er am Knoten —
 * wird eine gekürzte Liste ersetzt, folgt er dem Thema über die Kennung; in der Aktionsleiste
 * bleibt er, wo er ist.
 *
 * Bedienung nach dem WAI-ARIA-Muster „Tree View“: `tree`/`treeitem`/`group`, Ebene, Position,
 * `aria-expanded`, wandernder `tabindex`, die Auswahl folgt dem Fokus (`aria-selected` = der
 * Knoten, für den die Aktionsleiste gilt); Tasten und Ansage stehen seit U2 im gemeinsamen
 * Baum-Kern `../_baum/` (auch für den Strukturentwurf), das
 * Markup in `ui-themenbaum.component.html` (Review U1 gesamt). Anzahl, „weitere“ und der Ladezustand
 * hängen über `aria-describedby` am Eintrag, der Name bleibt der Titel. Im Baumeintrag stehen
 * keine Bedienelemente (APG): die Aktionen des aktiven Knotens stehen in einer Leiste darunter
 * und gehen über den Host. Start zugeklappt (Plan §15 E-5).
 */
@Component({
  selector: 'ui-themenbaum',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [SafeSvgPipe, NgTemplateOutlet],
  styleUrl: './ui-themenbaum.component.scss',
  templateUrl: './ui-themenbaum.component.html',
})
export class UiThemenbaum {
  readonly daten = input.required<UiThemenbaumDaten>();
  readonly kontext = input.required<ModulKontext>();

  private readonly host = inject(MODUL_HOST);
  private readonly el = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly injector = inject(Injector);

  protected readonly symbol = ICONS.collections_bookmark;
  protected readonly pfeil = ICONS.chevron_right;
  protected readonly texte = computed(() => TEXTE[this.kontext().sprache]);

  /** Offene Einträge und nachgeladene Zweige — je Knoten-Kennung, damit sie das Ersetzen einer
   *  gekürzten Liste überstehen (die Pfade verschieben sich dabei). */
  private readonly offen = signal<ReadonlySet<string>>(new Set());
  private readonly zweige = signal<ReadonlyMap<string, ZweigZustand>>(new Map());
  protected readonly aktiv = signal('0');
  /** Die Statuszeile für Vorleser (höflich; derselbe Text zweimal wird zweimal angesagt). */
  protected readonly ansage = new BaumAnsage();

  constructor() {
    inject(DestroyRef).onDestroy(() => this.ansage.aufraeumen());
  }

  protected readonly beschaeftigt = computed(() => this.host.beschaeftigt());

  /** Der sichtbare Baum (nur offene Einträge tragen Kinder). */
  protected readonly baum = computed(() => ebenen(this.daten().knoten, this.offen(), this.zweige()));
  /** Die sichtbaren Einträge in Lesereihenfolge — Grundlage der Pfeiltasten. */
  private readonly sichtbar = computed(() => flach(this.baum()));

  /** Wofür die Aktionsleiste gilt: der aktive Knoten, ohne Unterthemen die Sammlung selbst. */
  protected readonly ziel = computed<Ziel | null>(() => {
    const d = this.daten();
    const eintrag = this.sichtbar().find((s) => s.pfad === this.aktiv()) ?? this.sichtbar()[0];
    if (!eintrag) {
      return d.wurzel_id
        ? this.zielAus({ id: d.wurzel_id, titel: d.titel || this.texte().ueberschrift(''), url: d.wurzel_url }, null)
        : null;
    }
    return this.zielAus(eintrag.knoten, eintrag.nochmal ? eintrag : null);
  });

  /** Die Sammlung der Wurzel in WLO — für den Hinweis „mehr, als hier stehen“ (Review U1-e). */
  protected readonly wurzelLink = computed(() => {
    const url = this.daten().wurzel_url;
    return url ? this.host.link(url) : null;
  });

  private zielAus(knoten: ThemenbaumBlatt, erneut: Eintrag | null): Ziel {
    const link = knoten.url ? this.host.link(knoten.url) : { href: '', hinweis: '' };
    return { id: knoten.id, titel: knoten.titel, href: link.href, hinweis: link.hinweis, erneut };
  }

  /** Eine Element-Kennung im Block (Block-Kennungen sind `[a-z0-9]`, Pfade Ziffern). */
  protected kennung(teil: string): string {
    return `tb-${this.kontext().blockId}-${teil}`;
  }

  /** Anzahl, „weitere“ und Ladezustand als Beschreibung des Eintrags: der Name bleibt der Titel. */
  protected beschreibung(e: Eintrag): string | null {
    const ids = [
      e.knoten.anzahl !== undefined ? this.kennung(`k${e.pfad}-anzahl`) : '',
      e.mehr ? this.kennung(`k${e.pfad}-mehr`) : '',
      e.zustand ? this.kennung(`k${e.pfad}-zustand`) : '',
    ].filter(Boolean);
    return ids.length ? ids.join(' ') : null;
  }

  protected zustandText(e: Eintrag): string {
    return e.zustand ? this.texte().zustand[e.zustand] : '';
  }

  protected istOffen(e: Eintrag): boolean {
    return this.offen().has(e.knoten.id);
  }

  private setzeOffen(id: string, auf: boolean): void {
    this.offen.update((alt) => {
      const neu = new Set(alt);
      if (auf) neu.add(id);
      else neu.delete(id);
      return neu;
    });
  }

  /** Aufklappen; fehlen die Unterthemen noch, lädt es sie (U1-h). */
  private aufklappen(e: Eintrag): void {
    this.setzeOffen(e.knoten.id, true);
    if (e.ladbar) void this.laden(e.knoten);
  }

  private umschalten(e: Eintrag): void {
    if (this.istOffen(e)) this.setzeOffen(e.knoten.id, false);
    else this.aufklappen(e);
  }

  private setzeZweig(id: string, zustand: ZweigZustand): void {
    this.zweige.update((alt) => new Map(alt).set(id, zustand));
  }

  /** Die Unterthemen eines Knotens über den Host holen und einhängen. */
  private async laden(knoten: ThemenbaumBlatt): Promise<void> {
    this.setzeZweig(knoten.id, { status: 'laedt' });
    let liste: ThemenbaumKnoten[] | null = null;
    let mehr = false;
    let status: unknown;
    try {
      const roh = await this.host.zweig(knoten.id);
      liste = zweigKnoten(roh);
      mehr = roh['wurzel_mehr'] === true;
    } catch (err) {
      status = (err as { status?: unknown } | null)?.status;
    }
    const t = this.texte();
    if (!liste) {
      // 403: hier nicht angeboten oder abgeschaltet — ein neuer Versuch hülfe nicht. 429: zu viele
      // Anfragen — eigener Text; neu versucht wird nur auf Wunsch der Person (Review U1-h, 10).
      const gedrosselt = status === 429;
      this.setzeZweig(knoten.id, { status: 'fehler', nochmal: status !== 403, gedrosselt });
      // Review U1-h, Befund 2: ohne bekannte Kinder wieder zu — sonst stünde „offen“ ohne Gruppe
      // da, und →/Enter/Klick klappten zu statt neu zu laden.
      if (!this.sichtbar().find((s) => s.knoten.id === knoten.id)?.kinder.length) this.setzeOffen(knoten.id, false);
      this.ansage.sagen(gedrosselt ? t.gedrosselt(knoten.titel) : t.fehler(knoten.titel));
      return;
    }
    const fokusImBaum = this.fokusImBaum();
    const aktiveId = this.sichtbar().find((s) => s.pfad === this.aktiv())?.knoten.id;
    this.setzeZweig(knoten.id, { status: 'fertig', knoten: liste, mehr });
    this.ansage.sagen(liste.length ? t.geladen(liste.length, knoten.titel) : t.keine(knoten.titel));
    // Wurde eine gekürzte Liste ersetzt, folgt die Auswahl dem Thema (die Pfade verschieben sich).
    const neu = this.sichtbar();
    const ziel = neu.find((s) => s.knoten.id === aktiveId) ?? neu.find((s) => s.knoten.id === knoten.id);
    if (ziel) this.aktiv.set(ziel.pfad);
    if (fokusImBaum) afterNextRender(() => this.fokus(this.aktiv()), { injector: this.injector });
  }

  /** Steht der Fokus im Baum (nicht in Aktionsleiste oder Hinweis-Link, Review U1-h, Befund 3)?
   *  Im Shadow-DOM des Widgets über dessen Wurzel gefragt. */
  private fokusImBaum(): boolean {
    const wurzel = this.el.nativeElement.getRootNode() as Document | ShadowRoot;
    const fokussiert = wurzel.activeElement;
    const baum = this.el.nativeElement.querySelector('[role="tree"]');
    return !!fokussiert && !!baum && baum.contains(fokussiert);
  }

  protected klick(ereignis: Event, e: Eintrag): void {
    ereignis.stopPropagation();               // ein Kind-Eintrag liegt im Eltern-Eintrag
    this.aktiv.set(e.pfad);
    if (e.aufklappbar) this.umschalten(e);
  }

  private fokus(pfad: string): void {
    this.aktiv.set(pfad);
    const finde = () => this.el.nativeElement.querySelector<HTMLElement>(`#${this.kennung('k' + pfad)}`);
    const eintrag = finde();
    if (eintrag) {
      eintrag.focus();
      return;
    }
    // Eben aufgeklappt (→ → im selben Frame): das Kind ist noch nicht gezeichnet — danach fokussieren.
    afterNextRender(() => {
      if (this.aktiv() === pfad) finde()?.focus();
    }, { injector: this.injector });
  }

  protected taste(ereignis: KeyboardEvent): void {
    const aktion = tastenAktion(ereignis.key, this.sichtbar(), this.aktiv(), (e) => this.istOffen(e));
    if (!aktion) return;                       // Tab und alles andere: Verhalten des Browsers
    switch (aktion.art) {
      case 'fokus': this.fokus(aktion.pfad); break;
      case 'aufklappen': this.aufklappen(aktion.eintrag); break;
      case 'zuklappen': this.setzeOffen(aktion.eintrag.knoten.id, false); break;
      case 'umschalten': this.umschalten(aktion.eintrag); break;
      case 'inhalte': this.inhalteDesAktiven(); break;
      case 'nichts': break;
    }
    ereignis.preventDefault();
    ereignis.stopPropagation();                // ein Kind-Eintrag liegt im Eltern-Eintrag
  }

  private inhalteDesAktiven(): void {
    const z = this.ziel();
    if (z) this.inhalte(z);
  }

  /** Während eines Zugs `aria-disabled` statt `disabled` (Review U1 gesamt): der Knopf bleibt in der
   *  Tab-Reihenfolge, der Fokus geht beim Zugbeginn nicht verloren — gesperrt ist er hier. */
  protected inhalte(z: Ziel): void {
    if (this.beschaeftigt()) return;
    this.host.aktion('sammlung', { nodeId: z.id, title: z.titel });
  }

  /** U2 (T-13): „Als Entwurf bearbeiten“ — die Sammlung der Wurzel als neuer Zug ohne KI
   *  (Direktaktion `edit_collection_as_draft`); gesperrt während eines Zugs wie „Inhalte anzeigen“. */
  protected alsEntwurf(): void {
    const d = this.daten();
    if (this.beschaeftigt() || !d.wurzel_id || !d.entwurf_moeglich) return;
    this.host.aktion('alsEntwurf', { nodeId: d.wurzel_id, title: d.titel || this.texte().ueberschrift('') });
  }

  /** „Erneut laden“: der Knopf verschwindet beim Laden — der Fokus geht an den Eintrag zurück. */
  protected erneut(e: Eintrag): void {
    this.setzeOffen(e.knoten.id, true);
    void this.laden(e.knoten);
    this.fokus(e.pfad);
  }
}
