/**
 * Klartexte der Auswahlwerte (ST-2d): `feld.<Modell>.<feld>.wahl.<wert>`.
 *
 * Das Auswahlfeld zeigt „Klartext (wert)" — der Wert bleibt lesbar, weil er im
 * YAML-Reiter, in der Doku und in den Logs so heißt. Ein Name sagt, was die
 * Option IST; was sie bewirkt (oder dass der Code das Feld nicht auswertet),
 * steht im Hilfetext des Feldes. Wächter: `fields.spec.ts`.
 */
import type { CataloguePart } from './catalogue-part';

export const FIELDS_AUSWAHL: CataloguePart = {
  de: {
    // ── Kontext-Aktionen: was eine Pill auslöst ──────────────────────
    'feld.ContextPill.action.wahl.browse_collection': 'Sammlung durchstöbern',
    'feld.ContextPill.action.wahl.curate_collection': 'Sammlung kuratieren',
    'feld.ContextPill.action.wahl.generate_learning_path': 'Lernpfad erstellen',
    'feld.ContextPill.action.wahl.show_content_text': 'Volltext des Inhalts zeigen',

    // ── Sicherheit: wann eine Prüfstufe läuft ────────────────────────
    // „smart" = nur, wenn der Regex-Filter das Risiko schon auf mittel oder
    // hoch gesetzt hat (`services/safety/service.py`, `_stage_should_run`).
    'feld.SafetyPreset.moderation.wahl.never': 'Nie',
    'feld.SafetyPreset.moderation.wahl.smart': 'Nur bei Verdacht',
    'feld.SafetyPreset.moderation.wahl.always': 'Bei jeder Nachricht',
    'feld.SafetyPreset.legal_classifier.wahl.never': 'Nie',
    'feld.SafetyPreset.legal_classifier.wahl.smart': 'Nur bei Verdacht',
    'feld.SafetyPreset.legal_classifier.wahl.always': 'Bei jeder Nachricht',
    'feld.EscalationBlock.mode.wahl.off': 'Aus',
    'feld.EscalationBlock.mode.wahl.smart': 'Nur bei Verdacht',
    'feld.EscalationBlock.mode.wahl.always': 'Bei jeder Nachricht',

    // ── Muster ───────────────────────────────────────────────────────
    'feld.PatternFrontmatter.sources.wahl.llm': 'Sprachmodell',
    'feld.PatternFrontmatter.sources.wahl.mcp': 'WLO-Werkzeuge',
    'feld.PatternFrontmatter.sources.wahl.rag': 'Wissensbereiche',
    'feld.PatternFrontmatter.quick_replies_mode.wahl.exact': 'Nach der Antwort',
    'feld.PatternFrontmatter.quick_replies_mode.wahl.speculative': 'Parallel zur Antwort',
    'feld.PatternFrontmatter.quick_replies_mode.wahl.none': 'Keine Vorschläge',

    // ── Wissen und Agent ─────────────────────────────────────────────
    'feld.RagAreaDef.mode.wahl.always': 'Immer dazuladen',
    'feld.RagAreaDef.mode.wahl.on-demand': 'Nur bei Bedarf',
    'feld.EngineArea.mode.wahl.pattern': 'Muster-Maschine',
    'feld.EngineArea.mode.wahl.agent': 'Agent-Schleife',
    'feld.AgentLimits.write_mode.wahl.propose': 'Nur vorschlagen',
    'feld.AgentLimits.write_mode.wahl.execute': 'Ausführen',

    // ── Zonen eines Reglers (ST-2h): was der Wert gerade bewirkt ─────
    // Schwellen ±LENGTH_BIAS_STEP (0,15), dieselbe Zahl wie in der Engine.
    'feld.ToneModifier.length_bias.zone.unter': 'Eine Stufe kürzer',
    'feld.ToneModifier.length_bias.zone.mitte': 'Länge wie im Muster',
    'feld.ToneModifier.length_bias.zone.ueber': 'Eine Stufe länger',
    'feld.PersonaFrontmatter.length_bias.zone.unter': 'Eine Stufe kürzer',
    'feld.PersonaFrontmatter.length_bias.zone.mitte': 'Länge wie im Muster',
    'feld.PersonaFrontmatter.length_bias.zone.ueber': 'Eine Stufe länger',
    'feld.GoldTurn.anwendungsfall.wahl.suchen': 'Suchen',
    'feld.GoldTurn.anwendungsfall.wahl.zusammenstellen': 'Zusammenstellen',
    'feld.GoldTurn.anwendungsfall.wahl.erzeugen': 'Erzeugen',
    'feld.GoldTurn.anwendungsfall.wahl.ueberarbeiten': 'Überarbeiten',
    'feld.GoldTurn.anwendungsfall.wahl.zeigen': 'Zeigen',
    'feld.GoldTurn.anwendungsfall.wahl.erklaeren': 'Erklären',
    'feld.GoldTurn.anwendungsfall.wahl.wlo_wissen': 'WLO-Wissen',
    'feld.GoldTurn.anwendungsfall.wahl.orientieren': 'Orientieren',
    'feld.GoldTurn.anwendungsfall.wahl.kuratieren': 'Kuratieren',
    'feld.GoldTurn.anwendungsfall.wahl.rueckmeldung': 'Rückmeldung',
    'feld.GoldTurn.anwendungsfall.wahl.schutz': 'Schutz',
    'feld.GoldTurn.anwendungsfall.wahl.sonstiges': 'Sonstiges',
  },
  en: {
    'feld.ContextPill.action.wahl.browse_collection': 'Browse the collection',
    'feld.ContextPill.action.wahl.curate_collection': 'Curate the collection',
    'feld.ContextPill.action.wahl.generate_learning_path': 'Create a learning path',
    'feld.ContextPill.action.wahl.show_content_text': 'Show the full text',

    'feld.SafetyPreset.moderation.wahl.never': 'Never',
    'feld.SafetyPreset.moderation.wahl.smart': 'Only on suspicion',
    'feld.SafetyPreset.moderation.wahl.always': 'On every message',
    'feld.SafetyPreset.legal_classifier.wahl.never': 'Never',
    'feld.SafetyPreset.legal_classifier.wahl.smart': 'Only on suspicion',
    'feld.SafetyPreset.legal_classifier.wahl.always': 'On every message',
    'feld.EscalationBlock.mode.wahl.off': 'Off',
    'feld.EscalationBlock.mode.wahl.smart': 'Only on suspicion',
    'feld.EscalationBlock.mode.wahl.always': 'On every message',

    'feld.PatternFrontmatter.sources.wahl.llm': 'Language model',
    'feld.PatternFrontmatter.sources.wahl.mcp': 'WLO tools',
    'feld.PatternFrontmatter.sources.wahl.rag': 'Knowledge areas',
    'feld.PatternFrontmatter.quick_replies_mode.wahl.exact': 'After the answer',
    'feld.PatternFrontmatter.quick_replies_mode.wahl.speculative': 'Alongside the answer',
    'feld.PatternFrontmatter.quick_replies_mode.wahl.none': 'No suggestions',

    'feld.RagAreaDef.mode.wahl.always': 'Always include',
    'feld.RagAreaDef.mode.wahl.on-demand': 'Only on demand',
    'feld.EngineArea.mode.wahl.pattern': 'Pattern engine',
    'feld.EngineArea.mode.wahl.agent': 'Agent loop',
    'feld.AgentLimits.write_mode.wahl.propose': 'Propose only',
    'feld.AgentLimits.write_mode.wahl.execute': 'Execute',

    'feld.ToneModifier.length_bias.zone.unter': 'One step shorter',
    'feld.ToneModifier.length_bias.zone.mitte': 'Length as in the pattern',
    'feld.ToneModifier.length_bias.zone.ueber': 'One step longer',
    'feld.PersonaFrontmatter.length_bias.zone.unter': 'One step shorter',
    'feld.PersonaFrontmatter.length_bias.zone.mitte': 'Length as in the pattern',
    'feld.PersonaFrontmatter.length_bias.zone.ueber': 'One step longer',
    'feld.GoldTurn.anwendungsfall.wahl.suchen': 'Search',
    'feld.GoldTurn.anwendungsfall.wahl.zusammenstellen': 'Assemble',
    'feld.GoldTurn.anwendungsfall.wahl.erzeugen': 'Create',
    'feld.GoldTurn.anwendungsfall.wahl.ueberarbeiten': 'Revise',
    'feld.GoldTurn.anwendungsfall.wahl.zeigen': 'Show',
    'feld.GoldTurn.anwendungsfall.wahl.erklaeren': 'Explain',
    'feld.GoldTurn.anwendungsfall.wahl.wlo_wissen': 'WLO knowledge',
    'feld.GoldTurn.anwendungsfall.wahl.orientieren': 'Orient',
    'feld.GoldTurn.anwendungsfall.wahl.kuratieren': 'Curate',
    'feld.GoldTurn.anwendungsfall.wahl.rueckmeldung': 'Feedback',
    'feld.GoldTurn.anwendungsfall.wahl.schutz': 'Safety',
    'feld.GoldTurn.anwendungsfall.wahl.sonstiges': 'Other',
  },
};
