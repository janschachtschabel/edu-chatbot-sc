/**
 * Skill-Verzeichnis (ST-8c) — welche Skills eine Sammlung für den Agenten
 * freigibt, aus ihrem Registry-Dokument im Repositorium. Dazu die Suche per
 * Suchbegriff (Paket F3), sofern der MCP-Server `search_skill` anbietet, und je
 * Skill ein Link in den md-editor des Repositoriums (Paket F2).
 *
 * Auf Anfrage statt beim Aufklappen: jede Sammlung hat ihr eigenes Verzeichnis,
 * und jeder Abruf geht an den MCP. Kennung und Suchbegriff werden vorher geprüft
 * wie auf dem Server (`api/agent_center.py`) — die Meldung steht am Feld statt
 * als 422 nach dem Umweg über den Server.
 *
 * Titel, Beschreibungen und Stichworte sind Repositoriumstext: Angular setzt sie
 * als Text ein, nie als HTML.
 */
import {
  ChangeDetectionStrategy, Component, ElementRef, Injector, afterNextRender, computed, inject, input,
  signal, viewChild,
} from '@angular/core';

import {
  AgentCenterApi, type SkillDirectory, type SkillEntry, type SkillSearch,
} from '../core/agent-center-api.service';
import { describeApiError } from '../core/async-data';
import { StudioLanguageService } from '../i18n/studio-language.service';
import type { CuratedPanelSection } from './curated-views';

const KENNUNG = /^[A-Za-z0-9-]{1,64}$/;

/** Wie `search_skill` auf dem MCP-Server (`query` höchstens 200 Zeichen). */
const SUCHBEGRIFF_MAX = 200;

type Suchart = 'collection' | 'term';

/** Die Gründe des MCP-Servers (`RegistryMiss`); ein neuer kommt roh durch. */
const REASON_KEYS: ReadonlyMap<string, string> = new Map([
  ['no_registry', 'agentSkills.reason.no_registry'],
  ['collection_not_found', 'agentSkills.reason.collection_not_found'],
  ['unreadable', 'agentSkills.reason.unreadable'],
]);

@Component({
  selector: 'studio-agent-skills',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './agent-skills.component.html',
  styleUrl: './agent-skills.component.scss',
})
export class AgentSkillsComponent {
  private readonly api = inject(AgentCenterApi);
  private readonly lang = inject(StudioLanguageService);
  protected readonly t = this.lang.t;
  protected readonly plural = this.lang.plural;
  protected readonly list = this.lang.list;

  private readonly injector = inject(Injector);
  private readonly collectionField = viewChild<ElementRef<HTMLInputElement>>('collectionField');
  private readonly suchform = viewChild<ElementRef<HTMLFormElement>>('suchform');

  readonly section = input.required<CuratedPanelSection>();
  readonly open = input(false);

  readonly mode = signal<Suchart>('collection');
  /** Je Suchart die eigene Eingabe: ein Wechsel verliert nichts. */
  readonly collection = signal('');
  readonly term = signal('');
  readonly fieldError = signal('');
  readonly loading = signal(false);
  readonly error = signal('');
  readonly result = signal<SkillDirectory | null>(null);
  readonly found = signal<SkillSearch | null>(null);
  /**
   * Die Einträge, die gerade zu zeigen sind. Suche und Verzeichnis sind nie
   * zugleich gesetzt (`abrufen` leert beide) — so gibt es EINE Liste, und die
   * Vorlage prüft ihre Felder gegen `SkillEntry` (Review 2026-09-29: der
   * Kontext einer `ng-template` war `any`).
   */
  readonly eintraege = computed<readonly SkillEntry[]>(
    () => this.found()?.entries ?? this.result()?.entries ?? []);
  /** Der MCP-Server bietet `search_skill` nicht an — gemerkt, solange diese Ansicht besteht. */
  readonly searchOff = signal(false);
  readonly status = signal('');

  setMode(art: Suchart): void {
    this.mode.set(art);
    this.fieldError.set('');
  }

  onInput(event: Event): void {
    const wert = (event.target as HTMLInputElement).value;
    (this.mode() === 'term' ? this.term : this.collection).set(wert);
  }

  submit(): Promise<void> {
    return this.mode() === 'term' ? this.search() : this.lookup();
  }

  async lookup(): Promise<void> {
    if (this.loading()) return;
    const kennung = this.collection().trim();
    if (!kennung || !KENNUNG.test(kennung)) {
      this.fieldError.set(this.t(kennung ? 'agentSkills.error.format' : 'agentSkills.error.empty'));
      return;
    }
    await this.abrufen(async () => {
      this.result.set(await this.api.skills(kennung));
      this.status.set(this.t('agentSkills.loaded'));
    });
  }

  async search(): Promise<void> {
    if (this.loading()) return;
    const begriff = this.term().trim();
    if (!begriff || begriff.length > SUCHBEGRIFF_MAX) {
      this.fieldError.set(begriff
        ? this.t('agentSkills.error.termLong', { max: SUCHBEGRIFF_MAX })
        : this.t('agentSkills.error.termEmpty'));
      return;
    }
    await this.abrufen(async () => {
      const antwort = await this.api.searchSkills(begriff);
      if (!antwort.available) {
        // Ein Zustand des Servers, kein Fehler: ehrlich sagen und zur Suche per
        // Sammlungs-ID führen, statt eine leere Trefferliste zu zeigen.
        this.searchOff.set(true);
        this.mode.set('collection');
        this.status.set(this.t('agentSkills.searchOff'));
        return;
      }
      this.found.set(antwort);
      // Das Ergebnis steht EINMAL — in der Statuszeile, sichtbar und vorgelesen.
      this.status.set(antwort.entries.length > 0
        ? this.plural('agentSkills.found', antwort.entries.length)
        : this.t('agentSkills.noHits', { query: antwort.query }));
    });
  }

  /** Ohne Registry: warum. Ohne Grund heißt es „kein Dokument“ (so antwortet der MCP). */
  reasonText(reason: string | null): string {
    const key = REASON_KEYS.get(reason ?? 'no_registry');
    return key ? this.t(key) : this.t('agentSkills.reason.unknown', { reason: reason ?? '' });
  }

  private async abrufen(aufgabe: () => Promise<void>): Promise<void> {
    this.fieldError.set('');
    this.error.set('');
    this.status.set('');
    // Das alte Ergebnis weg, bevor das neue kommt: sonst stünde während des
    // Abrufs die Liste einer anderen Sammlung oder Suche da.
    this.result.set(null);
    this.found.set(null);
    this.loading.set(true);
    try {
      await aufgabe();
    } catch (err) {
      this.error.set(describeApiError(err, this.t));
    } finally {
      this.loading.set(false);
      // Der Knopf war gesperrt und hat den Fokus verloren; weiter geht es im Feld —
      // aber nur dann: wer inzwischen woanders arbeitet, behält seinen Platz.
      afterNextRender(() => {
        const aktiv = document.activeElement;
        if (!aktiv || aktiv === document.body || this.suchform()?.nativeElement.contains(aktiv)) {
          this.collectionField()?.nativeElement.focus();
        }
      }, { injector: this.injector });
    }
  }
}
