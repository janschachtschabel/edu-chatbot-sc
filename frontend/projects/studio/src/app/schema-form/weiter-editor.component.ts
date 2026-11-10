/**
 * AS-2a (Plan 2026-11-09): `weiter` eines Ablaufschritts ohne JSON.
 *
 * Die Arten richten sich nach dem Typ des Schritts, wie Prüfung und Treiber ihn lesen (Review AS-2,
 * Befund 1):
 * - **Verzweigung:** nur Regeln — je Regel eine Bedingung („gewählt ist“ eine Möglichkeit eines
 *   Auswahlfelds, „Teil vorhanden“, „sonst“), ihr Wert und das Ziel; „sonst“ zuletzt.
 * - **jeder andere Schritt:** der folgende Schritt der Liste (leer) oder ein bestimmter Schritt.
 *   Steht dort trotzdem eine Liste, bleibt sie sichtbar und ist als Fehler markiert.
 * - **ohne Typ** (frisch angelegt): alle drei.
 *
 * Ziele sind die Schritte des Ablaufs, der eigene ausdrücklich als „dieser Schritt“ (ein wartender
 * Schritt darf zu sich zurück); ein unbekanntes Ziel bleibt sichtbar und markiert. Wahlen und Teile
 * stehen als Vorschlag da (aus dem Ablauf selbst).
 *
 * Halbe Regeln sperren das Speichern — das Formular rechnet sie aus dem Dokument
 * (`regelFehlerVon`), nicht aus Ereignissen dieses Editors, denn eine Instanz zeigt nacheinander
 * verschiedene Schritte (Befund 2). Hier steht die Meldung am Feld (`aria-invalid`, Live-Region).
 * Was der Editor nicht zeigen kann (zwei Bedingungen in einer Regel, fremde Felder), steht in der
 * gewohnten JSON-Box; deren Meldungen gehen wie bei jedem JSON-Feld über `errorChange`.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input, output } from '@angular/core';

import { StudioLanguageService } from '../i18n/studio-language.service';
import { FORM_DOKUMENT } from './form-dokument';
import { JsonValueComponent } from './json-value.component';
import {
  artVon, type Bedingung, eigenerSchritt, folgendeKennung, MIT_WERT, QUELLE, type RegelZeile, regelFehlerVon,
  regelnAus, schritteAus, teileAus, VERGLEICHE, wahlenAus, type WeiterArt, weiterAus,
} from './weiter-regeln';

const BEDINGUNGEN: readonly Bedingung[] = ['gewaehlt', 'teil', 'wert', 'seite', 'sonst'];

@Component({
  selector: 'studio-weiter-editor',
  imports: [JsonValueComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './schema-form.scss',
  template: `
    @if (art() === 'json') {
      <studio-json-value
        [fieldId]="controlId()"
        [value]="value()"
        [describedByBase]="describedBy()"
        (valueChange)="valueChange.emit($event)"
        (errorChange)="errorChange.emit($event)"
      />
    } @else if (mitWahl()) {
      <!-- AS-3a: an einem Schritt mit Schnellantworten entscheidet die Wahl; nach „leeren“ steht
           der Fokus auf der Gruppe (der Knopf verschwindet, Review AS-3a, Befund 8) -->
      <div class="we" role="group" tabindex="-1" [id]="controlId()" [attr.aria-labelledby]="beschriftetVon()"
        [attr.aria-describedby]="describedBy()">
        <p class="sf-desc">{{ t('weiter.durchWahl') }}</p>
        @if (fehler()) {
          <button type="button" class="sf-remove" [id]="controlId() + '-leeren'"
            [attr.aria-describedby]="controlId() + '-fehler'" (click)="leeren()">{{ t('weiter.leeren') }}</button>
        }
        <p class="sf-error live" [id]="controlId() + '-fehler'" aria-live="polite">{{ fehlerText() }}</p>
      </div>
    } @else {
      <div class="we" role="group" [id]="controlId()" [attr.aria-labelledby]="beschriftetVon()"
        [attr.aria-describedby]="describedBy()">
        @if (arten().length > 1) {
          <label class="sf-label" [for]="controlId() + '-art'">{{ t('weiter.art') }}</label>
          <select class="sf-input" [id]="controlId() + '-art'" (change)="artWaehlen($event)"
            [attr.aria-invalid]="ungueltig('art')" [attr.aria-describedby]="fehlerId('art')">
            @for (a of arten(); track a) {
              <option [value]="a" [selected]="a === art()">{{ artText(a) }}</option>
            }
          </select>
        }
        @if (art() === 'schritt') {
          <label class="sf-label" [for]="controlId() + '-ziel'">{{ t('weiter.ziel') }}</label>
          <select class="sf-input" [id]="controlId() + '-ziel'" (change)="zielWaehlen($event)">
            @for (z of zieleMit(zielEinfach()); track z.id) {
              <option [value]="z.id" [selected]="z.id === zielEinfach()">{{ z.text }}</option>
            }
          </select>
        }
        @if (art() === 'regeln') {
          <ol class="we-regeln">
            @for (z of zeilen(); track $index; let i = $index) {
              <li class="we-zeile">
                <select class="sf-input" [id]="controlId() + '-bedingung-' + i"
                  [attr.aria-label]="t('weiter.bedingung', { n: i + 1 })" (change)="bedingung(i, $event)"
                  [attr.aria-invalid]="ungueltig('bedingung', i)" [attr.aria-describedby]="fehlerId('bedingung', i)">
                  @for (b of bedingungen; track b) {
                    <option [value]="b" [selected]="b === z.bedingung">{{ t('weiter.bedingung.' + b) }}</option>
                  }
                </select>
                @if (z.bedingung === 'wert') {
                  <!-- AS-3c: Quelle, Vergleich und (wo nötig) der Wert -->
                  <span class="we-wert">
                    <input class="sf-input" type="text" [id]="controlId() + '-quelle-' + i" [value]="z.quelle ?? ''"
                      [attr.list]="controlId() + '-quellen'" placeholder="teil.name.pfad"
                      [attr.aria-label]="t('weiter.quelle', { n: i + 1 })"
                      [attr.aria-invalid]="ungueltig('quelle', i)" [attr.aria-describedby]="fehlerId('quelle', i)"
                      (input)="quelle(i, $event)" />
                    <select class="sf-input" [id]="controlId() + '-vergleich-' + i"
                      [attr.aria-label]="t('weiter.vergleich', { n: i + 1 })" (change)="vergleichWaehlen(i, $event)">
                      @for (v of vergleiche; track v) {
                        <option [value]="v" [selected]="v === (z.vergleich || 'gleich')">{{ t('weiter.vergleich.' + v) }}</option>
                      }
                    </select>
                    @if (mitWert(z)) {
                      <input class="sf-input" type="text" [id]="controlId() + '-wert-' + i" [value]="z.wert"
                        [attr.aria-label]="t('weiter.wert.wert', { n: i + 1 })"
                        [attr.aria-invalid]="ungueltig('wert', i)" [attr.aria-describedby]="fehlerId('wert', i)"
                        (input)="wert(i, $event)" />
                    }
                  </span>
                } @else if (z.bedingung !== 'sonst') {
                  <span class="we-feld" [class.we-seite]="z.bedingung === 'seite'">
                  <input class="sf-input" type="text" [id]="controlId() + '-wert-' + i" [value]="z.wert"
                    [attr.list]="z.bedingung === 'seite' ? null : controlId() + (z.bedingung === 'teil' ? '-teile' : '-wahlen')"
                    [attr.placeholder]="z.bedingung === 'seite' ? t('weiter.wert.seite.platzhalter') : null"
                    [attr.aria-label]="t('weiter.wert.' + z.bedingung, { n: i + 1 })"
                    [attr.aria-invalid]="ungueltig('wert', i)"
                    [attr.aria-describedby]="z.bedingung === 'seite' ? seitenHilfe(i) : fehlerId('wert', i)"
                    (input)="wert(i, $event)" />
                  @if (z.bedingung === 'seite') {
                    <!-- Review AS-7b, Befund 8: die Regel steht sichtbar da, nicht nur im Platzhalter -->
                    <small class="we-hilfe" [id]="controlId() + '-seitenhilfe-' + i">{{ t('weiter.wert.seite.hilfe') }}</small>
                  }
                  </span>
                }
                <select class="sf-input we-ziel" [id]="controlId() + '-ziel-' + i"
                  [attr.aria-label]="t('weiter.zielN', { n: i + 1 })" (change)="ziel(i, $event)"
                  [attr.aria-invalid]="ungueltig('ziel', i)" [attr.aria-describedby]="fehlerId('ziel', i)">
                  @for (o of zieleMit(z.ziel); track o.id) {
                    <option [value]="o.id" [selected]="o.id === z.ziel">{{ o.text }}</option>
                  }
                </select>
                <span class="we-knoepfe">
                  <button type="button" class="sf-remove" [id]="controlId() + '-hoch-' + i" [disabled]="i === 0"
                    [attr.aria-label]="t('weiter.hoch', { n: i + 1 })" (click)="schieben(i, -1)">↑</button>
                  <button type="button" class="sf-remove" [id]="controlId() + '-runter-' + i"
                    [disabled]="i === zeilen().length - 1"
                    [attr.aria-label]="t('weiter.runter', { n: i + 1 })" (click)="schieben(i, 1)">↓</button>
                  <button type="button" class="sf-remove" [id]="controlId() + '-weg-' + i"
                    [attr.aria-label]="t('weiter.entfernen', { n: i + 1 })" (click)="entfernen(i)">✕</button>
                </span>
              </li>
            }
          </ol>
          <button type="button" class="sf-add we-neu" [id]="controlId() + '-neu'"
            [attr.aria-describedby]="fehlerId('neu')" (click)="hinzufuegen()">{{ t('weiter.neu') }}</button>
          <datalist [id]="controlId() + '-wahlen'">
            @for (w of wahlen(); track w.value) { <option [value]="w.value" [label]="w.label"></option> }
          </datalist>
          <datalist [id]="controlId() + '-teile'">
            @for (n of teile(); track n) { <option [value]="n"></option> }
          </datalist>
          <datalist [id]="controlId() + '-quellen'">
            @for (n of teile(); track n) { <option [value]="'teil.' + n"></option> }
          </datalist>
        }
        <!-- Befund 7: die Region steht immer da — eine schon gefüllt eingefügte lesen Vorlesehilfen
             oft nicht vor. -->
        <p class="sf-error live" [id]="controlId() + '-fehler'" aria-live="polite">{{ fehlerText() }}</p>
      </div>
    }
  `,
})
export class WeiterEditorComponent {
  private readonly lang = inject(StudioLanguageService);
  private readonly dokument = inject(FORM_DOKUMENT, { optional: true });
  protected readonly t = this.lang.t;
  protected readonly bedingungen = BEDINGUNGEN;
  protected readonly vergleiche = VERGLEICHE;

  readonly controlId = input.required<string>();
  readonly value = input<unknown>();
  readonly describedBy = input<string | null>(null);
  readonly beschriftetVon = input<string | null>(null);
  /** Der Pfad des Felds (`…, schritte, i, weiter`) — daraus Typ und Kennung des eigenen Schritts. */
  readonly pfad = input<readonly (string | number)[]>([]);

  readonly valueChange = output<unknown>();
  /** Nur aus der JSON-Box (wie ein JSON-Feld); halbe Regeln rechnet das Formular selbst. */
  readonly errorChange = output<string>();

  private readonly schritt = computed(() => eigenerSchritt(this.dokument?.(), this.pfad()));
  private readonly ablauf = computed(() => this.schritt()?.ablauf ?? this.dokument?.());
  readonly typ = computed(() => this.schritt()?.typ ?? '');
  /** AS-3a: der Schritt trägt Schnellantworten oder Freitext — dort entscheidet die Wahl. */
  readonly mitWahl = computed(() => this.schritt()?.mitWahl ?? false);

  readonly art = computed<WeiterArt>(() => {
    const art = artVon(this.value());
    // eine Verzweigung hat nur Regeln — auch solange noch keine da ist
    return this.typ() === 'verzweigung' && art !== 'json' ? 'regeln' : art;
  });
  readonly arten = computed<readonly WeiterArt[]>(() => {
    const typ = this.typ();
    if (typ === 'verzweigung') return ['regeln'];
    if (!typ) return ['folge', 'schritt', 'regeln'];
    // eine Liste, wo keine hingehört, bleibt sichtbar (markiert), bis man eine andere Art wählt
    return this.art() === 'regeln' ? ['folge', 'schritt', 'regeln'] : ['folge', 'schritt'];
  });
  readonly zeilen = computed(() => regelnAus(this.value()));
  readonly zielEinfach = computed(() => (typeof this.value() === 'string' ? (this.value() as string) : ''));

  readonly ziele = computed(() => schritteAus(this.ablauf()));
  readonly wahlen = computed(() => wahlenAus(this.ablauf()));
  readonly teile = computed(() => teileAus(this.ablauf()));

  readonly fehler = computed(() => regelFehlerVon(this.typ(), this.value(), this.mitWahl()));
  readonly fehlerText = computed(() => {
    const f = this.fehler();
    return f ? this.t(`weiter.fehler.${f.art}`, { n: f.zeile + 1 }) : '';
  });
  /** Welches Feld die Meldung trägt (`aria-invalid`). */
  private readonly fehlerOrt = computed(() => {
    const f = this.fehler();
    if (!f) return '';
    switch (f.art) {
      case 'wert': return `wert-${f.zeile}`;
      case 'ziel': return `ziel-${f.zeile}`;
      case 'sonstZuletzt':
      case 'sonstFehlt': return `bedingung-${f.zeile}`;
      case 'nurVerzweigung': return 'art';
      case 'leer': return 'neu';
      case 'wahlWeiter': return 'leeren';
      case 'quelle':
      case 'quelleForm': return `quelle-${f.zeile}`;
      case 'zahl':
      case 'muster': return `wert-${f.zeile}`;
    }
  });

  protected ungueltig(feld: string, i?: number): 'true' | null {
    return this.fehlerOrt() === (i === undefined ? feld : `${feld}-${i}`) ? 'true' : null;
  }

  protected fehlerId(feld: string, i?: number): string | null {
    return this.ungueltig(feld, i) ? `${this.controlId()}-fehler` : null;
  }

  /** AS-7b: Hilfe zu den Seitenmustern und, wenn es einen gibt, der Fehler der Zeile. */
  protected seitenHilfe(i: number): string {
    return [`${this.controlId()}-seitenhilfe-${i}`, this.fehlerId('wert', i)].filter(Boolean).join(' ');
  }

  protected artText(a: WeiterArt): string {
    return this.typ() && this.typ() !== 'verzweigung' && a === 'regeln'
      ? this.t('weiter.art.regelnFalsch') : this.t(`weiter.art.${a}`);
  }

  /** Die Ziele zur Auswahl — der eigene Schritt als „dieser Schritt“, ein gesetztes, das es nicht
   *  gibt, markiert dabei. */
  protected zieleMit(gesetzt: string): { id: string; text: string }[] {
    const eigene = this.schritt()?.id ?? '';
    const liste = this.ziele().map((s) => ({
      id: s.id,
      text: s.id === eigene ? this.t('weiter.dieser', { id: s.id })
        : s.typ ? `${s.id} (${this.typText(s.typ)})` : s.id,
    }));
    if (!gesetzt) return [{ id: '', text: this.t('weiter.zielWaehlen') }, ...liste];
    if (!liste.some((z) => z.id === gesetzt)) {
      return [{ id: gesetzt, text: this.t('weiter.unbekannt', { id: gesetzt }) }, ...liste];
    }
    return liste;
  }

  private typText(typ: string): string {
    const key = `feld.Schritt.typ.wahl.${typ}`;
    return this.lang.has(key) ? this.t(key) : typ;
  }

  protected artWaehlen(ereignis: Event): void {
    const auswahl = ereignis.target as HTMLSelectElement;
    const neu = auswahl.value as WeiterArt;
    const bisher = this.value();
    if (neu === 'folge') this.senden(null);
    if (neu === 'schritt') {
      const s = this.schritt();
      const ziel = typeof bisher === 'string' && bisher ? bisher
        : (this.zeilen().find((z) => z.ziel)?.ziel
          || (s ? folgendeKennung(s.ablauf, s.nr) : '')
          || this.ziele().find((z) => z.id !== s?.id)?.id || this.ziele()[0]?.id || '');
      if (ziel) this.senden(ziel);
      // Befund 5: ohne Ziel bleibt es, wie es war — auch in der Auswahl
      else auswahl.value = this.art();
    }
    if (neu === 'regeln') this.regeln(this.anfang());
  }

  protected leeren(): void {
    this.senden(null);
    const id = this.controlId();
    setTimeout(() => document.getElementById(id)?.focus(), 0);
  }

  protected zielWaehlen(ereignis: Event): void {
    this.senden((ereignis.target as HTMLSelectElement).value || null);
  }

  /** Review AS-3c, Befund 6: „Teil vorhanden: x“ ↔ „Wert vergleichen: teil.x“ übernimmt den Teil;
   *  sonst wechselt der Wert die Bedeutung und wird geleert (nur Wahl ↔ Teil behält ihn). */
  protected bedingung(i: number, ereignis: Event): void {
    const b = (ereignis.target as HTMLSelectElement).value as Bedingung;
    this.aendern(i, (z) => {
      if (z.bedingung === 'teil' && b === 'wert') {
        return { ...z, bedingung: b, quelle: z.wert ? `teil.${z.wert}` : '', vergleich: 'vorhanden', wert: '' };
      }
      if (z.bedingung === 'wert' && b === 'teil') {
        return { ...z, bedingung: b, wert: QUELLE.exec((z.quelle ?? '').trim())?.[1] ?? '' };
      }
      // AS-7b: Seitenmuster und Kennungen sind verschiedene Dinge — beim Wechsel leer
      const behalten = b !== 'sonst' && b !== 'wert' && z.bedingung !== 'wert'
        && b !== 'seite' && z.bedingung !== 'seite';
      return { ...z, bedingung: b, wert: behalten ? z.wert : '' };
    });
  }

  protected mitWert(z: RegelZeile): boolean {
    return MIT_WERT.has(z.vergleich || 'gleich');
  }

  protected quelle(i: number, ereignis: Event): void {
    const quelle = (ereignis.target as HTMLInputElement).value;
    this.aendern(i, (z) => ({ ...z, quelle }));
  }

  protected vergleichWaehlen(i: number, ereignis: Event): void {
    const vergleich = (ereignis.target as HTMLSelectElement).value;
    this.aendern(i, (z) => ({ ...z, vergleich, wert: MIT_WERT.has(vergleich) ? z.wert : '' }));
  }

  protected wert(i: number, ereignis: Event): void {
    const w = (ereignis.target as HTMLInputElement).value;
    this.aendern(i, (z) => ({ ...z, wert: w }));
  }

  protected ziel(i: number, ereignis: Event): void {
    const ziel = (ereignis.target as HTMLSelectElement).value;
    this.aendern(i, (z) => ({ ...z, ziel }));
  }

  /** Befund 6: der Fokus bleibt am selben Knopf an der neuen Stelle der Regel. */
  protected schieben(i: number, richtung: -1 | 1): void {
    const zeilen = [...this.zeilen()];
    const j = i + richtung;
    if (j < 0 || j >= zeilen.length) return;
    [zeilen[i], zeilen[j]] = [zeilen[j], zeilen[i]];
    this.regeln(zeilen);
    // ganz oben bzw. unten ist derselbe Knopf gesperrt — dann der andere
    const knopf = richtung < 0 ? (j === 0 ? 'runter' : 'hoch') : (j === zeilen.length - 1 ? 'hoch' : 'runter');
    this.fokus(`${knopf}-${j}`);
  }

  /** Befund 6: danach die Nachbarregel, sonst „Regel hinzufügen“ bzw. die Art. */
  protected entfernen(i: number): void {
    const zeilen = this.zeilen().filter((_, n) => n !== i);
    if (zeilen.length) {
      this.regeln(zeilen);
      this.fokus(`weg-${Math.min(i, zeilen.length - 1)}`);
      return;
    }
    this.senden(null);
    this.fokus(this.typ() === 'verzweigung' || this.arten().length < 2 ? 'neu' : 'art');
  }

  /** Eine neue Regel — vor einem „sonst“ am Ende, denn das gilt zuletzt. Die erste bringt ihr
   *  „sonst“ gleich mit (Befund 3), mit dem bisherigen Ziel, falls eines da war. */
  protected hinzufuegen(): void {
    const zeilen = [...this.zeilen()];
    if (!zeilen.length) {
      this.regeln(this.anfang());
      this.fokus('bedingung-0');
      return;
    }
    const neu: RegelZeile = { bedingung: 'gewaehlt', wert: '', ziel: '' };
    const sonstZuletzt = zeilen[zeilen.length - 1].bedingung === 'sonst';
    const an = sonstZuletzt ? zeilen.length - 1 : zeilen.length;
    zeilen.splice(an, 0, neu);
    this.regeln(zeilen);
    this.fokus(`bedingung-${an}`);
  }

  private anfang(): RegelZeile[] {
    const bisher = this.value();
    return [{ bedingung: 'gewaehlt', wert: '', ziel: '' },
            { bedingung: 'sonst', wert: '', ziel: typeof bisher === 'string' ? bisher : '' }];
  }

  private aendern(i: number, neu: (z: RegelZeile) => RegelZeile): void {
    this.regeln(this.zeilen().map((z, n) => (n === i ? neu(z) : z)));
  }

  private regeln(zeilen: readonly RegelZeile[]): void {
    this.senden(weiterAus(zeilen));
  }

  private senden(wert: unknown): void {
    this.valueChange.emit(wert);
  }

  /** Wie `teil-werte`: nach dem Zeichnen der neuen Zeilen. */
  private fokus(teil: string): void {
    const id = `${this.controlId()}-${teil}`;
    setTimeout(() => document.getElementById(id)?.focus(), 0);
  }
}
