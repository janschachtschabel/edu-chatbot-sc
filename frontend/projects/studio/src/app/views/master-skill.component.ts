/**
 * Der Master-Skill des Agent-Modus (AG-2) — anzeigen, nicht bearbeiten.
 *
 * Nutzer-Entscheid 2026-09-26: er bleibt im edu-sharing-Repositorium, „das ist
 * so gewollt". Das Panel zeigt, was gilt, und verweist zum Bearbeiten auf den
 * Knoten. „Neu laden" wartet den nächsten Takt des Backends nicht ab.
 *
 * Der Wortlaut steht als reiner Text im `<pre>`: er kommt aus dem Repositorium,
 * und eine Anzeige, die ihn als Markdown oder HTML deutete, hinge an fremdem
 * Inhalt.
 */
import {
  ChangeDetectionStrategy, Component, computed, effect, inject, input, signal,
} from '@angular/core';

import { describeApiError } from '../core/async-data';
import { StudioApi } from '../core/studio-api.service';
import { StudioFormat } from '../i18n/studio-format.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import type { CuratedPanelSection } from './curated-views';

/** Antwort von `GET /api/master-skill` (`schemas_agent.MasterSkillStatus`). */
export interface MasterSkillStatus {
  enabled: boolean;
  node_id: string;
  cached: boolean;
  fetched_at: string | null;
  length: number | null;
  sha256: string | null;
  last_error: string | null;
  ttl_seconds: number;
  text: string | null;
  /** Der md-editor des Repositoriums (Paket F); bis 2026-09-29 die Render-Seite. */
  edit_url: string | null;
  /** Die Render-Seite des Knotens — zum Ansehen. */
  view_url: string | null;
}

@Component({
  selector: 'studio-master-skill',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './master-skill.component.html',
  styleUrl: './master-skill.component.scss',
})
export class MasterSkillComponent {
  private readonly api = inject(StudioApi);
  private readonly lang = inject(StudioLanguageService);
  protected readonly t = this.lang.t;
  protected readonly plural = this.lang.plural;
  protected readonly fmt = inject(StudioFormat);

  readonly section = input.required<CuratedPanelSection>();
  readonly open = input(false);

  readonly skill = signal<MasterSkillStatus | null>(null);
  readonly loading = signal(true);
  readonly loadError = signal('');
  readonly reloading = signal(false);
  readonly reloadError = signal('');
  readonly status = signal('');

  /** Zwölf Stellen reichen, um zwei Stände zu unterscheiden. */
  readonly shortSum = computed(() => (this.skill()?.sha256 ?? '').slice(0, 12));
  readonly minutes = computed(() => Math.round((this.skill()?.ttl_seconds ?? 0) / 60));

  private loaded = false;

  constructor() {
    effect(() => {
      if (this.open()) this.ensureLoaded();
    });
  }

  onToggle(event: Event): void {
    if ((event.target as HTMLDetailsElement).open) this.ensureLoaded();
  }

  private ensureLoaded(): void {
    if (this.loaded) return;
    this.loaded = true;
    void this.load();
  }

  async load(): Promise<void> {
    this.loading.set(true);
    this.loadError.set('');
    try {
      this.skill.set(await this.api.get<MasterSkillStatus>('/master-skill'));
    } catch (err) {
      this.loadError.set(describeApiError(err, this.t));
    } finally {
      this.loading.set(false);
    }
  }

  async reload(): Promise<void> {
    if (this.reloading()) return;
    this.reloading.set(true);
    this.reloadError.set('');
    this.status.set('');
    try {
      const skill = await this.api.post<MasterSkillStatus>('/master-skill/reload', null);
      this.skill.set(skill);
      // Ein gescheiterter Abruf kommt ebenfalls mit 200 — der Grund steht in
      // `last_error`, und dann darf der Knopf keinen Erfolg melden.
      if (skill.last_error) {
        this.reloadError.set(this.t('masterSkill.reloadFailed', { error: skill.last_error }));
      } else {
        this.status.set(this.t('masterSkill.reloaded'));
      }
    } catch (err) {
      this.reloadError.set(describeApiError(err, this.t));
    } finally {
      this.reloading.set(false);
    }
  }
}
