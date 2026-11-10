/**
 * Die Dokumente eines Ordners — Muster, Personas oder (AS-0) Abläufe (Paket 6, S1 — ST-3d):
 * laden, anlegen, duplizieren, löschen, und ob ein Dokument zum
 * Auslieferungsstand gehört.
 *
 * Aus `group-section` herausgelöst wie `AreaDocEditor` für den Editor: dort
 * stehen Darstellung und Wahl, hier der Verkehr mit dem Server. Den Schlüssel
 * eines neuen Dokuments leitet der Server ab (`POST /config/documents`) — eine
 * Persona wird zur Laufzeit über ihre Kennung gefunden, und die Regel dafür
 * steht nur dort.
 */
import { signal } from '@angular/core';

import type { AblaufZeile } from '../core/ablauf-api.service';
import type { ConfigApi } from '../core/config-api.service';
import type { SnapshotsApi } from '../core/snapshots-api.service';
import type { StudioApi } from '../core/studio-api.service';
import type { ListEntry } from '../schema-form/entry-list.component';

export interface GroupEntry extends ListEntry {
  /** Bereichsschlüssel ohne Endung — so wird das Dokument angesprochen. */
  readonly id: string;
  readonly kennung: string;
  readonly name: string;
}

/** Der Ordner der Abläufe (AS-0): YAML-Dokumente, die Kennung ist der Schlüssel. */
export const ABLAEUFE = '06-ablaeufe';
/** Wie der Treiber Ablauf-Kennungen liest (`domain/config_models/ablauf.ID_FORM`). */
const ABLAUF_KENNUNG_MAX = 40;

/** Was die Liste der Abläufe je Eintrag über den Titel hinaus nennt — von der Seite übersetzt. */
export interface GroupOptions {
  /** Die Sprache des Studios: welcher Titel eines Ablaufs gilt. */
  readonly sprache?: () => string;
  /** Der Zusatz einer Ablauf-Zeile (Kennung, an/aus, Auslöser, Befunde). */
  readonly ablaufNotiz?: (zeile: AblaufZeile) => string;
}

interface ElementsResponse {
  readonly patterns?: readonly { id?: string; label?: string; file?: string }[];
  readonly personas?: readonly { id?: string; label?: string; file?: string }[];
}

export class GroupDocuments {
  readonly entries = signal<readonly GroupEntry[]>([]);
  readonly loading = signal(false);
  /** Zählt die Abrufe: eine spätere Antwort eines älteren Abrufs überschreibt
   *  nie die Liste eines neueren (Review Paket 6 — sonst fehlte ein eben
   *  angelegtes Dokument, samt seiner Knöpfe). */
  private generation = 0;

  constructor(
    private readonly api: StudioApi,
    private readonly config: ConfigApi,
    private readonly snapshots: SnapshotsApi,
    private readonly area: () => string,
    private readonly optionen: GroupOptions = {},
  ) {}

  /** Ist das der Ordner der Abläufe (YAML, Kennung = Schlüssel)? */
  get istAblauf(): boolean {
    return this.area() === ABLAEUFE;
  }

  /** Die Liste aus `/config/elements` — wirft bei einem Fehler (der Aufrufer meldet ihn). */
  async load(): Promise<void> {
    const mine = ++this.generation;
    this.loading.set(true);
    try {
      if (this.istAblauf) {
        const liste = await this.api.get<{ ablaeufe: readonly AblaufZeile[] }>('/config/ablaeufe');
        if (mine !== this.generation) return;
        this.entries.set(liste.ablaeufe.map((zeile) => this.ablaufEintrag(zeile)));
        return;
      }
      const elements = await this.api.get<ElementsResponse>('/config/elements');
      if (mine !== this.generation) return;
      const raw = this.area() === '04-personas' ? elements.personas : elements.patterns;
      this.entries.set(
        (raw ?? [])
          .map((entry) => {
            const kennung = String(entry.id ?? '');
            const name = String(entry.label || kennung);
            // `file` ist immer `<key>.md` (der Lader setzt es aus dem Schlüssel)
            const key = String(entry.file ?? '').replace(/\.md$/, '');
            return { id: key, title: name, note: kennung, kennung, name };
          })
          .filter((entry) => entry.id.startsWith(`${this.area()}/`)),
      );
    } finally {
      if (mine === this.generation) this.loading.set(false);
    }
  }

