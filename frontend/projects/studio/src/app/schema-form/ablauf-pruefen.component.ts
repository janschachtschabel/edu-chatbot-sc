/**
 * Paket K2c-4: „Ablauf prüfen“ und die Schrittfolge — unter einem Ablauf (`x-widget: ablauf`).
 *
 * - **Prüfen** schickt den Entwurf an `POST /api/config/ablauf-pruefen` (dieselbe Prüfung wie beim
 *   Speichern, ohne zu speichern). Die Befunde eines Schritts stehen an diesem Schritt (Meldung am
 *   Feld, ⚠ in der Liste der Schritte) und in der Schrittfolge; die des ganzen Ablaufs hier oben.
 *   Ein Entwurf, der das Modell nicht besteht (422), zeigt dessen Meldungen am Feld.
 * - Die Befunde sind ein **Stand**: Ändert sich der Ablauf, nimmt das Feld sie aus dem Formular und
 *   bittet um eine neue Prüfung. Ein anderer Ablauf in derselben Instanz (die Liste zeigt einen
 *   Eintrag nach dem anderen) und „Verwerfen“ setzen alles zurück.
 * - Die **Schrittfolge** liest den Entwurf live (`ablauf-folge.ts`): je Schritt die Pfeile zum
 *   nächsten, bei Fehler, je Regel; unbekannte Ziele sind markiert.
 *
 * Die Befunde sperren das Speichern nicht (`FORM_BEFUNDE`); das Speichern prüft ohnehin selbst.
 */
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  DestroyRef,
  effect,
  inject,
  input,
  signal,
  untracked,
} from '@angular/core';

import { type AblaufBefund, AblaufApi } from '../core/ablauf-api.service';
import { describeProblem, pathKey } from '../core/field-problems';
import { StudioApiError } from '../core/studio-api-error';
import { StudioFormat } from '../i18n/studio-format.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { type FolgePfeil, schrittFolge } from './ablauf-folge';
import { FORM_BEFUNDE, type FormBefund } from './form-befunde';
import { FORM_EPOCHE } from './form-epoche';
import type { ValuePath } from './form-value';

/** `alt`: seit der Prüfung geändert — fest gemerkt, damit nicht jede weitere Änderung den ganzen
 *  Ablauf noch einmal serialisiert (Review K2c-4, Befund 8). */
type Stand = { readonly geprueft: string; readonly alt?: boolean } & (
  | { readonly art: 'befunde'; readonly befunde: readonly AblaufBefund[] }
  | { readonly art: 'form'; readonly meldungen: readonly { readonly ort: string; readonly text: string }[] }
  | { readonly art: 'fehler'; readonly text: string });

@Component({
  selector: 'studio-ablauf-pruefen',
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './schema-form.scss',
  template: `
    <div class="ap" role="group" [attr.aria-labelledby]="idBasis() + '-titel'">
      <p class="sf-legend ap-titel" [id]="idBasis() + '-titel'">{{ t('ablaufPruefen.titel') }}</p>
      <div class="ap-kopf">
        <button type="button" class="sf-add" [id]="idBasis() + '-knopf'"
          [attr.aria-disabled]="laeuft() ? 'true' : null" (click)="pruefen()">
          {{ veraltet() ? t('ablaufPruefen.erneut') : t('ablaufPruefen.knopf') }}
        </button>
        <p class="ap-status live" role="status">{{ statusText() }}</p>
      </div>
      @if (gueltig(); as s) {
        @if (s.art === 'befunde' && ablaufBefunde().length) {
          <ul class="ap-befunde">
            @for (text of ablaufBefunde(); track $index) { <li class="sf-error">{{ text }}</li> }
          </ul>
        }
        @if (s.art === 'form') {
          <!-- Review K2c-4, Befund 1: jede Meldung steht hier mit ihrer Stelle — auch eine, für
               die es kein Feld gibt (etwa ein Zweig von „str | list[Weiter]“). -->
          <ul class="ap-befunde">
            @for (m of s.meldungen; track $index) {
              <li class="sf-error">@if (m.ort) { <code>{{ m.ort }}</code>: }{{ m.text }}</li>
            }
          </ul>
        }
      }
      <p class="sf-desc">{{ t('ablaufPruefen.folge') }}</p>
      @if (!folge().length) {
        <p class="sf-desc">{{ t('ablaufPruefen.keineSchritte') }}</p>
      } @else {
        <ol class="ap-folge">
          @for (z of folge(); track z.nr) {
            <li class="ap-zeile" [class.ap-mit-befund]="befundeAn(z.nr).length > 0">
              <span class="ap-schritt">
                <code>{{ z.id || t('ablaufPruefen.ohneKennung') }}</code>
                @if (z.typ) { <span class="ap-typ">{{ typText(z.typ) }}</span> }
              </span>
              @if (!z.pfeile.length) {
                <!-- Befund 3: „Endet hier.“ nur am ende-Schritt; sonst läuft der Lauf aus -->
                <span class="ap-pfeil">{{ z.typ === 'ende' ? t('ablaufPruefen.endetHier') : t('ablaufPruefen.laeuftAus') }}</span>
              } @else {
                <ul class="ap-pfeile">
                  @for (p of z.pfeile; track $index) {
                    <li class="ap-pfeil" [class.ap-unbekannt]="!p.bekannt">{{ pfeilText(p) }}</li>
                  }
                </ul>
              }
              @for (text of befundeAn(z.nr); track $index) {
                <p class="sf-error ap-befund">{{ text }}</p>
              }
            </li>
          }
        </ol>
      }
    </div>
  `,
})
export class AblaufPruefenComponent {
  private readonly lang = inject(StudioLanguageService);
  private readonly format = inject(StudioFormat);
  private readonly api = inject(AblaufApi);
  private readonly befundeImFormular = inject(FORM_BEFUNDE, { optional: true });
  private readonly epoche = inject(FORM_EPOCHE, { optional: true });
  protected readonly t = this.lang.t;

