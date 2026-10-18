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
      'Die Regel-Tabelle, aus der die Schutzregeln stammen. Im Agent-Modus gelten nur die dort '
      + 'gewählten Regeln (Reiter „Rolle & Grenzen“ › Schutzregeln); alle anderen nur im '
      + 'Muster-Modus und bei Krisen-Zügen.',
    'curated.agentRolle.safety.label': 'Sicherheitsstufe',
    'curated.agentRolle.safety.hint':
      'Gate, Protokoll und Drosselung laufen vor jeder Maschine.',
    'curated.agentRolle.policy.label': 'Werkzeug-Regelwerk',
    'curated.agentRolle.policy.hint':
      'Welche Werkzeuge eine Regel sperrt. Im Agent-Modus greifen nur Regeln ohne Bedingung auf '
      + 'Persona oder Anliegen (oder mit P-AND bzw. I01) — der Agent erkennt beides nicht.',
    'curated.agentRolle.policy.hinweis.ohneWirkung':
      'Greifen im Agent-Modus nicht (Bedingung auf Persona oder Anliegen): {regeln}. '
      + 'Im Muster-Modus wirken sie weiter.',
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
      'Wirkt nur im Muster-Modus, und nur wenn eingeschaltet: gibt jedem Muster-Zug die '
      + 'freigegebenen Skills einer Sammlung mit. Die Agent-Schleife arbeitet mit dem Master-Skill.',
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
    'agentUebersicht.schichten': 'Der Weg einer Frage durch die Agent-Schleife',
    'agentUebersicht.schichten.hint':
      'Von oben nach unten: was eine Frage durchläuft, bevor die Antwort kommt — und auf '
      + 'welcher Seite sich jede Schicht einstellen lässt.',
    'agentUebersicht.schicht.sicherheit': 'Sicherheitsstufe',
    'agentUebersicht.schicht.sicherheit.desc':
      'prüft jede Nachricht vor der Schleife; bei Krise antwortet sie selbst',
    'agentUebersicht.schicht.rolle': 'Rolle und Grenzen',
    'agentUebersicht.schicht.rolle.desc':
      'der feste Kopf des Systemteils, dazu Runden, Zeit und Budget der Schleife',
    'agentUebersicht.schicht.skill': 'Master-Skill und Skills',
    'agentUebersicht.schicht.skill.desc':
      'das Vorgehen aus dem Repositorium, nachgeladene Skills je Aufgabe',
    'agentUebersicht.schicht.werkzeuge': 'Werkzeuge',
    'agentUebersicht.schicht.werkzeuge.desc':
      'Suche und Schreiben über den WLO-MCP, weitere Server nur lesend',
    'agentUebersicht.schicht.wissen': 'Wissen',
    'agentUebersicht.schicht.wissen.desc': 'Wissensbereiche, die die Agent-Schleife abfragen darf',
    'agentUebersicht.schicht.antwort': 'Antwort und Anzeige',
    'agentUebersicht.schicht.antwort.desc': 'Karten, Schnellantworten und wie das Widget sie zeigt',
    'agentUebersicht.testseiten': 'Testseiten',
    'agentUebersicht.testseiten.hint':
      'Das Widget so, wie Besucher es sehen — mit der Vorgabe-Maschine dieses Servers.',
    'agentUebersicht.neuerTab': '(neuer Tab)',
    'agentUebersicht.testseite.start': 'Übersicht der Einbettungen',
    'agentUebersicht.testseite.start.desc': 'alle Testseiten mit ihrem Einbett-Code',
    'agentUebersicht.testseite.inline': 'Eingebettet',
    'agentUebersicht.testseite.inline.desc': 'im Seitenkasten, geöffnet',
    'agentUebersicht.testseite.classic': 'Schwebender Knopf',
    'agentUebersicht.testseite.classic.desc': 'unten rechts, öffnet sich auf Klick',
    'agentUebersicht.testseite.frameless': 'Rahmenlos',
    'agentUebersicht.testseite.frameless.desc': 'füllt den Kasten der Seite, zugeklappt',
    'agentUebersicht.testseite.vorschau.desc': 'im Studio, mit wählbarem Seitenkontext',
    // Panel „Anrede je Zielgruppe“ (C2)
    'anrede.caption': 'Anrede je Zielgruppe',
    'anrede.rueckfallGilt': 'Rückfall gilt (Abschnitt darunter)',
    'anrede.col.zielgruppe': 'Zielgruppe',
    'anrede.col.anrede': 'Anrede',
    'anrede.col.aktion': 'Speichern',
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
      'The rule table the safeguard rules come from. In agent mode only the rules selected '
      + 'there apply (tab “Role & limits” › Safeguard rules); all others only in pattern mode '
      + 'and on crisis turns.',
    'curated.agentRolle.safety.label': 'Safety level',
    'curated.agentRolle.safety.hint':
      'Gate, log and throttling run before either engine.',
    'curated.agentRolle.policy.label': 'Tool policy',
    'curated.agentRolle.policy.hint':
      'Which tools a rule locks. In agent mode only rules without a persona or intent '
      + 'condition apply (or with P-AND or I01) — the agent detects neither.',
    'curated.agentRolle.policy.hinweis.ohneWirkung':
      'Do not apply in agent mode (condition on persona or intent): {regeln}. They '
      + 'still apply in pattern mode.',
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
      'Only in pattern mode, and only when switched on: gives every pattern turn the approved '
      + 'skills of a collection. The agent loop works with the master skill.',
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
    'agentUebersicht.schichten': 'How a question passes through the agent loop',
    'agentUebersicht.schichten.hint':
      'Top to bottom: what a question passes through before the answer arrives — and on which '
      + 'page each layer is set.',
    'agentUebersicht.schicht.sicherheit': 'Safety level',
    'agentUebersicht.schicht.sicherheit.desc':
      'checks every message before the loop; in a crisis it answers itself',
    'agentUebersicht.schicht.rolle': 'Role and limits',
    'agentUebersicht.schicht.rolle.desc':
      'the fixed head of the system part, plus rounds, time and budget of the loop',
    'agentUebersicht.schicht.skill': 'Master skill and skills',
    'agentUebersicht.schicht.skill.desc':
      'the procedure from the repository, skills loaded per task',
    'agentUebersicht.schicht.werkzeuge': 'Tools',
    'agentUebersicht.schicht.werkzeuge.desc':
      'search and writing via the WLO MCP, further servers read-only',
    'agentUebersicht.schicht.wissen': 'Knowledge',
    'agentUebersicht.schicht.wissen.desc': 'knowledge areas the agent loop may query',
    'agentUebersicht.schicht.antwort': 'Answer and display',
    'agentUebersicht.schicht.antwort.desc': 'cards, quick replies and how the widget shows them',
    'agentUebersicht.testseiten': 'Test pages',
    'agentUebersicht.testseiten.hint':
      'The widget as visitors see it — with this server’s default engine.',
    'agentUebersicht.neuerTab': '(new tab)',
    'agentUebersicht.testseite.start': 'Embedding overview',
    'agentUebersicht.testseite.start.desc': 'all test pages with their embed code',
    'agentUebersicht.testseite.inline': 'Embedded',
    'agentUebersicht.testseite.inline.desc': 'inside the page box, open',
    'agentUebersicht.testseite.classic': 'Floating button',
    'agentUebersicht.testseite.classic.desc': 'bottom right, opens on click',
    'agentUebersicht.testseite.frameless': 'Frameless',
    'agentUebersicht.testseite.frameless.desc': 'fills the page box, collapsed',
    'agentUebersicht.testseite.vorschau.desc': 'in the studio, with a selectable page context',
    'anrede.caption': 'Form of address per audience',
    'anrede.rueckfallGilt': 'Fallback applies (section below)',
    'anrede.col.zielgruppe': 'Audience',
    'anrede.col.anrede': 'Address',
    'anrede.col.aktion': 'Save',
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
