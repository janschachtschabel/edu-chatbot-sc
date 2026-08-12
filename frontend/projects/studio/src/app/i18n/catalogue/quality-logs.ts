/**
 * Der Reiter „Logs" der Analyse samt Turn-Detail (C1-d4d2).
 *
 * **Ein Teil für beide Bauteile**, weil es EIN Panel ist: das Detail wird von
 * `quality-logs.component.html` in die rechte Spalte gerendert, nicht daneben —
 * dieselbe Lage wie Übersicht/Diagnose in C1-d4d1. Sie teilen sich dadurch
 * `qualLogs.emptyMessage` und `qualLogs.confidence` statt sie zu verdoppeln.
 *
 * **Was NICHT hier steht:** `action.refresh*`, `action.cancel` und
 * `action.confirmDelete` aus `shared.ts` — „Abbrechen" und „Ja, löschen" stehen
 * seit C1-d4b1 dort.
 *
 * **`qualLogs.label` ist bewusst NICHT `bars.unit`**, obwohl beide „Turns"
 * lauten: das eine ist das Substantiv des Zustands-Streifens („Lade Turns …"),
 * das andere die voreingestellte Einheit einer Balken-Tabelle. Ein gemeinsamer
 * Eintrag hiesse, dass eine Übersetzung die andere Stelle mitzieht.
 *
 * **Offen als eigene Nacharbeit:** „Persona", „Intent", „Confidence" und
 * „Pattern" stehen inzwischen in vier Teilkatalogen gleichlautend
 * (`eval-detail`, `eval-pattern`, `quality`, hier). Eine `label.*`-Gruppe in
 * `shared.ts` wäre die Zusammenlegung — aber sie berührt drei fertige Scheiben
 * und gehört deshalb in eine eigene, nicht in diese.
 */
import type { CataloguePart } from './catalogue-part';