  /** Der Ablauf im Entwurf (`AblaufArea`). */
  readonly wert = input<unknown>();
  /** Sein Pfad im Dokument — dort hängen die Befunde der Schritte (`…, schritte, nr`). */
  readonly pfad = input.required<ValuePath>();
  readonly idBasis = input.required<string>();

  readonly laeuft = signal(false);
  private readonly stand = signal<Stand | null>(null);
  /** Nummer der jüngsten Anfrage — eine ältere Antwort gilt nicht, und ein Wechsel des Ablaufs gibt
   *  den Knopf sofort frei (Review K2c-4, Befund 5). */
  private anfrage = 0;
  /** Unter welcher Quelle die Befunde im Formular stehen (der Pfad zur Zeit der Prüfung). */
  private quelle: string | null = null;

  readonly folge = computed(() => schrittFolge(this.wert()));
  private readonly jetzt = computed(() => JSON.stringify(this.wert() ?? null));
  readonly veraltet = computed(() => {
    const s = this.stand();
    return s !== null && (s.alt === true || s.geprueft !== this.jetzt());
  });
  /** Der Stand, solange er zum Entwurf passt. */
  readonly gueltig = computed(() => (this.veraltet() ? null : this.stand()));

  readonly ablaufBefunde = computed(() => {
    const s = this.gueltig();
    return s?.art === 'befunde' ? s.befunde.filter((b) => b.nr === null).map((b) => b.text) : [];
  });

  readonly statusText = computed(() => {
    if (this.laeuft()) return this.t('ablaufPruefen.laeuft');
    const s = this.stand();
    if (!s) return '';
    if (this.veraltet()) return this.t('ablaufPruefen.veraltet');
    switch (s.art) {
      case 'befunde':
        return s.befunde.length
          ? this.lang.plural('ablaufPruefen.befunde', s.befunde.length)
          : this.t('ablaufPruefen.ok');
      case 'form':
        return this.lang.plural('ablaufPruefen.form', s.meldungen.length);
      case 'fehler':
        return this.t('ablaufPruefen.fehler', { detail: s.text });
    }
  });

  /** Welcher Ablauf das ist: Pfad und Kennung als Text. Das Formular reicht bei jedem Neuzeichnen
   *  ein neues Pfad-Feld herein — erst ein anderer Text ist ein anderer Ablauf. Mit der Kennung:
   *  nach dem Löschen eines Ablaufs steht an derselben Stelle ein anderer (Befund 6). */
  private readonly welcher = computed(() => {
    const w = this.wert();
    const id = typeof w === 'object' && w !== null ? (w as Record<string, unknown>)['id'] : null;
    return `${pathKey(this.pfad())}#${typeof id === 'string' ? id : ''}`;
  });

  /** Ein anderer Ablauf in derselben Instanz, oder „Verwerfen“: nichts vom vorigen bleibt. */
  private readonly zuruecksetzen = effect(() => {
    this.welcher();
    this.epoche?.();
    untracked(() => this.leeren());
  });

  /** Geändert seit der Prüfung: die Befunde verlassen das Formular, der Stand bleibt als Hinweis. */
  private readonly veraltetRaeumen = effect(() => {
    if (!this.veraltet()) return;
    untracked(() => {
      this.ausFormular();
      const s = this.stand();
      if (s && !s.alt) this.stand.set({ ...s, alt: true });
    });
  });

