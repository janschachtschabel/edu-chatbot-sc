/**
 * „Agent testen" — ein Formular auf `POST /api/agent`, und darunter, was
 * herauskam (2026-08-13).
 *
 * Der Nutzer wollte „eine Seite zum Testen des Endpunkts, wo man Formularfelder
 * hat, um die Anfrage zu machen und den Output sieht". Bis dahin liess sich der
 * Agent-Endpunkt nur mit einem HTTP-Werkzeug und dem Admin-Schlüssel von Hand
 * rufen — und wer den Schlüssel in einem Browser-Reiter hält, hat ihn dort auch
 * liegen.
 *
 * Das Formular-Bauen liegt in `agent-request.ts`, prüfbar ohne DOM. Hier bleibt
 * nur: Felder halten, Fehler zeigen, Lauf auslösen, Ergebnis anzeigen.
 *
 * **Der Knopf sagt vorher, was er kostet.** Ein Lauf fährt die echte Schleife
 * (bis zu `max_iterations` LLM-Runden plus Werkzeuge), also dieselbe Klasse wie
 * der Lasttest. Ein Formular, das aussieht wie eine Suche, aber wie ein Lauf
 * abrechnet, ist eine Falle.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input, signal } from '@angular/core';

import { AgentApi, type AgentResult, describeAgentError } from '../core/agent-api.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { buildAgentRequest } from './agent-request';
import type { CuratedPanelSection } from './curated-views';

/**
 * Die Schreib-Wahl. `''` heisst „die Vorgabe aus `01-base/engine`" — das ist
 * etwas anderes als `propose` und muss unterscheidbar bleiben: wer die Vorgabe
 * im Bereich ändert, will sie hier wirken sehen.
 */
const WRITE_MODES: readonly { readonly id: string; readonly labelKey: string }[] = [
  { id: '', labelKey: 'agent.write.default' },
  { id: 'propose', labelKey: 'agent.write.propose' },
  { id: 'execute', labelKey: 'agent.write.execute' },
];

const LOCALES: readonly { readonly id: string; readonly labelKey: string }[] = [
  { id: '', labelKey: 'agent.locale.default' },
  { id: 'de', labelKey: 'agent.locale.de' },
  { id: 'en', labelKey: 'agent.locale.en' },
];

@Component({
  selector: 'studio-agent-tester',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './agent-tester.component.html',
  styleUrl: './agent-tester.component.scss',
})
export class AgentTesterComponent {
  private readonly agent = inject(AgentApi);
  private readonly lang = inject(StudioLanguageService);
  protected readonly t = this.lang.t;

  readonly section = input.required<CuratedPanelSection>();
  readonly open = input(false);

  readonly writeModes = WRITE_MODES;
  readonly locales = LOCALES;

  readonly instruction = signal('');
  readonly collectionId = signal('');
  readonly nodeIds = signal('');
  readonly resultSchema = signal('');
  readonly writeMode = signal('');
  readonly locale = signal('');
  /** Vorgabe wie im Backend (`AgentRequest.allow_curation = True`). */
  readonly allowCuration = signal(true);

  readonly running = signal(false);
  readonly error = signal('');
  readonly result = signal<AgentResult | null>(null);

  /** Eindeutiges Präfix, damit `<label for>` auch neben anderen Panels trifft. */
  readonly idPrefix = 'at';

  /**
   * Der eine Satz, den die Live-Region ansagt.
   *
   * Ein SATZ, nicht der Ergebnisblock: der steht darunter zum Nachlesen und ist
   * über seine Überschrift erreichbar. Eine Live-Region, die eine Definitionsliste
   * plus Antworttext plus JSON vorliest, sagt weniger als eine, die „fertig" sagt.
   */
  readonly liveStatus = computed(() => {
    if (this.running()) return this.t('agent.running');
    return this.result() ? this.t('agent.result.ready') : '';
  });

  /** Das Ergebnis-JSON, eingerückt — `null`, wenn der Lauf keines lieferte. */
  readonly resultJson = computed(() => {
    const roh = this.result()?.result;
    if (roh === null || roh === undefined) return null;
    return JSON.stringify(roh, null, 2);
  });

  onField(feld: 'instruction' | 'collectionId' | 'nodeIds' | 'resultSchema', event: Event): void {
    const ziel = event.target as HTMLInputElement | HTMLTextAreaElement;
    this[feld].set(ziel.value);
  }

  onSelect(feld: 'writeMode' | 'locale', event: Event): void {
    this[feld].set((event.target as HTMLSelectElement).value);
  }

  onCuration(event: Event): void {
    this.allowCuration.set((event.target as HTMLInputElement).checked);
  }

  async run(): Promise<void> {
    const { request, error } = buildAgentRequest({
      instruction: this.instruction(),
      collectionId: this.collectionId(),
      nodeIds: this.nodeIds(),
      resultSchema: this.resultSchema(),
      writeMode: this.writeMode(),
      locale: this.locale(),
      allowCuration: this.allowCuration(),
    });
    if (!request) {
      this.error.set(this.t(error ?? 'agent.error.instruction'));
      return;
    }
    this.error.set('');
    // Das alte Ergebnis WEG, bevor der neue Lauf startet: sonst stünde während
    // eines zweiten Laufs das Ergebnis des ersten da, und niemand sähe, welches
    // gerade gilt.
    this.result.set(null);
    this.running.set(true);
    try {
      this.result.set(await this.agent.run(request));
    } catch (e) {
      this.error.set(describeAgentError(e, this.lang.t));
    } finally {
      this.running.set(false);
    }
  }
}
