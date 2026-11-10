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
 * - Die **Schrittfolge** (Text und Bild) steht darunter (`ablauf-schrittfolge.component.ts`), mit
 *   den Befunden der Prüfung am Schritt.
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

import { Router } from '@angular/router';
import { ohneMarkdownEscapes } from '@boerdi/ui';

import { type AblaufBefund, AblaufApi, type AblaufTeil, type AblaufTestErgebnis } from '../core/ablauf-api.service';
import { describeProblem, pathKey } from '../core/field-problems';
import { StudioApiError } from '../core/studio-api-error';
import { StudioFormat } from '../i18n/studio-format.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { probeHref } from '../views/probe-start';
import { schrittFolge } from './ablauf-folge';
import { AblaufDatenComponent } from './ablauf-daten.component';
import { AblaufSchrittfolgeComponent } from './ablauf-schrittfolge.component';
import { FORM_BEFUNDE, type FormBefund } from './form-befunde';
import { FORM_EPOCHE } from './form-epoche';
import type { ValuePath } from './form-value';

/** `alt`: seit der Prüfung geändert — fest gemerkt, damit nicht jede weitere Änderung den ganzen
 *  Ablauf noch einmal serialisiert (Review K2c-4, Befund 8). */
type Stand = { readonly geprueft: string; readonly alt?: boolean } & (
  | { readonly art: 'befunde'; readonly befunde: readonly AblaufBefund[];
      readonly warnungen: readonly string[]; readonly teile: readonly AblaufTeil[] }
  | { readonly art: 'form'; readonly meldungen: readonly { readonly ort: string; readonly text: string }[] }
  | { readonly art: 'fehler'; readonly text: string });

