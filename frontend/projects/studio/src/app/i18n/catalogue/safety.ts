/**
 * Die Ansicht „Safety-Logs" (C1-d4e3) — Kennzahlen, Filter, Liste und die
 * vollständige Entscheidung.
 *
 * **Ein Teil, weil es EIN Panel ist:** das Detail wird in die rechte Spalte der
 * Liste hinein gerendert. Es teilt sich deshalb `sfl.emptyMessage` und die
 * Risiko-Namen mit ihr — dieselbe Lage wie Logs/Turn-Detail (C1-d4d2).
 *
 * **Zwei eingefrorene Konstanten-Karten in `safety-labels.ts`** (Risikostufen
 * und Rechtsfelder) sind der 16. und 17. Fall dieser Klasse. Beide behalten
 * ihren Rückfall auf den rohen Schlüssel: das Backend hängt zugeordnete
 * Rechtsfelder an (`safety/service.py:113`), die diese Liste nicht aufzählen
 * kann, und ein unbekannter Schlüssel im Klartext schlägt eine leere Zelle.
 *
 * **Was NICHT hier steht:** Brotkrume (`nav.group.auswertung`) und Titel
 * (`view.safety-logs.label`), `action.refresh*` und der Zustands-Streifen
 * (`shared.ts`).
 *
 * **Die Marker der Zeile bleiben ·-verbunden statt `list()`**: sie sind eine
 * technische Kennzeichnung, keine Prosa — dieselbe Entscheidung wie bei
 * `qualLogs.bulk.filtered` und der Lasttest-Zusammenfassung.
 */
import type { CataloguePart } from './catalogue-part';

export const SAFETY: CataloguePart = {
  de: {
    'sfl.intro':
      'Jede Nachricht, bei der die Sicherheits-Pipeline eingegriffen oder ein Risiko '
      + 'festgestellt hat — neueste zuerst, höchstens 200. Ein Event wählen, um die '
      + 'vollständige Entscheidung zu sehen.',

    // ── Kennzahlen ──────────────────────────────────────────────────
    'sfl.stats': 'Kennzahlen',
    'sfl.stats.note':
      'Diese Zahlen gelten immer für alle geprüften Events. Der Filter darunter wirkt nur '
      + 'auf die Liste.',
    'sfl.kpi.total': 'Events gesamt',
    'sfl.kpi.high': 'Risiko hoch',
    'sfl.kpi.medium': 'Risiko mittel',
    'sfl.kpi.escalated': 'An das LLM eskaliert',
    'sfl.kpi.rateLimited': 'Rate-limited',

    // ── Filter und Liste ────────────────────────────────────────────
    'sfl.filter': 'Risikostufe',
    'sfl.filter.all': 'Alle Risiken',
    'sfl.filter.medium': 'Mittel und hoch',
    'sfl.filter.high': 'Nur hoch',
    'sfl.events': 'Safety-Events',
    'sfl.empty.filtered':
      'Kein Event mit dieser Risikostufe im geladenen Fenster. Der Filter oben zeigt wieder '
      + 'alle.',
    'sfl.empty.none':
      'Noch keine Safety-Events. Hier steht jede Nachricht, die die Sicherheits-Pipeline '
      + 'geprüft und als auffällig eingestuft hat.',
    /** Eine Nachricht, die das Backend ohne Text gespeichert hat — gelesen in
     *  der Liste UND im Detail. */
    'sfl.emptyMessage': '(leer)',
    'sfl.marker.rateLimited': 'rate-limited',
    'sfl.marker.escalated': 'an das LLM eskaliert',
    'sfl.decision': 'Entscheidung',
    'sfl.pick': 'Links ein Event wählen.',

    // ── Vokabular der Pipeline (`safety-labels.ts`) ─────────────────
    'sfl.risk.low': 'Niedrig',
    'sfl.risk.medium': 'Mittel',
    'sfl.risk.high': 'Hoch',
    'sfl.legal.strafrecht': 'Strafrecht',
    'sfl.legal.jugendschutz': 'Jugendschutz',
    'sfl.legal.persoenlichkeitsrechte': 'Persönlichkeitsrechte',
    'sfl.legal.datenschutz': 'Datenschutz',

    // ── Die vollständige Entscheidung ───────────────────────────────
    'sd.risk': 'Risiko: {value}',
    'sd.session': 'Session: {id}',
    'sd.message': 'Nachricht',
    'sd.stages': 'Geprüfte Stufen',
    'sd.reasons': 'Gründe',
    'sd.legal': 'Rechtsfelder',
    'sd.categories': 'Geflaggte Kategorien',
    'sd.blockedTools': 'Blockierte Werkzeuge',
    'sd.enforcedPattern': 'Erzwungenes Muster',
    'sd.scores': 'Alle Kategorie-Werte',
  },

  en: {
    'sfl.intro':
      'Every message where the safety pipeline stepped in or found a risk — newest first, '
      + 'at most 200. Pick an event to see the full decision.',

    'sfl.stats': 'Key figures',
    'sfl.stats.note':
      'These numbers always cover all checked events. The filter below only affects the '
      + 'list.',
    'sfl.kpi.total': 'Events in total',
    'sfl.kpi.high': 'High risk',
    'sfl.kpi.medium': 'Medium risk',
    'sfl.kpi.escalated': 'Escalated to the LLM',
    'sfl.kpi.rateLimited': 'Rate-limited',

    'sfl.filter': 'Risk level',
    'sfl.filter.all': 'All risks',
    'sfl.filter.medium': 'Medium and high',
    'sfl.filter.high': 'High only',
    'sfl.events': 'Safety events',
    'sfl.empty.filtered':
      'No event at this risk level in the loaded window. The filter above shows all of them '
      + 'again.',
    'sfl.empty.none':
      'No safety events yet. This is where every message shows up that the safety pipeline '
      + 'checked and judged noteworthy.',
    'sfl.emptyMessage': '(empty)',
    'sfl.marker.rateLimited': 'rate-limited',
    'sfl.marker.escalated': 'escalated to the LLM',
    'sfl.decision': 'Decision',
    'sfl.pick': 'Pick an event on the left.',

    'sfl.risk.low': 'Low',
    'sfl.risk.medium': 'Medium',
    'sfl.risk.high': 'High',
    'sfl.legal.strafrecht': 'Criminal law',
    'sfl.legal.jugendschutz': 'Youth protection',
    'sfl.legal.persoenlichkeitsrechte': 'Personality rights',
    'sfl.legal.datenschutz': 'Data protection',

    'sd.risk': 'Risk: {value}',
    'sd.session': 'Session: {id}',
    'sd.message': 'Message',
    'sd.stages': 'Stages run',
    'sd.reasons': 'Reasons',
    'sd.legal': 'Legal fields',
    'sd.categories': 'Flagged categories',
    'sd.blockedTools': 'Blocked tools',
    'sd.enforcedPattern': 'Enforced pattern',
    'sd.scores': 'All category scores',
  },
};
