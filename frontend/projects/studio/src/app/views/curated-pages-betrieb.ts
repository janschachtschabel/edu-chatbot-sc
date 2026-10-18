/**
 * Die kuratierten Seiten für den Betrieb (9-4b): Anzeige, Datenschutz, Wissen (gemeinsam)
 * und Betrieb (System, Paket 14).
 *
 * Aus `curated-views.ts` herausgelöst (Paket 6), das über 300 Zeilen stand; die
 * Regeln für diese Daten stehen dort im Kopf. Die Reihenfolge der Seiten und
 * ihrer Abschnitte ist unverändert.
 */
import type { CuratedView } from './curated-views';

/**
 * Paket 15 (A1): Im Agent-Modus streamt nur `respond_to_user`, und das Werkzeug gibt es nur mit
 * den Agent-Schnellantworten. Beide Schalter haben die Vorgabe „an“ (`config_models/engine.py`);
 * ein fehlender Schlüssel zählt deshalb als an, ein fehlender Modus als `pattern`.
 */
function betriebHinweise(doc: Readonly<Record<string, unknown>>): readonly string[] {
  const betrieb = (doc['betrieb'] ?? {}) as Record<string, unknown>;
  const an = (schalter: string) => betrieb[schalter] !== false;
  return doc['mode'] === 'agent' && an('token_streaming') && !an('agent_schnellantworten')
    ? ['curated.betrieb.hinweis.streamingOhneSchnellantworten'] : [];
}

export const BETRIEB_SEITEN: readonly CuratedView[] = [
  {
    slug: 'anzeige',
    introKey: 'curated.anzeige.intro',
    // Paket 15: Reiter statt fünf gestapelter Abschnitte (Nutzer-Rundgang 2026-10-17).
    reiter: [
      { id: 'chat', labelKey: 'curated.anzeige.reiter.chat' },
      { id: 'karten', labelKey: 'curated.anzeige.reiter.karten' },
      { id: 'kopfzeile', labelKey: 'curated.anzeige.reiter.kopfzeile' },
      { id: 'geraete', labelKey: 'curated.anzeige.reiter.geraete' },
    ],
    sections: [
      {
        area: '01-base/display-rules',
        reiter: 'chat',
        labelKey: 'curated.anzeige.display.label',
        hintKey: 'curated.anzeige.display.hint',
      },
      // ST-9: welche Treffer überhaupt zu Karten werden, und die Links darin.
      {
        area: '01-base/card-pipeline',
        reiter: 'karten',
        labelKey: 'curated.anzeige.cardPipeline.label',
        hintKey: 'curated.anzeige.cardPipeline.hint',
      },
      {
        area: '01-base/widget-modes',
        reiter: 'karten',
        labelKey: 'curated.anzeige.widgetModes.label',
        hintKey: 'curated.anzeige.widgetModes.hint',
      },
      {
        area: '01-base/header-nav',
        reiter: 'kopfzeile',
        labelKey: 'curated.anzeige.header.label',
        hintKey: 'curated.anzeige.header.hint',
      },
      {
        area: '01-base/device-config',
        reiter: 'geraete',
        // Paket 15: der Anrede-Rückfall steht auf „Zielgruppen“.
        felder: ['device_max_items'],
        labelKey: 'curated.anzeige.devices.label',
        hintKey: 'curated.anzeige.devices.hint',
      },
    ],
  },
  {
    slug: 'datenschutz',
    introKey: 'curated.datenschutz.intro',
    sections: [
      {
        area: '01-base/privacy-config',
        labelKey: 'curated.datenschutz.privacy.label',
        hintKey: 'curated.datenschutz.privacy.hint',
      },
      {
        area: '01-base/quality-log-config',
        labelKey: 'curated.datenschutz.qualityLog.label',
        hintKey: 'curated.datenschutz.qualityLog.hint',
      },
      {
        // Paket 8 (A): what the `retention_days` fields (conversations, safety log,
        // quality log) mean right now.
        panel: 'retention',
        labelKey: 'curated.datenschutz.retention.label',
        hintKey: 'curated.datenschutz.retention.hint',
      },
      {
        panel: 'privacy-purge',
        labelKey: 'curated.datenschutz.purge.label',
        hintKey: 'curated.datenschutz.purge.hint',
      },
    ],
  },
  {
    slug: 'wissen',
    introKey: 'curated.wissen.intro',
    // Paket 15: Wissensbereiche und MCP-Server getrennt — die Server-Liste ging unten unter.
    reiter: [
      { id: 'rag', labelKey: 'curated.wissen.reiter.rag' },
      { id: 'mcp', labelKey: 'curated.wissen.reiter.mcp' },
    ],
    sections: [
      {
        panel: 'rag-areas',
        reiter: 'rag',
        labelKey: 'curated.wissen.areas.label',
        hintKey: 'curated.wissen.areas.hint',
      },
      {
        panel: 'rag-ingest',
        reiter: 'rag',
        labelKey: 'curated.wissen.ingest.label',
        hintKey: 'curated.wissen.ingest.hint',
      },
      {
        // Describes the areas the panel above lists — only useful together,
        // which is why this config sits between them and not on its own page.
        area: '05-knowledge/rag-config',
        reiter: 'rag',
        labelKey: 'curated.wissen.ragConfig.label',
        hintKey: 'curated.wissen.ragConfig.hint',
      },
      {
        // Paket 7 (P4): read since ever by `rag/retrieval`, editable only now.
        area: '01-base/rag-retrieval',
        reiter: 'rag',
        labelKey: 'curated.wissen.retrieval.label',
        hintKey: 'curated.wissen.retrieval.hint',
      },
      {
        panel: 'mcp-registry',
        reiter: 'mcp',
        labelKey: 'curated.wissen.mcp.label',
        hintKey: 'curated.wissen.mcp.hint',
      },
    ],
  },
  {
    // Paket 14: Vorgabe-Maschine und Betriebsschalter gelten für beide Arbeitsbereiche; die
    // Felder der Agent-Schleife stehen auf „Rolle & Grenzen“, „Werkzeuge“ und „Skills“ (Paket 15).
    slug: 'betrieb',
    introKey: 'curated.betrieb.intro',
    sections: [
      {
        area: '01-base/engine',
        felder: ['mode', 'betrieb'],
        labelKey: 'curated.betrieb.engine.label',
        hintKey: 'curated.betrieb.engine.hint',
        hinweise: betriebHinweise,
      },
    ],
  },
];