@Component({
  selector: 'studio-ablauf-pruefen',
  imports: [AblaufDatenComponent, AblaufSchrittfolgeComponent],
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
      <!-- AS-8b: dieselbe Kennung in der Vorschau ausprobieren (gespeicherte Fassung, Trockenlauf) -->
      @if (probeLink(); as href) {
        <p class="ap-probe-zeile">
          <a class="ap-probe" [href]="href" (click)="zurProbe($event)"
            [attr.aria-describedby]="idBasis() + '-probe-hinweis'">{{ t('ablaufPruefen.ausprobieren') }}</a>
          <span class="ap-probe-hinweis" [id]="idBasis() + '-probe-hinweis'">{{
            t('ablaufPruefen.ausprobierenHinweis') }}</span>
        </p>
      }
      @if (gueltig(); as s) {
        @if (s.art === 'befunde' && ablaufBefunde().length) {
          <ul class="ap-befunde">
            @for (text of ablaufBefunde(); track $index) { <li class="sf-error">{{ text }}</li> }
          </ul>
        }
        @if (s.art === 'befunde' && s.warnungen.length) {
          <!-- AS-0: Hinweise ohne Sperre (dieselbe Wendung in einem anderen aktiven Ablauf);
               seit AS-Db auch zum Datenfluss (Teil entsteht später oder kommt aus dem Gespräch). -->
          <ul class="ap-befunde" [attr.aria-label]="t('ablaufPruefen.warnungen')">
            @for (text of s.warnungen; track $index) {
              <li>{{ t('ablaufPruefen.warnung', { text }) }}</li>
            }
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
      <!-- AS-1: die Testfälle des Ablaufs, mit dem echten Treiber simuliert (ohne LLM, MCP, Auftrag). -->
      <div class="ap-tests">
        @if (testZahl()) {
          <div class="ap-kopf">
            <button type="button" class="sf-add" [id]="idBasis() + '-tests'"
              [attr.aria-disabled]="testLaeuft() ? 'true' : null" (click)="testen()">
              {{ t('ablaufTesten.knopf') }}
            </button>
            <p class="ap-test-status live" role="status">{{ testStatus() }}</p>
          </div>
          @if (testErgebnisse(); as ergebnisse) {
            <ul class="ap-befunde">
              @for (e of ergebnisse; track $index) {
                <li class="ap-test" [class.sf-error]="!e.ok">
                  {{ t(e.ok ? 'ablaufTesten.bestanden' : 'ablaufTesten.abweichung', { name: e.name }) }}
                  @if (!e.ok) {
                    <ul>
                      @for (a of e.abweichungen; track $index) { <li>{{ a }}</li> }
                    </ul>
                  }
                  @if (e.texte?.length) {
                    <!-- AS-3b: was der Lauf sagte, mit eingesetzten Platzhaltern -->
                    <details class="ap-texte">
                      <summary>{{ lang.plural('ablaufTesten.texte', e.texte!.length) }}</summary>
                      <ol>
                        @for (text of e.texte; track $index) { <li>{{ lesbar(text) }}</li> }
                      </ol>
                    </details>
                  }
                </li>
              }
            </ul>
          }
        } @else {
          <p class="sf-desc">{{ t('ablaufTesten.keine') }}</p>
        }
      </div>
      <studio-ablauf-schrittfolge [folge]="folge()" [pfad]="pfad()" [befunde]="schrittBefunde()" />
      <!-- AS-Dc: die Sicht „Daten“ — mit „Prüfen“ gerechnet, solange sie zum Entwurf passt -->
      <studio-ablauf-daten [teile]="datenTeile()" [folge]="folge()" [pfad]="pfad()" />
    </div>
  `,
})
export class AblaufPruefenComponent {
  protected readonly lang = inject(StudioLanguageService);
  protected readonly lesbar = ohneMarkdownEscapes;
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
  /** AS-1: der Stand von „Tests ausführen“ — für genau den Entwurf, der geschickt wurde. */
  readonly testLaeuft = signal(false);
  private readonly testStand = signal<{ readonly geprueft: string; readonly ergebnisse?: readonly AblaufTestErgebnis[];
                                         readonly fehler?: string } | null>(null);
  private testAnfrage = 0;
  private readonly stand = signal<Stand | null>(null);
  /** Nummer der jüngsten Anfrage — eine ältere Antwort gilt nicht, und ein Wechsel des Ablaufs gibt
   *  den Knopf sofort frei (Review K2c-4, Befund 5). */
  private anfrage = 0;
  /** Unter welcher Quelle die Befunde im Formular stehen (der Pfad zur Zeit der Prüfung). */
  private quelle: string | null = null;

  readonly folge = computed(() => schrittFolge(this.wert()));
  /** AS-8b: der Weg in die Vorschau mit diesem Ablauf — nur mit Kennung. */
  readonly probeLink = computed(() => probeHref((this.wert() as { id?: unknown } | null | undefined)?.id));
  private readonly router = inject(Router, { optional: true });
  private readonly jetzt = computed(() => JSON.stringify(this.wert() ?? null));
  readonly veraltet = computed(() => {
    const s = this.stand();
    return s !== null && (s.alt === true || s.geprueft !== this.jetzt());
  });
  readonly testZahl = computed(() => {
    const tests = (this.wert() as { tests?: unknown } | null | undefined)?.tests;
    return Array.isArray(tests) ? tests.length : 0;
  });
  /** Die Ergebnisse, solange sie zum Entwurf passen. */
  readonly testErgebnisse = computed(() => {
    const s = this.testStand();
    return s && s.geprueft === this.jetzt() ? (s.ergebnisse ?? null) : null;
  });
  readonly testStatus = computed(() => {
    if (this.testLaeuft()) return this.t('ablaufTesten.laeuft');
    const s = this.testStand();
    if (!s) return '';
    if (s.geprueft !== this.jetzt()) return this.t('ablaufTesten.veraltet');
    if (s.fehler !== undefined) return this.t('ablaufTesten.fehler', { detail: s.fehler });
    const alle = s.ergebnisse ?? [];
    const gut = alle.filter((e) => e.ok).length;
    return this.lang.plural('ablaufTesten.zusammen', alle.length, { gut, abweichend: alle.length - gut });
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
        if (s.befunde.length) return this.lang.plural('ablaufPruefen.befunde', s.befunde.length);
        // Review AS-0, Befund 6: Hinweise ohne Befund — die Live-Region sagt es auch an.
        return s.warnungen.length
          ? this.lang.plural('ablaufPruefen.okMitHinweisen', s.warnungen.length)
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

  /** AS-Dc: die Sicht „Daten“ der gültigen Prüfung. */
  readonly datenTeile = computed<readonly AblaufTeil[] | null>(() => {
    const s = this.gueltig();
    return s?.art === 'befunde' ? s.teile : null;
  });

  /** Die Befunde der gültigen Prüfung je Stelle in `schritte` — für die Schrittfolge. */
  readonly schrittBefunde = computed<ReadonlyMap<number, readonly string[]>>(() => {
    const s = this.gueltig();
    const je = new Map<number, string[]>();
    if (s?.art === 'befunde') {
      for (const b of s.befunde) if (b.nr !== null) je.set(b.nr, [...(je.get(b.nr) ?? []), b.text]);
    }
    return je;
  });

  async testen(): Promise<void> {
    if (this.testLaeuft()) return;
    const wert = this.wert() ?? null;
    const geprueft = JSON.stringify(wert);
    const nummer = ++this.testAnfrage;
    this.testLaeuft.set(true);
    try {
      const ergebnisse = await this.api.testen(wert);
      if (nummer === this.testAnfrage) this.testStand.set({ geprueft, ergebnisse });
    } catch (err) {
      if (nummer !== this.testAnfrage) return;
      const problems = err instanceof StudioApiError && err.status === 422 ? err.problems : [];
      const text = problems.length
        ? problems.map((p) => `${pathKey(p.path[0] === 'body' ? p.path.slice(1) : p.path)}: ${describeProblem(p, this.t, this.format.decimal)}`).join('; ')
        // Querschnitts-Review AS-0…AS-2, Befund 9: der Grund statt eines nackten 413
        : err instanceof StudioApiError && err.status === 413 ? this.t('ablaufTesten.zuGross')
        : err instanceof StudioApiError ? err.detail : String(err);
      this.testStand.set({ geprueft, fehler: text });
    } finally {
      if (nummer === this.testAnfrage) this.testLaeuft.set(false);
    }
  }

  async pruefen(): Promise<void> {
    if (this.laeuft()) return;
    const wert = this.wert() ?? null;
    const pfad = this.pfad();
    const geprueft = JSON.stringify(wert);
    const nummer = ++this.anfrage;
    this.laeuft.set(true);
    try {
      const { befunde, warnungen, teile } = await this.api.pruefen(wert);
      if (this.verpasst(nummer, geprueft)) return;
      this.stand.set({ art: 'befunde', geprueft, befunde, warnungen, teile: teile ?? [] });
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
    // Review AS-1, Befund 8: auch der Testlauf gehört zum alten Ablauf
    this.testStand.set(null);
    this.testAnfrage += 1;
    this.testLaeuft.set(false);
  }

  /** Im Studio ohne Neuladen — die Adresse bleibt für „in neuem Tab öffnen“. */
  zurProbe(event: MouseEvent): void {
    const id = (this.wert() as { id?: unknown } | null | undefined)?.id;
    if (!this.router || typeof id !== 'string' || event.ctrlKey || event.metaKey || event.shiftKey
        || event.button !== 0) return;
    event.preventDefault();
    void this.router.navigate(['/vorschau'], { queryParams: { ablauf: id } });
  }
}
