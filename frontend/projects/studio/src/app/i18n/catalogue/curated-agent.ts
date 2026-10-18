/**
 * Paket 14: Texte der Seiten im Agent-Arbeitsbereich, der neuen gemeinsamen Seite „Tour &
 * Lotse“, der Seite „Betrieb“ und der Skill-Brücke auf „Patterns“.
 */
import type { CataloguePart } from './catalogue-part';

export const CURATED_AGENT: CataloguePart = {
  de: {
    'curated.agentRolle.intro':
      'Was der Agent bei jedem Zug zuerst liest: seine Rolle und die Regeln, die immer gelten — '
      + 'dazu die Grenzen der Schleife. Wie er vorgeht, steht im Master-Skill (Seite „Skills“).',
    'curated.agentRolle.rolle.label': 'Rolle, Schutzregeln und Grenzen',
    'curated.agentRolle.rolle.hint':
      'Der erste Absatz jedes Agent-Prompts, die Leitplanken, die er wörtlich mitbekommt, und '
      + 'wie weit eine Schleife gehen darf (Runden, Frist, Budget).',
    'curated.agentRolle.anrede.label': 'Anrede je Zielgruppe',
    'curated.agentRolle.anrede.hint':
      'Du oder Sie je Zielgruppe — gilt in beiden Modi; die übrigen Persona-Einstellungen '
      + 'stehen unter Muster › Dimensionen.',
    'curated.agentRolle.guardrails.label': 'Leitplanken',
    'curated.agentRolle.guardrails.hint':
      'Die Regel-Tabelle, aus der die Schutzregeln oben stammen.',
    'curated.agentRolle.safety.label': 'Sicherheitsstufe',
    'curated.agentRolle.safety.hint':
      'Gate, Protokoll und Drosselung laufen vor jeder Maschine.',
    'curated.agentRolle.policy.label': 'Werkzeug-Regelwerk',
    'curated.agentRolle.policy.hint':
      'Welche Werkzeuge eine Regel sperrt. Im Agent-Modus greifen nur Regeln ohne '
      + 'Anliegen-Bedingung — der Agent erkennt keine Anliegen (Intents).',
    'curated.agentRolle.schutz.label': 'Schutzantworten (Krise und Drohung)',
    'curated.agentRolle.schutz.hint':
      'M01 und M02 beantworten Krisen- und Drohungs-Züge — auch im Agent-Modus, über den '
      + 'Muster-Weg. Alle übrigen Muster stehen im Muster-Arbeitsbereich.',
    'curated.agentPrompt.intro':
      'Die Kette, wie das Modell sie liest, und zwei Probeläufe: im Chat und als Auftrag für '
      + 'Gastanwendungen. Den Wortlaut des Master-Skills zeigt die Seite „Skills“.',
    'curated.fuehrung.intro':
      'Wege auf der Plattform: die Website-Tour und der Lotsen-Modus. Beide wirken in jedem '
      + 'Betriebsmodus.',
    'curated.patterns.skillBruecke.label': 'Skill-Brücke',
    'curated.patterns.skillBruecke.hint':
      'Gibt jedem Muster-Zug die freigegebenen Skills einer Sammlung mit.',
    'curated.betrieb.intro':
      'Mit welcher Maschine der Server antwortet, wenn eine Einbettung nichts wählt, und die '
      + 'Schalter für den Betrieb beider Modi.',
    'curated.betrieb.engine.label': 'Vorgabe-Maschine und Betriebsschalter',
    'curated.betrieb.engine.hint':
      'Muster oder Agent als Vorgabe, dazu Fast-Modus, Token-Streaming, Schnellantworten und '
      + 'Schreiben mit dem Gastkonto.',
    'curated.betrieb.hinweis.streamingOhneSchnellantworten':
      'Token-Streaming wirkt im Agent-Modus nur zusammen mit den Agent-Schnellantworten — '
      + 'so kommt die Antwort weiter am Stück. Agent-Schnellantworten einschalten.',
    // Agent-Übersicht (C1)
    'agentUebersicht.intro':
      'Der Agent-Arbeitsbereich: was der Agent liest, was er darf und wie er sich in der '
      + 'Evaluation bewährt.',
    'agentUebersicht.zustand.agent': 'Der Server antwortet mit der Agent-Schleife.',
    'agentUebersicht.zustand.pattern':
      'Der Server antwortet mit der Muster-Maschine; Einbettungen können die Agent-Schleife '
      + 'wählen.',
    'agentUebersicht.zustand.unbekannt':
      'Mit welcher Maschine der Server antwortet, ist gerade nicht lesbar.',
    'agentUebersicht.betrieb': 'Vorgabe-Maschine ändern',
    'agentUebersicht.wege': 'Weiter im Agent-Arbeitsbereich',
    'agentUebersicht.wege.evaluation': 'Golden-Läufe der Agent-Schleife und ihr Verlauf',
    'agentUebersicht.lauf.titel': 'Letzter Lauf der Agent-Schleife',
    'agentUebersicht.lauf.text': 'Lauf vom {datum}: Ø {score}',
    'agentUebersicht.lauf.leer': 'Noch kein fertiger Lauf der Agent-Schleife.',
    'agentUebersicht.lauf.laedt': 'Läufe werden geladen …',
    'agentUebersicht.lauf.link': 'Zur Evaluation',
    // Panel „Anrede je Zielgruppe“ (C2)
    'anrede.caption': 'Anrede je Zielgruppe',
    'anrede.col.zielgruppe': 'Zielgruppe',
    'anrede.col.anrede': 'Anrede',
    'anrede.feld': 'Anrede für {name}',
    'anrede.wert.siezen': 'Sie',
    'anrede.wert.duzen': 'du',
    'anrede.wert.wie_user': 'wie die Person schreibt',
    'anrede.wert.neutral': 'ohne direkte Anrede',
    'anrede.wert.unbekannt': 'unbekannt: {wert}',
    'anrede.speichern': 'Speichern',
    'anrede.speichert': 'Speichert …',
    'anrede.gespeichert': 'Gespeichert',
    'anrede.laedt': 'Zielgruppen werden geladen …',
    'anrede.leer': 'Keine Zielgruppen angelegt — Personas stehen im Muster-Arbeitsbereich unter '
      + '„Dimensionen“.',
    'anrede.rueckfall':
      'Bei „wie die Person schreibt“ gilt, bis sie geschrieben hat, der Rückfall im Abschnitt '
      + 'darunter.',
  },
  en: {
    'curated.agentRolle.intro':
      'What the agent reads first on every turn: its role and the rules that always apply — '
      + 'plus the limits of the loop. How it proceeds is in the master skill (page “Skills”).',
    'curated.agentRolle.rolle.label': 'Role, safeguard rules and limits',
    'curated.agentRolle.rolle.hint':
      'The first paragraph of every agent prompt, the guardrails it receives verbatim, and how '
      + 'far a loop may go (rounds, deadline, budget).',
    'curated.agentRolle.anrede.label': 'Form of address per audience',
    'curated.agentRolle.anrede.hint':
      'Informal or formal per audience — applies in both modes; the other persona settings '
      + 'are under Patterns › Dimensions.',
    'curated.agentRolle.guardrails.label': 'Guardrails',
    'curated.agentRolle.guardrails.hint':
      'The rule table the safeguard rules above come from.',
    'curated.agentRolle.safety.label': 'Safety level',
    'curated.agentRolle.safety.hint':
      'Gate, log and throttling run before either engine.',
    'curated.agentRolle.policy.label': 'Tool policy',
    'curated.agentRolle.policy.hint':
      'Which tools a rule locks. In agent mode only rules without an intent condition apply — '
      + 'the agent does not detect intents.',
    'curated.agentRolle.schutz.label': 'Protective answers (crisis and threat)',
    'curated.agentRolle.schutz.hint':
      'M01 and M02 answer crisis and threat turns — in agent mode too, via the pattern path. '
      + 'All other patterns are in the patterns workspace.',
    'curated.agentPrompt.intro':
      'The chain as the model reads it and two test runs: in the chat and as a task for host '
      + 'applications. The page “Skills” shows the master skill’s text.',
    'curated.fuehrung.intro':
      'Ways around the platform: the website tour and guide mode. Both take effect in every '
      + 'operating mode.',
    'curated.patterns.skillBruecke.label': 'Skill bridge',
    'curated.patterns.skillBruecke.hint':
      'Gives every pattern turn the approved skills of a collection.',
    'curated.betrieb.intro':
      'Which engine the server answers with when an embedding chooses none, and the switches '
      + 'for operating both modes.',
    'curated.betrieb.engine.label': 'Default engine and operating switches',
    'curated.betrieb.engine.hint':
      'Pattern or agent as default, plus fast mode, token streaming, quick replies and '
      + 'writing with the guest account.',
    'curated.betrieb.hinweis.streamingOhneSchnellantworten':
      'In agent mode, token streaming only works together with the agent quick replies — '
      + 'as it stands the answer still arrives in one piece. Switch on agent quick replies.',
    'agentUebersicht.intro':
      'The agent workspace: what the agent reads, what it may do and how it holds up in '
      + 'evaluation.',
    'agentUebersicht.zustand.agent': 'The server answers with the agent loop.',
    'agentUebersicht.zustand.pattern':
      'The server answers with the pattern engine; embeddings can choose the agent loop.',
    'agentUebersicht.zustand.unbekannt':
      'Which engine the server answers with cannot be read right now.',
    'agentUebersicht.betrieb': 'Change the default engine',
    'agentUebersicht.wege': 'More in the agent workspace',
    'agentUebersicht.wege.evaluation': 'Golden runs of the agent loop and their history',
    'agentUebersicht.lauf.titel': 'Latest run of the agent loop',
    'agentUebersicht.lauf.text': 'Run of {datum}: mean {score}',
    'agentUebersicht.lauf.leer': 'No finished run of the agent loop yet.',
    'agentUebersicht.lauf.laedt': 'Loading runs …',
    'agentUebersicht.lauf.link': 'Go to evaluation',
    'anrede.caption': 'Form of address per audience',
    'anrede.col.zielgruppe': 'Audience',
    'anrede.col.anrede': 'Address',
    'anrede.feld': 'Address for {name}',
    'anrede.wert.siezen': 'formal (Sie)',
    'anrede.wert.duzen': 'informal (du)',
    'anrede.wert.wie_user': 'as the person writes',
    'anrede.wert.neutral': 'no direct address',
    'anrede.wert.unbekannt': 'unknown: {wert}',
    'anrede.speichern': 'Save',
    'anrede.speichert': 'Saving …',
    'anrede.gespeichert': 'Saved',
    'anrede.laedt': 'Loading audiences …',
    'anrede.leer': 'No audiences yet — personas are in the patterns workspace under '
      + '“Dimensions”.',
    'anrede.rueckfall':
      'With “as the person writes”, the fallback in the section below applies until they have '
      + 'written.',
  },
};
