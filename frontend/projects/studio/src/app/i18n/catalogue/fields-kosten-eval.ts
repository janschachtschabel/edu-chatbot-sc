/**
 * Feldtexte (ST-1) der Preistafel `01-base/pricing` (`PricingArea`, `ModelPrice`;
 * Seite „Kosten“) und der Gold-Flows `eval/gold-flows` (`GoldFlowsArea`,
 * `GoldFlow`, `GoldTurn`; Seite „Evaluation“).
 *
 * Schlüsselschema wie in `fields-layer-doc.ts`. Gerechnet wird in
 * `domain/pricing.py`: alle drei Preise auf 0 heißt „nicht gepflegt“, ein
 * Kurzname gilt auch für Namen, die an einem `-` weitergehen. Die Gold-Flows liest
 * `services/config_loader/gold_flows.py` roh, geprüft wird in `evals/run_golden.py`.
 * Das Format v2 trägt die Zielgruppe als `zielgruppe`, das Modell kennt nur das
 * v1-Feld `persona` — `persona` und `intents` werden darum nur noch angezeigt, und
 * `version` prüft der Lauf aus dem Studio nicht.
 */
import type { CataloguePart } from './catalogue-part';

export const FIELDS_KOSTEN_EVAL: CataloguePart = {
  de: {
    // ── Preistafel ──────────────────────────────────────────────────
    'feld.PricingArea.currency.label': 'Währung',
    'feld.PricingArea.currency.hint':
      'Code aus drei Buchstaben, etwa EUR oder USD; Vorgabe EUR. Die Preise gelten in dieser '
      + 'Währung, die Seite „Kosten“ zeigt Beträge darin an. Umgerechnet wird nichts.',
    'feld.PricingArea.models.label': 'Preise je Modell',
    'feld.PricingArea.models.hint':
      'Schlüssel ist der Modellname, wie ihn die Seite „Kosten“ in der Spalte „Modell“ zeigt; '
      + 'gpt-5.4-mini gilt auch für gpt-5.4-mini-2026-03-01. Ohne Eintrag steht dort „kein '
      + 'Preis“.',
    'feld.ModelPrice.input.label': 'Eingabe',
    'feld.ModelPrice.input.hint':
      'Preis je 1 Mio. Eingabe-Token ohne Cache-Anteil, in der eingestellten Währung. Stehen '
      + 'alle drei Preise auf 0, gilt das Modell als nicht gepflegt, nicht als kostenlos.',
    'feld.ModelPrice.cached_input.label': 'Eingabe aus dem Cache',
    'feld.ModelPrice.cached_input.hint':
      'Preis je 1 Mio. Eingabe-Token aus dem Cache des Anbieters; sie zählen nur hier, nicht '
      + 'beim Eingabepreis. Bei 0 kosten sie nichts, sobald ein anderer Preis gepflegt ist: ohne '
      + 'Cache-Rabatt den Eingabepreis eintragen.',
    'feld.ModelPrice.output.label': 'Ausgabe',
    'feld.ModelPrice.output.hint':
      'Preis je 1 Mio. Ausgabe-Token, in der eingestellten Währung. Reasoning-Token stecken '
      + 'schon darin und haben keinen eigenen Preis.',

    // ── Gold-Flows ──────────────────────────────────────────────────
    'feld.GoldFlowsArea.version.label': 'Formatversion',
    'feld.GoldFlowsArea.version.hint':
      'Formatversion der Flows, aktuell 2. Ein Lauf aus dem Studio prüft sie nicht; der '
      + 'Kommandozeilen-Runner verlangt in seiner Datei Version 2.',
    'feld.GoldFlowsArea.flows.label': 'Gold-Flows',
    'feld.GoldFlowsArea.flows.hint':
      'Feste Gespräche für den Gold-Lauf. Jeder Flow läuft in einer neuen Sitzung Zug für Zug '
      + 'gegen den echten Chat; Flows ohne Züge werden übergangen.',
    'feld.GoldFlow.id.label': 'Kennung',
    'feld.GoldFlow.id.hint':
      'Kurze, eindeutige Kennung, etwa GV-LEH-1. Darüber wählt man Flows beim Start eines '
      + 'Gold-Laufs aus; die Auswertung führt Ergebnisse unter ihr.',
    'feld.GoldFlow.persona.label': 'Persona (alt)',
    'feld.GoldFlow.persona.hint':
      'Persona aus dem alten Format. Wird nur angezeigt, wenn „zielgruppe“ fehlt; der '
      + 'LLM-Judge liest allein „zielgruppe“, das sich nur im Rohtext setzen lässt.',
    'feld.GoldFlow.title.label': 'Titel',
    'feld.GoldFlow.title.hint':
      'Name des Flows, wie er in der Startliste und in der Auswertung je Flow erscheint.',
    'feld.GoldFlow.intents.label': 'Intents (alt)',
    'feld.GoldFlow.intents.hint':
      'Intents aus dem alten Format. Werden nicht geprüft, nur in Start- und Laufliste '
      + 'angezeigt.',
    'feld.GoldFlow.turns.label': 'Züge',
    'feld.GoldFlow.turns.hint':
      'Die Nachrichten des Flows, in dieser Reihenfolge in einer Sitzung gesendet. Jeder Zug '
      + 'ist eine echte Chat-Anfrage; mit LLM-Judge kommt je beantwortetem Zug ein '
      + 'Bewertungsaufruf dazu.',
    'feld.GoldFlow.environment.label': 'Einbettungs-Kontext',
    'feld.GoldFlow.environment.hint':
      'Was sonst die einbettende Seite mitschickt, etwa Seitenkontext oder Werkzeugmodus; geht '
      + 'bei jedem Zug mit. Leer = Vorgaben des Servers. Ungültige Werte machen den Zug zum '
      + 'Chat-Fehler, unbekannte Schlüssel fallen weg.',
    'feld.GoldFlow.auf_abruf.label': 'Nur auf Abruf',
    'feld.GoldFlow.auf_abruf.hint':
      'Läuft nur, wenn man den Flow beim Start ausdrücklich wählt — nicht bei „alle“ und nicht '
      + 'in der Kommandozeile ohne --only. Für Flows, die echt schreiben (etwa GV-RED-1).',
    'feld.GoldTurn.message.label': 'Nachricht',
    'feld.GoldTurn.message.hint':
      'Was der Lauf in diesem Zug an den Chat schickt, als hätte eine Person es getippt.',
    'feld.GoldTurn.expect.label': 'Erwartungen',
    'feld.GoldTurn.expect.hint':
      'Fest geprüft: register (sie/du), structure (idoc/cards), tools_any, tools_none, '
      + 'tools_max, text_any, text_none, qr (fehlt = mind. ein Antwortvorschlag, false = '
      + 'keiner). must_offer bewertet nur der LLM-Judge.',
  },
  en: {
    // ── Price table ─────────────────────────────────────────────────
    'feld.PricingArea.currency.label': 'Currency',
    'feld.PricingArea.currency.hint':
      'Three-letter code such as EUR or USD; default EUR. Prices are taken to be in this '
      + 'currency, and the “Costs” page shows amounts in it. Nothing is converted.',
    'feld.PricingArea.models.label': 'Prices per model',
    'feld.PricingArea.models.hint':
      'The key is the model name as the “Costs” page shows it in the “Model” column; '
      + 'gpt-5.4-mini also covers gpt-5.4-mini-2026-03-01. Without an entry it shows “no '
      + 'price” there.',
    'feld.ModelPrice.input.label': 'Input',
    'feld.ModelPrice.input.hint':
      'Price per 1 million input tokens without the cached share, in the set currency. If all '
      + 'three prices are 0, the model counts as not maintained, not as free.',
    'feld.ModelPrice.cached_input.label': 'Cached input',
    'feld.ModelPrice.cached_input.hint':
      'Price per 1 million input tokens served from the provider cache; they count only here, '
      + 'not at the input price. At 0 they cost nothing once another price is set: without a '
      + 'cache discount, enter the input price.',
    'feld.ModelPrice.output.label': 'Output',
    'feld.ModelPrice.output.hint':
      'Price per 1 million output tokens, in the set currency. Reasoning tokens are already '
      + 'included and have no price of their own.',

    // ── Gold flows ──────────────────────────────────────────────────
    'feld.GoldFlowsArea.version.label': 'Format version',
    'feld.GoldFlowsArea.version.hint':
      'Format version of the flows, currently 2. A run started from the studio does not check '
      + 'it; the command-line runner requires version 2 in its file.',
    'feld.GoldFlowsArea.flows.label': 'Gold flows',
    'feld.GoldFlowsArea.flows.hint':
      'Fixed conversations for the gold run. Each flow runs turn by turn in a new session '
      + 'against the real chat; flows without turns are skipped.',
    'feld.GoldFlow.id.label': 'Identifier',
    'feld.GoldFlow.id.hint':
      'Short, unique identifier such as GV-LEH-1. Flows are picked by it when a gold run '
      + 'starts, and the results are listed under it.',
    'feld.GoldFlow.persona.label': 'Persona (legacy)',
    'feld.GoldFlow.persona.hint':
      'Persona from the old format. Only shown when “zielgruppe” is missing; the LLM judge '
      + 'reads “zielgruppe” alone, which can only be set in the source text.',
    'feld.GoldFlow.title.label': 'Title',
    'feld.GoldFlow.title.hint':
      'Name of the flow as it appears in the start list and in the per-flow results.',
    'feld.GoldFlow.intents.label': 'Intents (legacy)',
    'feld.GoldFlow.intents.hint':
      'Intents from the old format. Not checked; only shown in the start list and the run '
      + 'list.',
    'feld.GoldFlow.turns.label': 'Turns',
    'feld.GoldFlow.turns.hint':
      'The messages of the flow, sent in this order within one session. Each turn is a real '
      + 'chat request; with the LLM judge, each answered turn adds one scoring call.',
    'feld.GoldFlow.environment.label': 'Embedding context',
    'feld.GoldFlow.environment.hint':
      'What the embedding page would otherwise send, such as page context or tool mode; it goes '
      + 'with every turn. Empty = server defaults. Invalid values make the turn a chat error, '
      + 'unknown keys are dropped.',
    'feld.GoldFlow.auf_abruf.label': 'On demand only',
    'feld.GoldFlow.auf_abruf.hint':
      'Runs only when the flow is chosen explicitly at the start — not with “all” and not on the '
      + 'command line without --only. For flows that really write (such as GV-RED-1).',
    'feld.GoldTurn.message.label': 'Message',
    'feld.GoldTurn.message.hint':
      'What the run sends to the chat in this turn, as if a person had typed it.',
    'feld.GoldTurn.expect.label': 'Expectations',
    'feld.GoldTurn.expect.hint':
      'Checked by rule: register (sie/du), structure (idoc/cards), tools_any, tools_none, '
      + 'tools_max, text_any, text_none, qr (missing = at least one reply suggestion, false = '
      + 'none). must_offer is scored by the LLM judge only.',
  },
};