  private ablaufEintrag(zeile: AblaufZeile): GroupEntry {
    const sprache = this.optionen.sprache?.() ?? 'de';
    const name = zeile.titel[sprache] || zeile.titel['de'] || Object.values(zeile.titel)[0] || zeile.id;
    return {
      id: zeile.key, title: name, kennung: zeile.id, name,
      note: this.optionen.ablaufNotiz?.(zeile) ?? zeile.id,
      problem: !zeile.lesbar || zeile.befunde > 0,
    };
  }

  /** Die Kennung eines neuen Dokuments aus seinem Namen: bei Abläufen in der Form des Treibers
   *  (Kleinbuchstaben, Ziffern, `_`, Buchstabe vorn, höchstens 40), sonst wie bisher. */
  neueKennung(name: string): string {
    if (!this.istAblauf) return slugify(name);
    const roh = slugify(name).replace(/-/g, '_').slice(0, ABLAUF_KENNUNG_MAX).replace(/_+$/, '');
    if (!roh) return '';
    return /^[a-z]/.test(roh) ? roh : `a_${roh}`.slice(0, ABLAUF_KENNUNG_MAX).replace(/_+$/, '');
  }

  /** Gibt es die Kennung schon — als Kennung oder als Dateiname, ohne Groß/Klein?
   *  Der Server prüft dasselbe (409); hier spart es den Weg dorthin. */
  taken(kennung: string): boolean {
    const gesucht = kennung.toLowerCase();
    // `katalog` hieß bis AS-0 der Bereich aller Abläufe — vergeben (der Server weist ihn ab).
    if (this.istAblauf && gesucht === 'katalog') return true;
    return this.entries().some((entry) =>
      entry.kennung.toLowerCase() === gesucht
      || entry.id.slice(this.area().length + 1).toLowerCase() === gesucht);
  }

  /** `M05` → `M05_kopie`, `M05_kopie_2` … wie die Kopie eines Listeneintrags. */
  freeCopyId(kennung: string): string {
    // Abläufe: die Kopie muss in 40 Zeichen passen — der Stamm wird je Endung gekürzt.
    const kopie = (endung: string) => this.istAblauf
      ? `${kennung.slice(0, ABLAUF_KENNUNG_MAX - endung.length)}${endung}`
      : `${kennung}${endung}`;
    if (!this.taken(kopie('_kopie'))) return kopie('_kopie');
    for (let n = 2; ; n += 1) {
      if (!this.taken(kopie(`_kopie_${n}`))) return kopie(`_kopie_${n}`);
    }
  }

  /** Anlegen oder duplizieren; gibt den Schlüssel des neuen Dokuments zurück. */
  async create(id: string, label: string, source?: string): Promise<string> {
    const created = await this.config.createDocument({
      group: this.area(), id, label, ...(source ? { source } : {}),
    });
    return created.key;
  }

  /** `version`: der geladene Stand — hat inzwischen jemand gespeichert, lehnt
   *  der Server mit 409 ab, statt dessen Fassung still mitzulöschen. */
  async remove(key: string, version: number | null = null): Promise<void> {
    await this.config.deleteDocument(key, version);
  }

  /**
   * Gehört das Dokument zum Auslieferungsstand? `null`, wenn sich das nicht
   * sagen lässt (kein Seed im Abbild, Fehler) — dann schweigt die Rückfrage
   * dazu, statt zu raten.
   */
  async shipped(key: string): Promise<boolean | null> {
    try {
      const seed = await this.snapshots.seed();
      if (!seed.available) return null;
      if (seed.gleich.includes(key) || seed.abweichend.includes(key)) return true;
      return seed.nur_in_db.includes(key) ? false : null;
    } catch {
      return null;
    }
  }
}

/** `M03 Kuratieren` → `m03-kuratieren`. Empty when nothing usable is left.
 *  The id is the WHOLE title's slug (Paket 4, D5): the first word alone gave
 *  „Neue Zielgruppe" and „Neue Lehrkraft" the same id. */
export function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[äöüß]/g, (c) => ({ ä: 'ae', ö: 'oe', ü: 'ue', ß: 'ss' })[c] ?? c)
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}
