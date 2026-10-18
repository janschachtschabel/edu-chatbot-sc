/**
 * Der Vergleich mit dem Judge v2 (Paket 13, F8): Noten je Maschine und was zwischen den Läufen
 * anders war (`compare.bewertung_je_maschine`, `compare.unterschiede`, D4).
 *
 * Ohne die Unterschiede läse man eine bessere Note als Verbesserung, obwohl nur Modell,
 * Konfiguration oder Master-Skill wechselten. Ein geänderter Prompt-Baustein lässt sich als
 * Text-Unterschied aufklappen (`GET /api/eval/prompt-diff`, erst auf Wunsch geladen: der
 * Master-Skill ist lang). Ein älteres Backend schickt beides nicht — dann bleibt die
 * Komponente leer.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input, signal } from '@angular/core';

import { describeApiError } from '../core/async-data';
import { EvalApi } from '../core/eval-api.service';
import type { EngineComparison } from '../core/eval-profile';
import { StudioFormat } from '../i18n/studio-format.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { engineLabel } from './engine-label';

const SKALEN = ['zielgruppe', 'anliegen', 'angebot', 'werkzeuge', 'verlauf', 'qualitaet', 'sicherheit'];

type DiffStand =
  | { readonly art: 'laden' }
  | { readonly art: 'fehler'; readonly grund: string }
  | { readonly art: 'da'; readonly zeilen: readonly { text: string; klasse: string }[] };

function klasse(zeile: string): string {
  if (zeile.startsWith('+++') || zeile.startsWith('---') || zeile.startsWith('@@')) return 'vg-kopf';
  if (zeile.startsWith('+')) return 'vg-neu';
  if (zeile.startsWith('-')) return 'vg-weg';
  return '';
}

@Component({
  selector: 'studio-eval-vergleich-v2',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './eval-vergleich-v2.component.html',
  styleUrl: './eval-vergleich-v2.component.scss',
})
export class EvalVergleichV2Component {
  protected readonly t = inject(StudioLanguageService).t;
  private readonly fmt = inject(StudioFormat);
  private readonly api = inject(EvalApi);

  readonly vergleich = input.required<EngineComparison>();

  /** Je Schlüssel `<lauf>|<art>` der geladene Text-Unterschied. */
  readonly diffs = signal<Readonly<Record<string, DiffStand>>>({});

  readonly noten = computed(() => {
    const je = this.vergleich().bewertung_je_maschine ?? {};
    const maschinen = Object.entries(je);
    if (maschinen.length === 0) return null;
    const vorhanden = new Set(maschinen.flatMap(([, b]) => Object.keys(b.skalen_mittel ?? {})));
    const skalen = SKALEN.filter((s) => vorhanden.has(s));
    const zahl = (n: number | null | undefined): string =>
      (n === null || n === undefined ? this.t('evalV2.vgl.ohne') : this.fmt.decimal(n));
    return {
      skalen: skalen.map((s) => this.t(`evalV2.skala.${s}`)),
      zeilen: maschinen.map(([maschine, b]) => ({
        maschine: engineLabel(maschine, this.t),
        laeufe: String(b.laeufe ?? '—'),
        werte: [zahl(b.gesamt_mittel), zahl(b.zug_mittel),
          ...skalen.map((s) => zahl(b.skalen_mittel?.[s]))],
      })),
    };
  });

  readonly unterschiede = computed(() => {
    const u = this.vergleich().unterschiede;
    if (!u?.referenz) return null;
    const wert = (v: unknown): string =>
      (v === null || v === undefined || v === '' ? this.t('evalV2.vgl.ohne') : String(v));
    const laeufe = u.laeufe.map((lauf) => ({
      run: lauf.run,
      punkte: [
        ...lauf.felder.map((f) => this.t('evalV2.vgl.feld', {
          feld: this.t(`evalV2.feld.${f.feld}`), a: wert(f.a), b: wert(f.b),
        })),
        ...(lauf.bereiche.length
          ? [this.t('evalV2.vgl.bereiche', { liste: lauf.bereiche.join(', ') })] : []),
      ],
      prompts: lauf.prompts.map((p) => {
        // Je Baustein sortierte Prüfsummen (ein Lauf kann mehrere Fassungen tragen): verglichen
        // wird die, die nur A hat, mit der, die nur B hat — a[0] gegen b[0] traf oft dieselbe
        // (Review PR #18). Fehlt eine Seite, gibt es nichts zu vergleichen.
        const a = p.a.find((h) => !p.b.includes(h)) ?? '';
        const b = p.b.find((h) => !p.a.includes(h)) ?? '';
        return { art: p.art, a, b, schluessel: `${a}|${b}` };
      }),
    }));
    return {
      referenz: u.referenz,
      laeufe,
      keine: laeufe.every((l) => l.punkte.length === 0 && l.prompts.length === 0),
    };
  });

  async zeigeDiff(schluessel: string, a: string, b: string): Promise<void> {
    // Ein Fehler lässt sich erneut versuchen; geladen oder ladend nicht (Review PR #18).
    const stand = this.diffs()[schluessel];
    if (!a || !b || (stand && stand.art !== 'fehler')) return;
    this.setze(schluessel, { art: 'laden' });
    try {
      const diff = await this.api.promptDiff(a, b);
      this.setze(schluessel, {
        art: 'da', zeilen: diff.diff.map((text) => ({ text, klasse: klasse(text) })),
      });
    } catch (err) {
      this.setze(schluessel, { art: 'fehler', grund: describeApiError(err, this.t) });
    }
  }

  private setze(schluessel: string, stand: DiffStand): void {
    this.diffs.update((alle) => ({ ...alle, [schluessel]: stand }));
  }
}
