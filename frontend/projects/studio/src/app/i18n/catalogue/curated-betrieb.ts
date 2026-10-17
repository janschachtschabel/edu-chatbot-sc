/**
 * Die kuratierten Konfigurations-Seiten für den Betrieb (C1-d3d): Anzeige,
 * Datenschutz, die ST-9-Abschnitte auf Kosten und Evaluation, Wissen, Agent.
 * Aus `curated.ts` herausgelöst (Paket 6), das über 300 Zeilen stand; das
 * Schlüsselschema steht dort im Kopf.
 */
import type { CataloguePart } from './catalogue-part';

export const CURATED_BETRIEB: CataloguePart = {
  de: {
    // ── Anzeige ─────────────────────────────────────────────────────
    'curated.anzeige.intro':
      'Wie Ergebnisse im Widget erscheinen: welche Boxen, wie viele Einträge, '
      + 'welche Kopfzeilen-Links — und was kleine Geräte davon abweichend bekommen.',
    'curated.anzeige.display.label': 'Darstellungsregeln',
    'curated.anzeige.display.hint': 'Boxen, Grenzen und Textlängen der Ergebnisdarstellung.',
    'curated.anzeige.cardPipeline.label': 'Trefferauswahl und Links',
    'curated.anzeige.cardPipeline.hint':
      'Wohin Treffer-Links zeigen (wirkt immer) und eine Nachauswahl, die nur mit der '
      + 'Umgebungsvariable CARD_PIPELINE_V2 läuft.',
    'curated.anzeige.widgetModes.label': 'Trefferliste im Text',
    'curated.anzeige.widgetModes.hint':
      'Grenzen einer älteren Darstellung, die Treffer als Linkliste an die Antwort hängt. '
      + 'Wirkt derzeit nicht, der Server schaltet sie nie ein.',
    'curated.anzeige.header.label': 'Kopfzeilen-Navigation',
    'curated.anzeige.header.hint': 'Die Links, die das Widget oben anbietet.',
    'curated.anzeige.devices.label': 'Geräte & Anrede',
    // ST-1: bis 2026-09-27 „Abweichende Grenzen für kleine Bildschirme" — die
    // Grenze kürzt aber keine Box im Widget, sie steht nur im Muster-Prompt,
    // und die Anrede je Zielgruppe gehört ebenfalls in diesen Bereich.
    'curated.anzeige.devices.hint':
      'Wie viele Ergebnisse der Muster-Modus je Gerät höchstens nennt, und die Anrede je '
      + 'Zielgruppe.',

    // ── Datenschutz ─────────────────────────────────────────────────
    'curated.datenschutz.intro':
      'Was mitgeschrieben wird und wie lange. Weniger Logging heißt weniger '
      + 'Auswertung — die Analyse-Ansichten zeigen dann entsprechend weniger.',
    'curated.datenschutz.privacy.label': 'Datenschutz',
    'curated.datenschutz.privacy.hint':
      'Welche Inhalte gespeichert werden dürfen und wie lange die Gesprächsverläufe bleiben.',
    'curated.datenschutz.qualityLog.label': 'Qualitäts-Logging',
    'curated.datenschutz.qualityLog.hint':
      'Umfang der Protokolle, aus denen die Analyse gespeist wird.',
    'curated.datenschutz.retention.label': 'Aufbewahrung',
    'curated.datenschutz.retention.hint':
      'Wie lange Gesprächsverläufe und Protokolle bleiben und was davon jetzt fällig ist.',
    'curated.datenschutz.purge.label': 'Gespräche löschen',
    'curated.datenschutz.purge.hint':
      'Gespeicherte Daten aller Sitzungen auf einmal löschen; dazu die Datenbank aufräumen.',

    // ── ST-9: Abschnitte auf Kosten und Evaluation ─────────────────
    'curated.kosten.pricing.label': 'Preistafel',
    'curated.kosten.pricing.hint':
      'Preise je Million Token und Modell. Ein Modell ohne Preis fehlt im Betrag oben.',
    'curated.evaluation.goldFlows.label': 'Gold-Flows',
    'curated.evaluation.goldFlows.hint':
      'Die festen Gesprächsabläufe samt Erwartungen, die ein Gold-Lauf abspielt und prüft.',

    // ── Wissen ──────────────────────────────────────────────────────
    'curated.wissen.intro':
      'Woher der Bot Wissen holt: eigene Dokumente (RAG) und die MCP-Server, über '
      + 'die er WirLernenOnline durchsucht. Ein Wissensbereich entsteht mit dem '
      + 'ersten Dokument darin — angelegt wird er nicht, er wird befüllt.',
    'curated.wissen.areas.label': 'Wissensbereiche',
    'curated.wissen.areas.hint':
      'Was aktuell in der Datenbank liegt, mit Dokumenten und Abschnitten.',
    'curated.wissen.ingest.label': 'Dokumente hinzufügen',
    'curated.wissen.ingest.hint': 'Datei, Webseite oder Text einlesen und in einen Bereich legen.',
    'curated.wissen.ragConfig.label': 'Bereichs-Einstellungen',
    'curated.wissen.ragConfig.hint':
      '„always" wird vor der Antwort vorab durchsucht, „on-demand" nur auf Abruf — jeweils in '
      + 'den Mustern, die den Bereich nutzen.',
    'curated.wissen.retrieval.label': 'Suchwerte',
    'curated.wissen.retrieval.hint':
      'Wie viele Abschnitte die Wissenssuche liefert und ab welcher Ähnlichkeit — für beide '
      + 'Maschinen. Leer gilt die Vorgabe; eine gesetzte Umgebungsvariable geht vor.',
    'curated.wissen.mcp.label': 'MCP-Server',
    'curated.wissen.mcp.hint': 'Werkzeug-Server, die der Bot im Gespräch aufrufen darf.',

    'curated.agent.intro':
      'Zwei Wege, einen Zug zu beantworten. Die Muster-Engine ist der Bestand: '
      + 'Klassifikator, Musterwahl, gebundene Werkzeugliste. Die Agent-Schleife '
      + 'überlässt dem Modell alles — Systemprompt plus voller Werkzeugkatalog, '
      + 'kein Muster, kein Klassifikator. Ausgeliefert wird seit 2026-10-09 die '
      + 'Agent-Schleife; Krise und Drohung beantwortet weiter die Muster-Engine.',
    'curated.agent.engine.label': 'Welche Maschine antwortet',
    'curated.agent.engine.hint':
      'Umschalter, die Deckel der Schleife (Runden, Frist, Token-Budget, Schreibrecht) '
      + 'und die Betriebsschalter: Fast-Modus, Token-Streaming, Agent-Schnellantworten, '
      + 'Schreiben mit dem Gastkonto.',
    'curated.agent.masterSkill.label': 'Master-Skill',
    'curated.agent.masterSkill.hint':
      'Die Gesamtanleitung des Agenten. Gepflegt im Repositorium; hier steht, was gilt.',
    'curated.agent.tester.label': 'Auftrag testen (Gastanwendungen)',
    'curated.agent.tester.hint':
      'Eine Aufgabe stellen und das Ergebnis ansehen — ohne Chat, ohne Sitzung.',
  },

  en: {
    'curated.anzeige.intro':
      'How results appear in the widget: which boxes, how many entries, which '
      + 'header links — and what small devices get instead.',
    'curated.anzeige.display.label': 'Display rules',
    'curated.anzeige.display.hint': 'Boxes, limits and text lengths of the result display.',
    'curated.anzeige.cardPipeline.label': 'Result selection and links',
    'curated.anzeige.cardPipeline.hint':
      'Where result links point (always in effect) and a post-selection that only runs with '
      + 'the CARD_PIPELINE_V2 environment variable.',
    'curated.anzeige.widgetModes.label': 'Result list in the text',
    'curated.anzeige.widgetModes.hint':
      'Limits of an older display that appends results to the answer as a list of links. '
      + 'Currently without effect, the server never switches it on.',
    'curated.anzeige.header.label': 'Header navigation',
    'curated.anzeige.header.hint': 'The links the widget offers at the top.',
    'curated.anzeige.devices.label': 'Devices & form of address',
    'curated.anzeige.devices.hint':
      'How many results the pattern engine names at most per device, and the form of '
      + 'address per target group.',

    'curated.datenschutz.intro':
      'What is recorded and for how long. Less logging means less analysis — the '
      + 'analysis views then show correspondingly less.',
    'curated.datenschutz.privacy.label': 'Privacy',
    'curated.datenschutz.privacy.hint':
      'Which content may be stored, and how long conversations are kept.',
    'curated.datenschutz.qualityLog.label': 'Quality logging',
    'curated.datenschutz.qualityLog.hint': 'Extent of the logs that feed the analysis.',
    'curated.datenschutz.retention.label': 'Retention',
    'curated.datenschutz.retention.hint':
      'How long conversations and logs are kept and what is due now.',
    'curated.datenschutz.purge.label': 'Delete conversations',
    'curated.datenschutz.purge.hint':
      'Delete the stored data of all sessions at once; plus tidying up the database.',

    'curated.kosten.pricing.label': 'Price table',
    'curated.kosten.pricing.hint':
      'Prices per million tokens and model. A model without a price is missing from the '
      + 'amount above.',
    'curated.evaluation.goldFlows.label': 'Gold flows',
    'curated.evaluation.goldFlows.hint':
      'The fixed conversation scripts with expectations that a gold run plays and checks.',

    'curated.wissen.intro':
      'Where the bot gets knowledge from: its own documents (RAG) and the MCP '
      + 'servers it searches WirLernenOnline through. A knowledge area comes into '
      + 'being with its first document — it is not created, it is filled.',
    'curated.wissen.areas.label': 'Knowledge areas',
    'curated.wissen.areas.hint':
      'What currently lies in the database, with documents and sections.',
    'curated.wissen.ingest.label': 'Add documents',
    'curated.wissen.ingest.hint': 'Ingest a file, a web page or text and put it into an area.',
    'curated.wissen.ragConfig.label': 'Area settings',
    'curated.wissen.ragConfig.hint':
      '“always” is searched before the answer, “on-demand” only on request — in each case in '
      + 'the patterns that use the area.',
    'curated.wissen.retrieval.label': 'Search values',
    'curated.wissen.retrieval.hint':
      'How many passages the knowledge search returns and from which similarity on — for both '
      + 'engines. Empty means the default; a set environment variable takes precedence.',
    'curated.wissen.mcp.label': 'MCP servers',
    'curated.wissen.mcp.hint': 'Tool servers the bot may call during a conversation.',

    'curated.agent.intro':
      'Two ways to answer a turn. The pattern engine is the established path: classifier, '
      + 'pattern selection, a bound tool list. The agent loop leaves everything '
      + 'to the model — system prompt plus the full tool catalogue, no pattern, '
      + 'no classifier. Since 2026-10-09 the agent loop is what ships; crisis and '
      + 'threat are still answered by the pattern engine.',
    'curated.agent.engine.label': 'Which engine answers',
    'curated.agent.engine.hint':
      'The switch, the loop’s caps (rounds, deadline, token budget, write mode) and the '
      + 'operation switches: fast mode, token streaming, agent quick replies, writing with '
      + 'the guest account.',
    'curated.agent.masterSkill.label': 'Master skill',
    'curated.agent.masterSkill.hint':
      'The agent’s overall instructions. Maintained in the repository; this shows what applies.',
    'curated.agent.tester.label': 'Test a task (host applications)',
    'curated.agent.tester.hint':
      'Give it a task and look at the result — no chat, no session.',
  },
};
