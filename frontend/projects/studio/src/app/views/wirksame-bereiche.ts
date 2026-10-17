/**
 * Welche Wissensbereiche ein Muster tatsächlich nutzt (Paket 6, S4 — externes
 * Audit F13). Seit Paket 4c (B2) unterscheidet das Formular „nicht gesetzt" von
 * „leer"; welche Bereiche damit wirken, sagte es nicht.
 *
 * **Ein Zwilling der Backend-Regel** — zwei Stufen, beide zählen:
 *  1. `rag` nicht unter den Quellen → kein Bereich, auch nicht aus `rag_areas`:
 *     die Sperre `_rag_allowed_for_pattern` in `services/response_tool_selection.py`
 *     schaltet dann Vorab-Abruf und `query_knowledge` ab;
 *  2. `rag_areas` gesetzt (auch leer) → genau diese, soweit der Katalog sie kennt
 *     (`domain/route_head._resolve_rag_areas`);
 *  3. sonst → die Bereiche „immer“, danach die „auf Abruf“ — ein Bereich ohne
 *     gültige Abrufart wirkt nur, wenn ein Muster ihn ausdrücklich nennt.
 * Ein Muster ohne `sources` hat die Vorgabe der Engine, `["mcp"]` — also
 * Fall 1. „Bekannt“ heißt wie im Lader (`load_rag_config`): ein Eintrag mit
 * `mode`. Ändert sich die Regel dort, muss sie es hier auch; die Tests in
 * `wirksame-bereiche.spec.ts` beschreiben dieselben Fälle.
 */
import { computed, signal } from '@angular/core';

import type { ConfigApi } from '../core/config-api.service';
import type { Translate } from '../i18n/studio-language.service';

export type RagKatalog = Readonly<Record<string, unknown>>;

export interface WirksameBereiche {
  /** `gesetzt`: die Liste des Musters · `vorgabe`: der Katalog · `ohne-rag`: keine Quelle */
  readonly art: 'gesetzt' | 'vorgabe' | 'ohne-rag';
  readonly bereiche: readonly string[];
  /** Namen aus der Liste, die der Katalog nicht kennt — sie wirken nicht. */
  readonly unbekannt: readonly string[];
}

/** Die Engine-Vorgabe für ein Muster ohne `sources` (`domain/pattern_engine.py`). */
const VORGABE_QUELLEN = ['mcp'];

export function wirksameBereiche(
  frontmatter: Readonly<Record<string, unknown>>, katalog: RagKatalog,
): WirksameBereiche {
  const quellen = Array.isArray(frontmatter['sources'])
    ? (frontmatter['sources'] as unknown[]).map(String)
    : VORGABE_QUELLEN;
  if (!quellen.includes('rag')) return { art: 'ohne-rag', bereiche: [], unbekannt: [] };
  const bekannt = Object.entries(katalog)
    .filter(([, eintrag]) => !!eintrag && typeof eintrag === 'object' && 'mode' in eintrag)
    .map(([name, eintrag]) => ({ name, mode: (eintrag as { mode?: unknown }).mode }));
  const namen = bekannt.map((eintrag) => eintrag.name);
  const liste = frontmatter['rag_areas'];
  if (Array.isArray(liste)) {
    const genannt = liste.map(String);
    return {
      art: 'gesetzt',
      bereiche: genannt.filter((name) => namen.includes(name)),
      unbekannt: genannt.filter((name) => !namen.includes(name)),
    };
  }
  const mitArt = (mode: string): string[] =>
    bekannt.filter((eintrag) => eintrag.mode === mode).map((eintrag) => eintrag.name);
  return { art: 'vorgabe', bereiche: [...mitArt('always'), ...mitArt('on-demand')], unbekannt: [] };
}

/** Der Wissens-Katalog (`05-knowledge/rag-config`), oder `null` — dann bleibt der
 *  Satz weg, statt etwas Falsches zu behaupten. */
export async function ladeRagKatalog(config: ConfigApi): Promise<RagKatalog | null> {
  try {
    const doc = await config.data('05-knowledge/rag-config');
    return doc.data && typeof doc.data === 'object' ? (doc.data as RagKatalog) : null;
  } catch {
    return null;
  }
}

/** Der Satz darüber für das Formular — „Nicht gesetzt — es wirken die Bereiche
 *  des Katalogs: A und B." `list` verbindet nach der Regel der Sprache. */
export function ragSatz(
  wirksam: WirksameBereiche, t: Translate, list: (parts: readonly string[]) => string,
): string {
  const bereiche = list(wirksam.bereiche);
  let satz: string;
  if (wirksam.art === 'ohne-rag') {
    satz = t('groupSection.rag.noRag');
  } else if (wirksam.art === 'gesetzt') {
    satz = wirksam.bereiche.length
      ? t('groupSection.rag.set', { areas: bereiche })
      : t('groupSection.rag.setEmpty');
  } else {
    satz = wirksam.bereiche.length
      ? t('groupSection.rag.default', { areas: bereiche })
      : t('groupSection.rag.defaultEmpty');
  }
  return wirksam.unbekannt.length
    ? `${satz} ${t('groupSection.rag.unknown', { areas: list(wirksam.unbekannt) })}`
    : satz;
}

/**
 * Der Hinweis im Muster-Formular: lädt den Katalog beim ersten offenen Muster
 * und sagt im Reiter „Tools & Wissen" (ohne Reiter immer), welche Bereiche
 * wirken. Außerhalb der Muster bleibt er leer.
 */
export class RagHinweis {
  readonly katalog = signal<RagKatalog | null>(null);
  private geladen = false;

  readonly satz = computed(() => {
    const katalog = this.katalog();
    const doc = this.doc() as { frontmatter?: unknown } | null;
    const reiter = this.reiter();
    if (!this.aktiv() || !katalog || !doc || (reiter && reiter !== 'pf-tools')) return '';
    const fm = doc.frontmatter && typeof doc.frontmatter === 'object'
      ? doc.frontmatter as Record<string, unknown> : {};
    return ragSatz(wirksameBereiche(fm, katalog), this.t, this.list);
  });

  constructor(
    private readonly config: ConfigApi,
    private readonly aktiv: () => boolean,
    private readonly doc: () => unknown,
    private readonly reiter: () => string,
    private readonly t: Translate,
    private readonly list: (parts: readonly string[]) => string,
  ) {}

  laden(): void {
    if (!this.aktiv() || this.geladen) return;
    this.geladen = true;
    void ladeRagKatalog(this.config).then((katalog) => this.katalog.set(katalog));
  }
}
