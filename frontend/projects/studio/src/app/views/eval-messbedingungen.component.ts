/**
 * Womit ein Lauf maß (Paket 13, F2): Maschine, Modell und Weg, Judge samt Fassung,
 * App-, Konfigurations-, Master-Skill- und Golden-Stand.
 *
 * Aufklappbar, weil es Nachschlagewissen ist. Erst beim Aufklappen fragt die Komponente die
 * Trends ihrer Maschine nach der Wechselmarke dieses Laufs (`trends.v2.wechsel`, D5): was sich
 * gegenüber dem vorigen Lauf derselben Maschine änderte. Ohne die Antwort läse man eine
 * gestiegene Note als Verbesserung, obwohl nur das Modell wechselte.
 */
import {
  ChangeDetectionStrategy, Component, computed, inject, input, signal,
} from '@angular/core';

import { describeApiError } from '../core/async-data';
import { EvalApi, type EngineFilter } from '../core/eval-api.service';
import type { LlmWeg, Messbedingungen } from '../core/eval-auswertung';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { engineLabel } from './engine-label';

type Wechselstand =
  | { readonly art: 'zu' | 'laden' | 'keine' | 'erster' | 'unbekannt' }
  | { readonly art: 'fehler'; readonly grund: string }
  | { readonly art: 'liste'; readonly punkte: readonly string[] };

const DENK = ['reasoning_effort', 'verbosity', 'service_tier'] as const;

@Component({
  selector: 'studio-eval-messbedingungen',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './eval-messbedingungen.component.html',
  styleUrl: './eval-messbedingungen.component.scss',
})
export class EvalMessbedingungenComponent {
  protected readonly t = inject(StudioLanguageService).t;
  private readonly api = inject(EvalApi);

  readonly mb = input.required<Messbedingungen>();
  readonly fassung = input('');
  readonly runId = input.required<string>();
  /** Die Maschine des Laufs (`run.engine`) — die Trends werden auf sie gefiltert. */
  readonly engine = input('');

  readonly wechsel = signal<Wechselstand>({ art: 'zu' });

  readonly zeilen = computed(() => {
    const mb = this.mb();
    const skill = mb.master_skill;
    const gold = mb.gold_flows;
    const ohne = this.t('evalV2.mb.ohne');
    return [
      { label: 'evalV2.mb.maschine', wert: mb.maschine ? engineLabel(mb.maschine, this.t) : ohne },
      { label: 'evalV2.mb.chat', wert: mb.weg ? this.weg(mb.weg) : mb.chat_model || ohne },
      { label: 'evalV2.mb.judge',
        wert: mb.judge_weg ? this.weg(mb.judge_weg) : this.t('evalV2.mb.ohneJudge') },
      { label: 'evalV2.mb.fassung', wert: this.fassung() || ohne },
      { label: 'evalV2.mb.app',
        wert: [mb.app?.version, mb.app?.commit].filter(Boolean).join(' · ') || ohne },
      { label: 'evalV2.mb.konfiguration',
        wert: mb.konfiguration?.hash || mb.konfiguration?.fehler || ohne },
      { label: 'evalV2.mb.masterSkill', wert: !skill ? ohne : skill.enabled === false
        ? this.t('evalV2.mb.masterSkillAus')
        : this.t('evalV2.mb.masterSkillAn', { hash: (skill.sha256 ?? '').slice(0, 12) || ohne }) },
      { label: 'evalV2.mb.gold', wert: gold?.hash
        ? this.t('evalV2.mb.goldWert', { hash: gold.hash, anzahl: gold.ids?.length ?? 0 })
        : ohne },
    ];
  });

  private weg(weg: LlmWeg): string {
    const teile = [weg.anbieter, weg.modell, weg.api].filter((x): x is string => !!x);
    for (const k of DENK) if (weg[k]) teile.push(`${k}=${weg[k]}`);
    return teile.join(' · ') || this.t('evalV2.mb.ohne');
  }

  /** Beim ersten Aufklappen die Wechselmarke lesen; danach steht sie. */
  async aufgeklappt(event: Event): Promise<void> {
    if (!(event.target as HTMLDetailsElement).open || this.wechsel().art !== 'zu') return;
    this.wechsel.set({ art: 'laden' });
    const engine = this.engine();
    const filter: EngineFilter = engine === 'pattern' || engine === 'agent' ? engine : '';
    try {
      const trends = await this.api.trends(filter);
      const ids = (trends.runs ?? []).map((run) => run.id);
      const eigene = trends.v2?.wechsel.find((w) => w.run_id === this.runId());
      if (eigene) {
        this.wechsel.set({ art: 'liste', punkte: [
          ...eigene.felder.map((feld) => this.t(`evalV2.feld.${feld}`)),
          ...eigene.prompts.map((art) => this.t('evalV2.wechsel.prompt', { art })),
        ] });
      } else if (!ids.includes(this.runId())) {
        this.wechsel.set({ art: 'unbekannt' });
      } else {
        this.wechsel.set({ art: ids[0] === this.runId() ? 'erster' : 'keine' });
      }
    } catch (err) {
      this.wechsel.set({ art: 'fehler', grund: describeApiError(err, this.t) });
    }
  }
}