export const QUALITY_LOGS: CataloguePart = {
  de: {
    // ── Filter-Formular ─────────────────────────────────────────────
    'qualLogs.pattern': 'Pattern-ID',
    'qualLogs.pattern.hint': 'z. B. M04',
    'qualLogs.intent': 'Intent-ID',
    'qualLogs.intent.hint': 'z. B. I02',
    'qualLogs.session': 'Session-ID',
    'qualLogs.session.hint': 'vollständige ID',
    'qualLogs.apply': 'Filtern',
    'qualLogs.reset': 'Filter zurücksetzen',
    'qualLogs.clearFiltered': 'Gefilterte löschen',
    'qualLogs.clearAll': 'Alle löschen',

    // ── Löschen ─────────────────────────────────────────────────────
    'qualLogs.bulk.all':
      'ALLE Quality-Logs löschen — auch die, die dieser Filter gerade nicht zeigt?',
    'qualLogs.bulk.filtered': 'Alle Turns löschen, die den Filter treffen ({parts})?',
    'qualLogs.filter.pattern': 'Pattern {id}*',
    'qualLogs.filter.intent': 'Intent {id}*',
    'qualLogs.filter.session': 'Session {id}',
    'qualLogs.confirmOne': 'Turn #{id} endgültig löschen?',
    'qualLogs.deletedOne': 'Turn #{id} gelöscht.',
    'qualLogs.deletedMany.one': '{count} Turn gelöscht.',
    'qualLogs.deletedMany.other': '{count} Turns gelöscht.',
    'qualLogs.delete': 'Löschen',
    /** EIN zugänglicher Name statt sichtbarem Wort plus `sr`-Anhang; er
     *  beginnt mit dem sichtbaren Wort (WCAG 2.5.3 „Label in Name"). */
    'qualLogs.deleteFor': 'Löschen — Turn #{id}',

    // ── Liste ───────────────────────────────────────────────────────
    /** Substantiv des Zustands-Streifens — siehe Kopf, nicht `bars.unit`. */
    'qualLogs.label': 'Turns',
    'qualLogs.empty.filtered':
      'Kein Turn passt zu diesem Filter. Setze den Filter zurück oder suche weiter '
      + 'gefasst.',
    'qualLogs.empty.none':
      'Noch keine Turns aufgezeichnet. Sobald jemand mit dem Widget chattet, erscheinen '
      + 'die Turns hier.',
    'qualLogs.count.one': '{count} Turn · neueste zuerst',
    'qualLogs.count.other': '{count} Turns · neueste zuerst',
    'qualLogs.emptyMessage': '(leere Nachricht)',
    'qualLogs.confidence': 'Confidence',
    'qualLogs.degradation': 'Degradation',
    'qualLogs.hint': 'Wähle links einen Turn, um Signale, Entities und Werkzeuge zu sehen.',

    // ── Turn-Detail ─────────────────────────────────────────────────
    'qualDetail.noLabel': 'Pattern ohne Label',
    'qualDetail.close': 'Detail schließen',
    'qualDetail.head': 'Turn {count} · {type} · {when}',
    'qualDetail.noType': 'ohne Typ',
    'qualDetail.persona': 'Persona',
    'qualDetail.intent': 'Intent',
    'qualDetail.state': 'Phase',
    'qualDetail.length': 'Antwortlänge',
    'qualDetail.cards': 'Kacheln',
    'qualDetail.degradation.on':
      'Degradation: der Turn lief mit fehlenden Pflicht-Slots weiter.',
    'qualDetail.degradation.missing': 'Fehlend: {slots}.',
    'qualDetail.degradation.off': 'Keine Degradation — alle Pflicht-Slots waren gefüllt.',
    'qualDetail.signals': 'Signale:',
    'qualDetail.tools': 'Werkzeuge:',
    'qualDetail.entities': 'Erkannte Entities',
    'qualDetail.noEntities': 'Keine Entities erkannt.',
    'qualDetail.session': 'Session {id}',
  },

  en: {
    'qualLogs.pattern': 'Pattern id',
    'qualLogs.pattern.hint': 'e.g. M04',
    'qualLogs.intent': 'Intent id',
    'qualLogs.intent.hint': 'e.g. I02',
    'qualLogs.session': 'Session id',
    'qualLogs.session.hint': 'full id',
    'qualLogs.apply': 'Filter',
    'qualLogs.reset': 'Reset filter',
    'qualLogs.clearFiltered': 'Delete filtered',
    'qualLogs.clearAll': 'Delete all',

    'qualLogs.bulk.all':
      'Delete ALL quality logs — including those this filter is not showing right now?',
    'qualLogs.bulk.filtered': 'Delete every turn matching the filter ({parts})?',
    'qualLogs.filter.pattern': 'Pattern {id}*',
    'qualLogs.filter.intent': 'Intent {id}*',
    'qualLogs.filter.session': 'Session {id}',
    'qualLogs.confirmOne': 'Delete turn #{id} for good?',
    'qualLogs.deletedOne': 'Turn #{id} deleted.',
    'qualLogs.deletedMany.one': '{count} turn deleted.',
    'qualLogs.deletedMany.other': '{count} turns deleted.',
    'qualLogs.delete': 'Delete',
    'qualLogs.deleteFor': 'Delete — turn #{id}',

    'qualLogs.label': 'Turns',
    'qualLogs.empty.filtered':
      'No turn matches this filter. Reset the filter or search more broadly.',
    'qualLogs.empty.none':
      'No turns recorded yet. As soon as someone chats with the widget, the turns appear '
      + 'here.',
    'qualLogs.count.one': '{count} turn · newest first',
    'qualLogs.count.other': '{count} turns · newest first',
    'qualLogs.emptyMessage': '(empty message)',
    'qualLogs.confidence': 'Confidence',
    'qualLogs.degradation': 'Degradation',
    'qualLogs.hint': 'Pick a turn on the left to see signals, entities and tools.',

    'qualDetail.noLabel': 'Pattern without a label',
    'qualDetail.close': 'Close detail',
    'qualDetail.head': 'Turn {count} · {type} · {when}',
    'qualDetail.noType': 'no type',
    'qualDetail.persona': 'Persona',
    'qualDetail.intent': 'Intent',
    'qualDetail.state': 'Phase',
    'qualDetail.length': 'Answer length',
    'qualDetail.cards': 'Tiles',
    'qualDetail.degradation.on':
      'Degradation: the turn continued with required slots missing.',
    'qualDetail.degradation.missing': 'Missing: {slots}.',
    'qualDetail.degradation.off': 'No degradation — every required slot was filled.',
    'qualDetail.signals': 'Signals:',
    'qualDetail.tools': 'Tools:',
    'qualDetail.entities': 'Recognised entities',
    'qualDetail.noEntities': 'No entities recognised.',
    'qualDetail.session': 'Session {id}',
  },
};
