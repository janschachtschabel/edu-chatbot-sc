/**
 * Index of every config area (9-3f) — the entry point to the generic editor.
 *
 * This is the view that makes V3 checkable: the list comes from the backend
 * (`GET /config/files`), not from a hand-kept menu, so an area cannot be
 * missing from the studio without also being missing from the store. ALT had
 * no such list; areas without a purpose-built view were simply unreachable, and
 * `classify-overrides` was the standing example.
 */
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { ConfigApi, type ConfigFileEntry } from '../core/config-api.service';
import { StudioApiError } from '../core/studio-api-error';
import { StudioLanguageService } from '../i18n/studio-language.service';

interface AreaEntry {
  readonly key: string;
  readonly name: string;
  readonly type: string;
  /** Pre-split: a single `'01-base/policy'` segment would be encoded to `%2F`. */
  readonly link: readonly string[];
}

interface AreaGroup {
  readonly folder: string;
  readonly areas: readonly AreaEntry[];
}

@Component({
  selector: 'studio-areas',
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 class="ar-title">{{ t('view.bereiche.label') }}</h2>
    <p class="ar-lead">{{ t('areas.lead') }}</p>

    @if (loading()) {
      <p class="ar-state" aria-busy="true">{{ t('areas.loading') }}</p>
    } @else if (error()) {
      <div class="ar-state ar-state--error" role="alert">
        <p>{{ error() }}</p>
        <button type="button" class="ar-retry" (click)="load()">{{ t('async.retry') }}</button>
      </div>
    } @else if (groups().length === 0) {
      <p class="ar-state">{{ t('areas.empty', { cmd: t('areas.importCmd') }) }}</p>
    } @else {
      <p class="ar-count">{{ plural('areas.count', total()) }}</p>
      @for (group of groups(); track group.folder) {
        <section class="ar-group">
          <h3 class="ar-folder">{{ group.folder }}</h3>
          <!-- role=list: Safari/VoiceOver drops list semantics from a list
               styled without markers, so the count is never announced. -->
          <ul class="ar-list" role="list">
            @for (area of group.areas; track area.key) {
              <li>
                <a class="ar-link" [routerLink]="area.link">
                  <span class="ar-name">{{ area.name }}</span>
                  <span class="ar-type">{{ area.type }}</span>
                </a>
              </li>
            }
          </ul>
        </section>
      }
    }
  `,
  styleUrl: './areas.component.scss',
})
export class AreasComponent {
  private readonly config = inject(ConfigApi);
  private readonly lang = inject(StudioLanguageService);
  protected readonly t = this.lang.t;
  protected readonly plural = this.lang.plural;

  readonly loading = signal(true);
  readonly error = signal('');
  private readonly files = signal<readonly ConfigFileEntry[]>([]);

  readonly total = computed(() => this.files().length);

  readonly groups = computed<readonly AreaGroup[]>(() => {
    const byFolder = new Map<string, AreaEntry[]>();
    for (const file of this.files()) {
      const key = stripExtension(file.path);
      const slash = key.lastIndexOf('/');
      const folder = slash < 0 ? this.lang.t('areas.noFolder') : key.slice(0, slash);
      const entry: AreaEntry = {
        key,
        name: key.slice(slash + 1),
        type: file.type,
        link: ['/bereich', ...key.split('/')],
      };
      byFolder.set(folder, [...(byFolder.get(folder) ?? []), entry]);
    }
    return [...byFolder.entries()]
      .sort(([a], [b]) => a.localeCompare(b, 'de'))
      .map(([folder, areas]) => ({
        folder,
        areas: [...areas].sort((a, b) => a.name.localeCompare(b.name, 'de')),
      }));
  });

  constructor() {
    void this.load();
  }

  async load(): Promise<void> {
    this.loading.set(true);
    this.error.set('');
    try {
      this.files.set(await this.config.listFiles());
    } catch (err) {
      this.error.set(this.lang.t(
        err instanceof StudioApiError && err.status === 0 ? 'error.offline' : 'areas.error',
      ));
    } finally {
      this.loading.set(false);
    }
  }
}

function stripExtension(path: string): string {
  return path.replace(/\.(ya?ml|md)$/i, '');
}
