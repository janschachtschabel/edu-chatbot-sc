/**
 * Feldtexte (ST-1) der Seite „Agent & Maschine“, Bereich `01-base/engine`:
 * Maschinenwahl, Deckel der Agent-Schleife, anonyme Deckel, Rolle und Schutzregeln,
 * Skill-Brücke der Muster-Engine, Betriebsschalter (Paket 7). Ausführlich:
 * `docs/agent-modus.md`.
 *
 * Schlüsselschema wie in `fields-layer-doc.ts`. Das Sicherheits-Gate läuft in jeder
 * Maschine (`graph/nodes/assess.py`) und am Endpunkt (`services/agent_gate.py`); sein
 * früherer Schalter `agent.safety` ist gestrichen (Paket 7). Die anonymen Deckel gelten nur im Chat
 * (`services/agent_deckel.py`), `agent_rolle` nur für die Schleife im Chat
 * (`services/agent_kopf.py`) — `/api/agent` hat einen festen Systemtext.
 */
import type { CataloguePart } from './catalogue-part';

export const FIELDS_AGENT: CataloguePart = {
  de: {
    'feld.EngineArea.mode.label': 'Maschine',
    'feld.EngineArea.mode.hint':
      'Wer Chat-Züge beantwortet: pattern = Muster-Engine (Klassifikator, Musterwahl), agent '
      + '= Agent-Schleife mit vollem Werkzeugkatalog. Einbettungen können übersteuern. Krise '
      + 'und Drohung beantwortet stets die Muster-Engine.',
    'feld.EngineArea.agent.label': 'Deckel der Agent-Schleife',
    'feld.EngineArea.agent.hint':
      'Grenzen und Schreibrecht jedes Laufs der Agent-Schleife, im Chat wie am Endpunkt '
      + '/api/agent. Welcher der drei Deckel zuerst greift, beendet den Lauf.',
    'feld.AgentLimits.max_iterations.label': 'Höchstzahl Runden',
    'feld.AgentLimits.max_iterations.hint':
      'Wie viele Runden (je ein Modellaufruf samt Werkzeugen) ein Lauf höchstens hat; danach '
      + 'endet er mit max_iterations. 1 bis 50, Vorgabe 30.',
    'feld.AgentLimits.deadline_s.label': 'Frist (Sekunden)',
    'feld.AgentLimits.deadline_s.hint':
      'Zeitgrenze je Lauf in Sekunden, 5 bis 1800, Vorgabe 900. Geprüft vor jeder Runde: eine '
      + 'laufende Runde wird nicht abgebrochen, der Lauf endet danach mit deadline.',
    'feld.AgentLimits.token_budget.label': 'Token-Budget',
    'feld.AgentLimits.token_budget.hint':
      'Höchstzahl Tokens je Lauf, Eingabe plus Ausgabe über alle Runden zusammen; mindestens '
      + '1000, Vorgabe 900.000. Geprüft vor jeder Runde. Deckelt die Kosten der Schleife.',
    'feld.AgentLimits.write_mode.label': 'Schreibrecht',
    'feld.AgentLimits.write_mode.hint':
      'propose = kuratierende Werkzeuge kommen nur bis zur Vorschau, bestätigen muss ein '
      + 'Mensch. execute = der Lauf darf selbst bestätigen, aber nur mit angemeldeter Person; '
      + 'sonst gilt propose.',
    'feld.AgentLimits.anonymous.label': 'Deckel ohne Anmeldung',
    'feld.AgentLimits.anonymous.hint':
      'Engere Deckel für Chat-Züge ohne persönliche Anmeldung; je Deckel gilt der kleinere '
      + 'Wert. Beim Anheben der normalen Deckel diese mit anheben oder leeren. Nicht für '
      + '/api/agent.',
    'feld.AnonymousLimits.max_iterations.label': 'Höchstzahl Runden',
    'feld.AnonymousLimits.max_iterations.hint':
      'Runden-Deckel für Chat-Züge ohne Anmeldung, 1 bis 50. Wirkt nur, wenn kleiner als der '
      + 'normale Deckel; leer = wie angemeldet.',
    'feld.AnonymousLimits.deadline_s.label': 'Frist (Sekunden)',
    'feld.AnonymousLimits.deadline_s.hint':
      'Frist in Sekunden für Chat-Züge ohne Anmeldung, 5 bis 1800. Wirkt nur, wenn kleiner '
      + 'als der normale Deckel; leer = wie angemeldet.',
    'feld.AnonymousLimits.token_budget.label': 'Token-Budget',
    'feld.AnonymousLimits.token_budget.hint':
      'Token-Budget für Chat-Züge ohne Anmeldung, mindestens 1000. Wirkt nur, wenn kleiner '
      + 'als der normale Deckel; leer = wie angemeldet.',
    'feld.EngineArea.agent_rolle.label': 'Rolle und Grenzen',
    'feld.EngineArea.agent_rolle.hint':
      'Kopf jeder Agent-Kette im Chat: Rolle und Schutzregeln, ergänzt um Anrede je '
      + 'Zielgruppe und Sprache. Steht vor dem Master-Skill und geht ihm vor. Am Endpunkt '
      + '/api/agent ohne Wirkung.',
    'feld.AgentRolle.rolle.label': 'Rolle',
    'feld.AgentRolle.rolle.hint':
      'Erster Systemtext der Agent-Schleife im Chat: wer der Agent ist, wie er arbeitet und '
      + 'antwortet. Leer = die mitgelieferte Vorgabe.',
    'feld.AgentRolle.schutzregeln.label': 'Schutzregeln',
    'feld.AgentRolle.schutzregeln.hint':
      'Kennungen aus den Leitplanken (etwa R-05), die auch im Agent-Modus gelten; ihr '
      + 'Wortlaut samt Erläuterung kommt in den Kopf. Unbekannte Kennungen entfallen, die '
      + 'übrigen Leitplanken gelten dort nicht.',
    'feld.EngineArea.muster_skills.label': 'Skills im Muster-Modus',
    'feld.EngineArea.muster_skills.hint':
      'Gibt Werkzeug-Mustern der Muster-Engine get_skill_registry und get_skill dazu, wenn '
      + 'freigegebene Skills im Spiel sind. Nicht bei Mustern ohne Werkzeuge (Krise, '
      + 'Drohung). Vorgabe aus.',
    // ── Betrieb (Paket 7, S1–S4) ──────────────────────────────────────
    'feld.EngineArea.betrieb.label': 'Betrieb',
    'feld.EngineArea.betrieb.hint':
      'Schalter des laufenden Betriebs, wirksam ohne Neustart. Nennt ein Schalter unter '
      + '„Umgebung:“ eine Variable und ist sie gesetzt, gilt sie statt des Schalters.',
    'feld.Betrieb.fast_modus.label': 'Fast-Modus (OpenAI)',
    'feld.Betrieb.fast_modus.hint':
      'Schnellere OpenAI-Stufe „fast“: ein Zug etwa 30 % schneller — zum 4- bis 5-fachen '
      + 'Tokenpreis und ohne EU-Datenhaltung. Wirkt nur bei OpenAI direkt mit gpt-5 oder '
      + 'gpt-6. Umgebung: LLM_SERVICE_TIER. Vorgabe aus.',
    'feld.Betrieb.token_streaming.label': 'Token-Streaming',
    'feld.Betrieb.token_streaming.hint':
      'Die Antwort erscheint, während das Modell schreibt. Im Agent-Modus erst mit den '
      + 'Agent-Schnellantworten. Umgebung: CHAT_TOKEN_STREAMING. Vorgabe an.',
    'feld.Betrieb.agent_schnellantworten.label': 'Agent-Schnellantworten',
    'feld.Betrieb.agent_schnellantworten.hint':
      'Der Agent schreibt die Schnellantworten gleich mit, statt sie in einem zweiten '
      + 'Aufruf zu holen (ein Zug 6,8 statt 12,2 s) — und nur so streamt der Agent. Der '
      + 'Abschnitt „Schnellantworten“ im Master-Skill sollte dazu passen. Umgebung: '
      + 'AGENT_INLINE_QUICK_REPLIES. Vorgabe an.',
    'feld.Betrieb.gastkonto_schreibt.label': 'Gastkonto darf schreiben',
    'feld.Betrieb.gastkonto_schreibt.hint':
      'Achtung: Eingeschaltet legt der Bot auch ohne Anmeldung Inhalte an und nimmt sie in '
      + 'Sammlungen auf — mit dem Dienstkonto der Anlage aus MCP_AUTH_TOKEN, für jede '
      + 'Person im Chat, in beiden Modi. Aus: schreiben kann nur, wer mit dem eigenen '
      + 'WLO-Konto angemeldet ist. Nur dieser Schalter, keine Umgebungsvariable. Vorgabe aus.',
  },
  en: {
    'feld.EngineArea.mode.label': 'Engine',
    'feld.EngineArea.mode.hint':
      'Who answers chat turns: pattern = pattern engine (classifier, pattern choice), agent = '
      + 'agent loop with the full tool catalogue. Embeddings can override this. Crisis and '
      + 'threat always go to the pattern engine.',
    'feld.EngineArea.agent.label': 'Agent loop limits',
    'feld.EngineArea.agent.hint':
      'Limits and write mode of every agent loop run, in the chat and at the /api/agent '
      + 'endpoint. Whichever of the three limits is reached first ends the run.',
    'feld.AgentLimits.max_iterations.label': 'Maximum rounds',
    'feld.AgentLimits.max_iterations.hint':
      'How many rounds (one model call plus its tools each) a run may have at most; then it '
      + 'ends with max_iterations. 1 to 50, default 30.',
    'feld.AgentLimits.deadline_s.label': 'Deadline (seconds)',
    'feld.AgentLimits.deadline_s.hint':
      'Time limit per run in seconds, 5 to 1800, default 900. Checked before each round: a '
      + 'running round is not cut off, the run then ends with deadline.',
    'feld.AgentLimits.token_budget.label': 'Token budget',
    'feld.AgentLimits.token_budget.hint':
      'Maximum tokens per run, input plus output summed over all rounds; at least 1000, '
      + 'default 900,000. Checked before each round. Caps the cost of the loop.',
    'feld.AgentLimits.write_mode.label': 'Write mode',
    'feld.AgentLimits.write_mode.hint':
      'propose = curating tools only get as far as the preview; a person must confirm. '
      + 'execute = the run may confirm by itself, but only with a signed-in person; otherwise '
      + 'propose applies.',
    'feld.AgentLimits.anonymous.label': 'Limits without sign-in',
    'feld.AgentLimits.anonymous.hint':
      'Tighter limits for chat turns without a personal sign-in; for each limit the smaller '
      + 'value applies. When raising the normal limits, raise or clear these too. Not for '
      + '/api/agent.',
    'feld.AnonymousLimits.max_iterations.label': 'Maximum rounds',
    'feld.AnonymousLimits.max_iterations.hint':
      'Round limit for chat turns without sign-in, 1 to 50. Only takes effect if smaller than '
      + 'the normal limit; empty = as signed in.',
    'feld.AnonymousLimits.deadline_s.label': 'Deadline (seconds)',
    'feld.AnonymousLimits.deadline_s.hint':
      'Deadline in seconds for chat turns without sign-in, 5 to 1800. Only takes effect if '
      + 'smaller than the normal limit; empty = as signed in.',
    'feld.AnonymousLimits.token_budget.label': 'Token budget',
    'feld.AnonymousLimits.token_budget.hint':
      'Token budget for chat turns without sign-in, at least 1000. Only takes effect if '
      + 'smaller than the normal limit; empty = as signed in.',
    'feld.EngineArea.agent_rolle.label': 'Role and boundaries',
    'feld.EngineArea.agent_rolle.hint':
      'Head of every agent chain in the chat: role and safeguard rules, plus form of address '
      + 'per audience and language. Comes before the master skill and takes precedence. No '
      + 'effect at /api/agent.',
    'feld.AgentRolle.rolle.label': 'Role',
    'feld.AgentRolle.rolle.hint':
      'First system text of the agent loop in the chat: who the agent is, how it works and '
      + 'answers. Empty = the shipped default.',
    'feld.AgentRolle.schutzregeln.label': 'Safeguard rules',
    'feld.AgentRolle.schutzregeln.hint':
      'Identifiers from the guardrails (such as R-05) that also apply in agent mode; their '
      + 'wording and explanation go into the head. Unknown identifiers are dropped; the other '
      + 'guardrails do not apply there.',
    'feld.EngineArea.muster_skills.label': 'Skills in pattern mode',
    'feld.EngineArea.muster_skills.hint':
      'Adds get_skill_registry and get_skill to tool patterns of the pattern engine when '
      + 'released skills are in play. Not for patterns without tools (crisis, threat). '
      + 'Default off.',
    'feld.EngineArea.betrieb.label': 'Operation',
    'feld.EngineArea.betrieb.hint':
      'Switches of the running operation, effective without a restart. If a switch names a '
      + 'variable under “Environment:” and it is set, it applies instead of the switch.',
    'feld.Betrieb.fast_modus.label': 'Fast mode (OpenAI)',
    'feld.Betrieb.fast_modus.hint':
      'Faster OpenAI tier “fast”: a turn about 30 % quicker — at 4 to 5 times the token '
      + 'price and without EU data residency. Only with OpenAI directly and gpt-5 or '
      + 'gpt-6. Environment: LLM_SERVICE_TIER. Default off.',
    'feld.Betrieb.token_streaming.label': 'Token streaming',
    'feld.Betrieb.token_streaming.hint':
      'The answer appears while the model is writing it. In agent mode only together with '
      + 'the agent quick replies. Environment: CHAT_TOKEN_STREAMING. Default on.',
    'feld.Betrieb.agent_schnellantworten.label': 'Agent quick replies',
    'feld.Betrieb.agent_schnellantworten.hint':
      'The agent writes the quick replies along with its answer instead of fetching them in '
      + 'a second call (a turn 6.8 instead of 12.2 s) — and only then does the agent stream. '
      + 'The master skill’s section on quick replies should match. Environment: '
      + 'AGENT_INLINE_QUICK_REPLIES. Default on.',
    'feld.Betrieb.gastkonto_schreibt.label': 'Guest account may write',
    'feld.Betrieb.gastkonto_schreibt.hint':
      'Caution: when on, the bot also creates content and adds it to collections without a '
      + 'sign-in — with the installation’s service account from MCP_AUTH_TOKEN, for every '
      + 'person in the chat, in both modes. Off: only people signed in with their own WLO '
      + 'account can write. Only this switch, no environment variable. Default off.',
  },
};