  constructor() {
    inject(DestroyRef).onDestroy(() => this.ausFormular());
  }

  befundeAn(nr: number): readonly string[] {
    const s = this.gueltig();
    return s?.art === 'befunde' ? s.befunde.filter((b) => b.nr === nr).map((b) => b.text) : [];
  }

  async pruefen(): Promise<void> {
    if (this.laeuft()) return;
    const wert = this.wert() ?? null;
    const pfad = this.pfad();
    const geprueft = JSON.stringify(wert);
    const nummer = ++this.anfrage;
    this.laeuft.set(true);
    try {
      const befunde = await this.api.pruefen(wert);
      if (this.verpasst(nummer, geprueft)) return;
      this.stand.set({ art: 'befunde', geprueft, befunde });
      this.insFormular(pfad, this.jeSchritt(pfad, befunde));
    } catch (err) {
      if (this.verpasst(nummer, geprueft)) return;
      const problems = err instanceof StudioApiError && err.status === 422 ? err.problems : [];
      if (problems.length) {
        // die Pfade der Anfrage beginnen mit `body` — der Ablauf selbst
        const meldungen = problems.map((p) => ({
          stelle: p.path[0] === 'body' ? p.path.slice(1) : p.path,
          text: describeProblem(p, this.t, this.format.decimal),
        }));
        this.stand.set({ art: 'form', geprueft,
                         meldungen: meldungen.map((m) => ({ ort: pathKey(m.stelle), text: m.text })) });
        this.insFormular(pfad, meldungen.map((m) => ({ pfad: [...pfad, ...m.stelle], text: m.text })));
      } else {
        this.ausFormular();
        const text = err instanceof StudioApiError ? err.detail : String(err);
        this.stand.set({ art: 'fehler', geprueft, text });
      }
    } finally {
      if (nummer === this.anfrage) this.laeuft.set(false);
    }
  }

  protected typText(typ: string): string {
    const key = `feld.Schritt.typ.wahl.${typ}`;
    return this.lang.has(key) ? this.t(key) : typ;
  }

  protected pfeilText(p: FolgePfeil): string {
    const ziel = p.ziel ? p.ziel : this.t('ablaufPruefen.laeuftAus');
    const unbekannt = p.bekannt ? '' : ` ${this.t('ablaufPruefen.unbekannt')}`;
    if (p.keineGreift) return this.t('ablaufPruefen.keineGreift', { ziel });
    if (p.art === 'fehler') return this.t('ablaufPruefen.beiFehler', { ziel }) + unbekannt;
    if (p.art === 'weiter') return this.t('ablaufPruefen.weiter', { ziel }) + unbekannt;
    if (p.sonst) return this.t('ablaufPruefen.sonst', { ziel }) + unbekannt;
    const bedingungen = [
      ...(p.wennTeil ? [this.t('ablaufPruefen.wennTeil', { teil: p.wennTeil })] : []),
      ...(p.wennGewaehlt ? [this.t('ablaufPruefen.wennGewaehlt', { wahl: p.wennGewaehlt })] : []),
    ];
    return this.t('ablaufPruefen.regel', {
      wenn: bedingungen.length ? this.lang.listOr(bedingungen) : this.t('ablaufPruefen.ohneBedingung'),
      ziel,
    }) + unbekannt;
  }

  /** Die Antwort kam, nachdem eine neuere Anfrage lief, der Ablauf wechselte (`leeren`) oder er sich
   *  geändert hat — sie gilt nicht mehr. */
  private verpasst(nummer: number, geprueft: string): boolean {
    return nummer !== this.anfrage || geprueft !== this.jetzt();
  }

  private jeSchritt(pfad: ValuePath, befunde: readonly AblaufBefund[]): FormBefund[] {
    const je = new Map<number, string[]>();
    for (const b of befunde) if (b.nr !== null) je.set(b.nr, [...(je.get(b.nr) ?? []), b.text]);
    return [...je].map(([nr, texte]) => ({ pfad: [...pfad, 'schritte', nr], text: texte.join(' ') }));
  }

  private insFormular(pfad: ValuePath, befunde: readonly FormBefund[]): void {
    this.ausFormular();
    this.quelle = pathKey(pfad);
    this.befundeImFormular?.setzen(this.quelle, befunde);
  }

  private ausFormular(): void {
    if (this.quelle !== null) this.befundeImFormular?.entfernen(this.quelle);
    this.quelle = null;
  }

  private leeren(): void {
    this.ausFormular();
    this.stand.set(null);
    this.anfrage += 1;
    this.laeuft.set(false);
  }
}
