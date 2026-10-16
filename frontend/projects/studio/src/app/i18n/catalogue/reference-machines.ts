/**
 * Die Architektur-Referenz für BEIDE Maschinen (Paket 6, S3 — Rest von ST-5).
 *
 * Die Referenz war ein Port der ALT-Seite und beschrieb nur die Muster-Maschine;
 * die Agent-Schleife kam außerhalb der Widget-Tabelle nicht vor. Seit dem
 * Entscheid D-15 (Z2) bleiben beide Maschinen im Betrieb. Dieser Abschnitt
 * steht deshalb vorn: was beide teilen, wo sie sich trennen, wer wählt.
 *
 * Inhaltliche Quelle: `docs/architektur.md` §4.3 und `docs/agent-modus.md` §1;
 * welche Einstellung wo wirkt, zeigt live die Zuordnung `/config/effects`.
 */
import type { CataloguePart } from './catalogue-part';

export const REFERENCE_MACHINES: CataloguePart = {
  de: {
    'rm.title': 'Zwei Maschinen: Muster und Agent',
    'rm.lead':
      'Den Chat beantworten zwei Maschinen. Die *Muster-Maschine* ordnet jede Nachricht '
      + 'ein, wählt ein Gesprächsmuster und antwortet nach dessen Regeln. Die '
      + '*Agent-Schleife* arbeitet mit einer Gesamtanleitung (Master-Skill) und ruft '
      + 'Werkzeuge, bis sie eine Antwort hat.',
    'rm.choice':
      'Welche antwortet, legt die Seite „Agent & Maschine" fest (`01-base/engine`). Eine '
      + 'Einbettung wählt mit dem Attribut `engine` die andere, eine einzelne Anfrage mit '
      + 'der Kopfzeile `X-Boerdi-Engine`.',
    'rm.current.pattern': 'Vorgabe dieser Anlage: *Muster-Maschine*.',
    'rm.current.agent': 'Vorgabe dieser Anlage: *Agent-Schleife*.',

    'rm.sharedTitle': 'Was beide teilen',
    'rm.shared.before':
      '*Vorlauf:* Tour, Seitenkontext, Kontext-Gruß und Direkt-Aktionen, darunter die '
      + 'Abnahme eines Schreibvorgangs. Tour, Kontext-Gruß und Direkt-Aktionen können den '
      + 'Zug beenden, bevor eine Maschine antwortet; der Seitenkontext läuft immer weiter.',
    'rm.shared.safety':
      '*Sicherheit:* Krisen-Regeln und Moderation für jede Nachricht, das '
      + 'Sicherheitsprotokoll und Policy-Regeln, die einzelne Werkzeuge sperren.',
    'rm.shared.after':
      '*Nachbereitung:* Karten, Dokumente und Schnellantworten zusammensetzen, dann die '
      + 'Antwort speichern.',

    'rm.flowTitle': 'Der Weg eines Zugs',
    'rm.flowLead':
      'Jede Nachricht läuft durch dieselben 13 Knoten (`graph/build.py`); drei davon können '
      + 'den Zug früh beenden. Die Maschine wirkt nur in `assess`, `merge`, `route`, '
      + '`respond` und `persist` — alle anderen Knoten laufen in beiden Modi gleich.',
    'rm.node.exit': 'Kann den Zug hier beenden.',
    'rm.node.setup': 'Sitzung laden oder anlegen, Verlauf und Gesprächszustand lesen.',
    'rm.node.tour': 'Die Web-Tour: Start, nächster Schritt oder Antwort in der Gruppe.',
    'rm.node.page_context_enrich':
      'Seitenkontext: die Kennungen der Gastseite übernehmen und ihre Metadaten nachschlagen.',
    'rm.node.context_greeting':
      'Gruß zur Seite beim Öffnen des Chats, mit Aktionen — ohne Sprachmodell.',
    'rm.node.persist_user': 'Die Nachricht der Person speichern.',
    'rm.node.preflight':
      'Grenzen je Zeitfenster und Direkt-Aktionen, darunter die Abnahme eines Schreibvorgangs.',
    'rm.node.assess':
      'Sicherheit, Einordnung und Gedächtnis nebeneinander; im Agent-Modus ohne Einordnung.',
    'rm.node.safety_log': 'Die Sicherheitsentscheidung protokollieren.',
    'rm.node.merge': 'Erkannte Angaben in den Gesprächszustand übernehmen.',
    'rm.node.route':
      'Regeln anwenden; im Muster-Modus das Muster wählen und die Wissensbereiche festlegen.',
    'rm.node.respond': 'Die Antwort erzeugen — nach dem Muster oder in der Agent-Schleife.',
    'rm.node.assemble': 'Karten, Dokumente und Schnellantworten zusammensetzen.',
    'rm.node.persist': 'Den Zug speichern, mit Debug-Block und Kosten.',

    'rm.diffTitle': 'Wo sie sich unterscheiden',
    'rm.col.aspect': 'Was',
    'rm.col.pattern': 'Muster-Maschine',
    'rm.col.agent': 'Agent-Schleife',
    'rm.row.classify': 'Einordnung',
    'rm.row.classify.pattern': 'Ein Klassifikator erkennt Persona, Intent, Signale, Entitäten und Zustand.',
    'rm.row.classify.agent':
      'Keine. Die Persona-Einstellungen wirken über die Anrede im Kopf des Agenten.',
    'rm.row.steer': 'Steuerung',
    'rm.row.steer.pattern': 'Das gewählte Muster, danach die Modulation von Ton, Länge und Format.',
    'rm.row.steer.agent':
      'Der Kopf (Rolle, Anrede, Schutzregeln, Sprache) und der Master-Skill.',
    'rm.row.tools': 'Werkzeuge',
    'rm.row.tools.pattern': 'Je Muster gebunden; Suchen starten nach dem Intent schon vorab.',
    'rm.row.tools.agent':
      'Der ganze Katalog ohne gesperrte Werkzeuge, dazu `wissen_suchen`, `zeige_dokument` '
      + 'und auf Wunsch der Gastanwendung `liefere_ergebnis`.',
    'rm.row.flow': 'Ablauf',
    'rm.row.flow.pattern': 'Eine Antwort; Werkzeuge laufen dazwischen.',
    'rm.row.flow.agent':
      'Eine Schleife bis zur Antwort oder bis zu einem Deckel: Runden, Frist, '
      + 'Token-Budget, Stillstand.',
    'rm.row.write': 'Schreiben',
    'rm.row.write.pattern': 'Vorschau, dann die Abnahme durch die Person.',
    'rm.row.write.agent': 'Vorschau, dann die Abnahme — nur mit persönlicher Anmeldung.',

    'rm.crisis':
      '*Krise und Bedrohung:* Erzwingt die Sicherheitsprüfung das Krisen- oder '
      + 'Bedrohungsmuster (M01, M02), antwortet auch im Agent-Modus die Muster-Maschine.',
    'rm.effects':
      'Welche Einstellung in welcher Maschine wirkt, steht im Kopf jedes Abschnitts '
      + 'unter „Wirkt in".',
  },
  en: {
    'rm.title': 'Two engines: pattern and agent',
    'rm.lead':
      'Two engines answer the chat. The *pattern engine* classifies each message, picks '
      + 'a conversation pattern and answers by its rules. The *agent loop* works from '
      + 'overall instructions (the master skill) and calls tools until it has an answer.',
    'rm.choice':
      'Which one answers is set on the page “Agent & engine” (`01-base/engine`). An '
      + 'embedding picks the other one with the attribute `engine`, a single request '
      + 'with the header `X-Boerdi-Engine`.',
    'rm.current.pattern': 'Default of this installation: *pattern engine*.',
    'rm.current.agent': 'Default of this installation: *agent loop*.',

    'rm.sharedTitle': 'What both share',
    'rm.shared.before':
      '*Before:* tour, page context, context greeting and direct actions, among them '
      + 'approving a write. Tour, context greeting and direct actions can end the turn '
      + 'before an engine answers; the page context always carries on.',
    'rm.shared.safety':
      '*Safety:* crisis rules and moderation for every message, the safety log and '
      + 'policy rules that block single tools.',
    'rm.shared.after':
      '*After:* assemble cards, documents and quick replies, then store the answer.',

    'rm.flowTitle': 'The path of a turn',
    'rm.flowLead':
      'Every message passes through the same 13 nodes (`graph/build.py`); three of them can '
      + 'end the turn early. The engine only matters in `assess`, `merge`, `route`, '
      + '`respond` and `persist` — every other node runs the same in both modes.',
    'rm.node.exit': 'Can end the turn here.',
    'rm.node.setup': 'Load or create the session, read the history and the conversation state.',
    'rm.node.tour': 'The website tour: start, next step or the answer in the group step.',
    'rm.node.page_context_enrich':
      'Page context: take over the IDs of the host page and look up its metadata.',
    'rm.node.context_greeting':
      'A greeting for the page when the chat opens, with actions — no language model.',
    'rm.node.persist_user': 'Store the person’s message.',
    'rm.node.preflight':
      'Limits per time window and direct actions, among them approving a write.',
    'rm.node.assess':
      'Safety, classification and memory side by side; in agent mode without classification.',
    'rm.node.safety_log': 'Log the safety decision.',
    'rm.node.merge': 'Take recognised details over into the conversation state.',
    'rm.node.route':
      'Apply the rules; in pattern mode pick the pattern and fix the knowledge areas.',
    'rm.node.respond': 'Produce the answer — by the pattern or in the agent loop.',
    'rm.node.assemble': 'Put cards, documents and quick replies together.',
    'rm.node.persist': 'Store the turn, with the debug block and the costs.',

    'rm.diffTitle': 'Where they differ',
    'rm.col.aspect': 'What',
    'rm.col.pattern': 'Pattern engine',
    'rm.col.agent': 'Agent loop',
    'rm.row.classify': 'Classification',
    'rm.row.classify.pattern': 'A classifier detects persona, intent, signals, entities and state.',
    'rm.row.classify.agent':
      'None. The persona settings act through the form of address in the agent’s head.',
    'rm.row.steer': 'Steering',
    'rm.row.steer.pattern': 'The chosen pattern, then the modulation of tone, length and format.',
    'rm.row.steer.agent':
      'The head (role, form of address, protection rules, language) and the master skill.',
    'rm.row.tools': 'Tools',
    'rm.row.tools.pattern': 'Bound per pattern; searches start ahead of time by intent.',
    'rm.row.tools.agent':
      'The whole catalogue minus blocked tools, plus `wissen_suchen`, `zeige_dokument` '
      + 'and, if the host application asks for it, `liefere_ergebnis`.',
    'rm.row.flow': 'Flow',
    'rm.row.flow.pattern': 'One answer; tools run in between.',
    'rm.row.flow.agent':
      'A loop until the answer or a cap: rounds, deadline, token budget, stagnation.',
    'rm.row.write': 'Writing',
    'rm.row.write.pattern': 'Preview, then approval by the person.',
    'rm.row.write.agent': 'Preview, then approval — only with a personal login.',

    'rm.crisis':
      '*Crisis and threat:* if the safety check forces the crisis or threat pattern '
      + '(M01, M02), the pattern engine answers even in agent mode.',
    'rm.effects':
      'Which setting acts in which engine is shown in the head of every section '
      + 'under “Takes effect in”.',
  },
};
