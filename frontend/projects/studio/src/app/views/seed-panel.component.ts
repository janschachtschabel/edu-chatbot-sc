/**
 * Der Auslieferungsstand aus dem Abbild (S4, `api/config_snapshots.py` `/seed`).
 *
 * **Warum eine eigene Karte und nicht ein fünfter Knopf im Werksstand-Panel:**
 * die beiden beantworten verschiedene Fragen. Der Werksstand ist eine
 * Momentaufnahme des *gelebten* Standes, dieser hier der Stand, mit dem das
 * Abbild gebaut wurde. Zusammengelegt hiesse das: fünf Knöpfe auf zwei Quellen,
 * und niemand wüsste mehr, welcher woher liest.
 *
 * **Zwei Knöpfe, und nur einer ist harmlos.** „Fehlende nachziehen" fasst
 * Bestehendes nicht an. „Alles auf Auslieferungsstand" überschreibt gepflegte
 * Bereiche und löscht, was nur in der Datenbank steht — deshalb hinter einer
 * Rückfrage, deren Text beide Folgen nennt. Das Backend legt vorher selbst einen
 * Schnappschuss an; die Meldung danach sagt, wo er liegt.
 *
 * **Die Zählung entscheidet, ob die Knöpfe überhaupt etwas tun können.** Sie
 * kommt aus derselben Leseroutine, die der Knopf danach benutzt
 * (`services/seed_sync.py`) — eine zweite Quelle würde zeigen, was nicht
 * passiert.
 */
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';

import { ActionState } from '../core/action-state';
import { AsyncData } from '../core/async-data';
import { SnapshotsApi, type SeedStatus } from '../core/snapshots-api.service';
import { StudioLanguageService } from '../i18n/studio-language.service';

@Component({
  selector: 'studio-seed-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './seed-panel.component.html',
  styleUrl: './seed-panel.component.scss',
})
export class SeedPanelComponent {
  private readonly api = inject(SnapshotsApi);
  private readonly lang = inject(StudioLanguageService);
  protected readonly t = this.lang.t;

  readonly status = new AsyncData<SeedStatus>(() => this.api.seed(), this.t);
  readonly action = new ActionState(this.t);

  /** Nur der scharfe Weg wird scharfgeschaltet — der harmlose braucht es nicht. */
  readonly armed = signal(false);

  readonly available = computed(() => this.status.value()?.available === true);
  readonly counts = computed(() => {
    const s = this.status.value();
    return {
      areas: s?.area_count ?? 0,
      gleich: s?.gleich.length ?? 0,
      neu: s?.neu.length ?? 0,
      abweichend: s?.abweichend.length ?? 0,
      nurInDb: s?.nur_in_db.length ?? 0,
    };
  });

  /** „Nachziehen" hat nur dann etwas zu tun, wenn wirklich etwas fehlt. */
  readonly canFill = computed(() => this.available() && this.counts().neu > 0);

  /** Der scharfe Weg lohnt nur, wenn es abweichende oder überzählige Bereiche
   *  gibt — sonst wäre er ein Schnappschuss ohne Wirkung. */
  readonly canApply = computed(() => {
    const c = this.counts();
    return this.available() && c.neu + c.abweichend + c.nurInDb > 0;
  });

  readonly namen = computed(() => {
    const s = this.status.value();
    if (!s) return [];
    return [
      { key: 'seed.new', areas: s.neu },
      { key: 'seed.differing', areas: s.abweichend },
      { key: 'seed.onlyInDb', areas: s.nur_in_db },
    ].filter(g => g.areas.length > 0);
  });

  constructor() {
    void this.status.reload();
  }

  arm(): void {
    this.armed.set(true);
  }

  disarm(): void {
    this.armed.set(false);
  }

  async fill(): Promise<void> {
    const ok = await this.action.run('fill', async () => {
      const { written } = await this.api.applySeed('missing');
      return written === 0
        ? this.t('seed.nothingToFill')
        : this.lang.plural('seed.filled', written);
    });
    if (ok) await this.status.reload();
  }

  async applyExact(): Promise<void> {
    this.disarm();
    const ok = await this.action.run('exact', async () => {
      const { written, deleted } = await this.api.applySeed('exact');
      return this.t('seed.applied', { written, deleted });
    });
    // Auch bei Fehlschlag neu lesen: der Lauf kann nach dem Schnappschuss
    // abgebrochen sein, und dann steht in der Karte sonst eine Zählung, die
    // nicht mehr stimmt.
    await this.status.reload();
    if (!ok) this.disarm();
  }
}
