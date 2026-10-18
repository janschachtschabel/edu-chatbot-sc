/**
 * Die Kostenschau (K5) — Zeitraum, Summenband, Betrag, zwei Tabellen.
 *
 * **Zwei Beschriftungen tragen Fachwissen, nicht nur einen Namen.** OpenAI
 * zählt `cached_tokens` INNERHALB von `prompt_tokens` und `reasoning_tokens`
 * INNERHALB von `completion_tokens`. Wer sie addiert, zahlt doppelt — deshalb
 * heissen die beiden Spalten „davon Cache" und „davon Reasoning" und nicht
 * bloss „Cache" und „Reasoning". Dieselbe Falle benennt der Plan als die
 * häufigste; sie am Bildschirm zu entschärfen kostet zwei Wörter.
 *
 * **`costs.amount.partial` ist Pflicht, keine Zierde.** Der Betrag deckt nur
 * die bepreisten Modelle. Stünde er allein, läse sich eine Teilsumme als
 * Gesamtsumme — und zwar umso überzeugender, je gepflegter die Tafel wirkt.
 *
 * Was NICHT hier steht: „Aktualisieren"/„Wird geladen …" (`action.refresh*` in
 * `shared.ts`), der Zustands-Streifen (`async.*` ebenda) und der Name der
 * Ansicht selbst (`view.kosten.label` in `views.ts`, wo ihn auch die
 * Navigation liest).
 */
import type { CataloguePart } from './catalogue-part';

export const COSTS: CataloguePart = {
  de: {
    'costs.intro':
      'Was der Bot in einem Zeitraum verbraucht hat: Token getrennt nach Eingabe, '
      + 'Cache, Ausgabe und Reasoning, dazu der Betrag nach der gepflegten '
      + 'Preistafel. Gezeigt wird die Maschine des Arbeitsbereichs; Züge ohne Maschine '
      + '(Vorprüfung, Direkt-Aktionen wie „Lernpfad erzeugen“) stehen in beiden.',

    // ── Zeitraum ────────────────────────────────────────────────────
    'costs.period.legend': 'Zeitraum',
    'costs.from.label': 'Von',
    'costs.to.label': 'Bis',
    /** Beide Grenzen zählen mit — ohne den Satz läse man „bis 11.08." als
     *  „bis zum Beginn des 11.08." und wunderte sich über den fehlenden Tag. */
    'costs.period.hint': 'Beide Tage zählen vollständig mit.',

    // ── Betrag ──────────────────────────────────────────────────────
    'costs.amount.label': 'Betrag',
    'costs.amount.none': 'Für kein Modell ist ein Preis gepflegt.',
    /** Anderer Grund als `none`, gleiche Folge. Ohne den Unterschied pflegt
     *  die Redaktion nach einem Tippfehler nach und wundert sich. */
    'costs.amount.broken': 'Die Preistafel ist nicht lesbar und wird ignoriert.',
    'costs.amount.partial': 'Teilsumme — ohne {models}',
    'costs.amount.where':
      'Preise pflegst du weiter unten in der *Preistafel*, je Million Token.',

    // ── Summenband ──────────────────────────────────────────────────
    'costs.band.prompt': 'Eingabe',
    'costs.band.cached': 'davon Cache',
    'costs.band.completion': 'Ausgabe',
    'costs.band.reasoning': 'davon Reasoning',
    'costs.band.calls': 'LLM-Aufrufe',

    // ── Tabellen ────────────────────────────────────────────────────
    'costs.models.caption': 'Je Modell',
    'costs.sessions.caption': 'Teuerste Sitzungen des Zeitraums',
    /** Paket 7 (P3): Aufträge der Agent-API buchen ohne Sitzung. */
    'costs.sessions.agentApi': 'Agent-API (Aufträge ohne Sitzung)',
    /** Paket 9: die Probeläufe des Auftragstesters zählen nicht als Betrieb. */
    'costs.sessions.studioProbe': 'Studio: „Auftrag testen“ (Probeläufe ohne Sitzung)',
    'costs.sessions.evalJudge': 'Evaluation: Judge (ohne Sitzung)',
    'costs.sessions.evalSimulator': 'Evaluation: Simulator (ohne Sitzung)',
    'costs.sessions.evalSzenario': 'Evaluation: Szenarien (ohne Sitzung)',
    /** Ohne gepflegte Preise ordnet die Liste nach Token — sonst wäre sie
     *  beim ersten Blick auf eine frische Anlage unsortiert. */
    'costs.sessions.hint':
      'Ohne gepflegte Preise nach Token geordnet, nicht nach Betrag.',
    'costs.col.model': 'Modell',
    'costs.col.session': 'Sitzung',
    'costs.col.calls': 'Aufrufe',
    'costs.col.prompt': 'Eingabe',
    'costs.col.cached': 'davon Cache',
    'costs.col.completion': 'Ausgabe',
    'costs.col.reasoning': 'davon Reasoning',
    'costs.col.amount': 'Betrag',
    /** Eine Zelle ohne Preis. Ein leeres Feld läse sich als Anzeigefehler. */
    'costs.noPrice': 'kein Preis',
    // Paket 16, D3: Nutzung
    'nutzung.intro':
      'Wie oft und wann mit dem Chatbot gesprochen wird — aus dem Qualitäts-Protokoll, eine '
      + 'Zeile je Zug, beide Maschinen zusammen. Ohne Eval- und Lasttest-Züge, wenn „Betrieb“ '
      + 'gewählt ist.',
    'nutzung.aus':
      'Das Qualitäts-Protokoll schreibt gerade nicht — neue Züge fehlen hier.',
    'nutzung.ausLink': 'Einschalten unter „Datenschutz“',
    'nutzung.leer': 'In diesem Zeitraum gibt es keine protokollierten Züge.',
    'nutzung.zuege': 'Züge',
    'nutzung.sitzungen': 'Sitzungen',
    'nutzung.mittel': 'Züge je Sitzung (Mittel)',
    'nutzung.median': 'Züge je Sitzung (Median)',
    'nutzung.klein': '<{n}',
    'nutzung.stunde': '{h} Uhr',
    'nutzung.ohneAngabe': '(ohne Angabe)',
    'nutzung.keine': 'keine',
    'nutzung.raster.title': 'Wochentag × Stunde',
    'nutzung.raster.hint':
      'Züge je Stunde in deutscher Zeit; je dunkler, desto mehr, leer heißt keine. „<5“: Züge '
      + 'aus weniger als fünf Sitzungen — Raster und Verteilungen runden kleine Zellen ab; '
      + 'Summen und Tageswerte bleiben genau.',
    'nutzung.tage.title': 'Je Tag',
    'nutzung.verteilungen.title': 'Verteilungen (Züge)',
    'nutzung.nurMuster': 'nur Muster-Züge — die Agent-Schleife setzt sie fest',
    'nutzung.facette.maschine': 'Maschine',
    'nutzung.facette.sprache': 'Sprache',
    'nutzung.facette.geraet': 'Gerät',
    'nutzung.facette.seitenart': 'Seitenart',
    'nutzung.facette.persona': 'Zielgruppe',
    'nutzung.facette.anliegen': 'Anliegen',
    'nutzung.wochentag.0': 'Mo',
    'nutzung.wochentag.1': 'Di',
    'nutzung.wochentag.2': 'Mi',
    'nutzung.wochentag.3': 'Do',
    'nutzung.wochentag.4': 'Fr',
    'nutzung.wochentag.5': 'Sa',
    'nutzung.wochentag.6': 'So',
    // Paket 16, D2: Kosten je Tag
    'costDays.title': 'Kosten je Tag',
    'costDays.hint':
      'Je Kalendertag (deutsche Zeit) eine Säule; die höchste steht für {max}. Gestrichelte '
      + 'Marke: Tage mit Zügen, aber ganz ohne gepflegten Preis; fehlt nur für ein Modell der '
      + 'Preis, sagt es die Tabelle („unvollständig“).',
    'costDays.hintOhnePreis':
      'Im Zeitraum hat noch kein Tag mit gepflegtem Preis Kosten — die gestrichelten Marken '
      + 'zeigen Tage mit Zügen ohne Preis.',
    'costDays.table': 'Als Tabelle',
    'costDays.col.tag': 'Tag',
    'costDays.col.calls': 'Aufrufe',
    'costDays.col.amount': 'Betrag',
    'costDays.unvollstaendig': '{betrag} (unvollständig — ein Modell ohne Preis)',

    'costs.empty':
      'In diesem Zeitraum wurde kein Modell aufgerufen. Zahlen entstehen mit dem '
      + 'ersten Chat-Zug.',
  },

  en: {
    'costs.intro':
      'What the bot consumed in a period: tokens split into input, cache, output '
      + 'and reasoning, plus the amount from the maintained price table. Shows the engine of the '
      + 'workspace; turns without an engine (pre-check, direct actions such as “create learning '
      + 'path”) appear in both.',

    'costs.period.legend': 'Period',
    'costs.from.label': 'From',
    'costs.to.label': 'To',
    'costs.period.hint': 'Both days count in full.',

    'costs.amount.label': 'Amount',
    'costs.amount.none': 'No model has a maintained price.',
    'costs.amount.broken': 'The price table is unreadable and is being ignored.',
    'costs.amount.partial': 'Partial sum — without {models}',
    'costs.amount.where':
      'Prices are maintained further down in the *price table*, per million tokens.',

    'costs.band.prompt': 'Input',
    'costs.band.cached': 'of which cached',
    'costs.band.completion': 'Output',
    'costs.band.reasoning': 'of which reasoning',
    'costs.band.calls': 'LLM calls',

    'costs.models.caption': 'By model',
    'costs.sessions.caption': 'Most expensive sessions of the period',
    'costs.sessions.agentApi': 'Agent API (tasks without a session)',
    'costs.sessions.studioProbe': 'Studio: “Test a task” (trial runs without a session)',
    'costs.sessions.evalJudge': 'Evaluation: judge (without a session)',
    'costs.sessions.evalSimulator': 'Evaluation: simulator (without a session)',
    'costs.sessions.evalSzenario': 'Evaluation: scenarios (without a session)',
    'costs.sessions.hint':
      'Ordered by tokens rather than amount while no prices are maintained.',
    'costs.col.model': 'Model',
    'costs.col.session': 'Session',
    'costs.col.calls': 'Calls',
    'costs.col.prompt': 'Input',
    'costs.col.cached': 'of which cached',
    'costs.col.completion': 'Output',
    'costs.col.reasoning': 'of which reasoning',
    'costs.col.amount': 'Amount',
    'costs.noPrice': 'no price',
    'nutzung.intro':
      'How often and when people talk to the chatbot — from the quality log, one row per turn, '
      + 'both engines together. Without eval and load-test turns when “Production” is selected.',
    'nutzung.aus': 'The quality log is not recording right now — new turns are missing here.',
    'nutzung.ausLink': 'Switch it on under “Privacy”',
    'nutzung.leer': 'There are no logged turns in this period.',
    'nutzung.zuege': 'Turns',
    'nutzung.sitzungen': 'Sessions',
    'nutzung.mittel': 'Turns per session (mean)',
    'nutzung.median': 'Turns per session (median)',
    'nutzung.klein': '<{n}',
    'nutzung.stunde': '{h}:00',
    'nutzung.ohneAngabe': '(not given)',
    'nutzung.keine': 'none',
    'nutzung.raster.title': 'Weekday × hour',
    'nutzung.raster.hint':
      'Turns per hour in German time; the darker, the more, empty means none. “<5”: turns from '
      + 'fewer than five sessions — grid and distributions round small cells off; totals and '
      + 'daily figures stay exact.',
    'nutzung.tage.title': 'Per day',
    'nutzung.verteilungen.title': 'Distributions (turns)',
    'nutzung.nurMuster': 'pattern turns only — the agent loop fixes these',
    'nutzung.facette.maschine': 'Engine',
    'nutzung.facette.sprache': 'Language',
    'nutzung.facette.geraet': 'Device',
    'nutzung.facette.seitenart': 'Page type',
    'nutzung.facette.persona': 'Audience',
    'nutzung.facette.anliegen': 'Intent',
    'nutzung.wochentag.0': 'Mon',
    'nutzung.wochentag.1': 'Tue',
    'nutzung.wochentag.2': 'Wed',
    'nutzung.wochentag.3': 'Thu',
    'nutzung.wochentag.4': 'Fri',
    'nutzung.wochentag.5': 'Sat',
    'nutzung.wochentag.6': 'Sun',
    'costDays.title': 'Cost per day',
    'costDays.hint':
      'One bar per calendar day (German time); the tallest stands for {max}. Dashed mark: days '
      + 'with turns but no maintained price at all; if only one model lacks a price, the table '
      + 'says so (“incomplete”).',
    'costDays.hintOhnePreis':
      'No day in this period has costs with a maintained price yet — the dashed marks show '
      + 'days with turns but no price.',
    'costDays.table': 'As a table',
    'costDays.col.tag': 'Day',
    'costDays.col.calls': 'Calls',
    'costDays.col.amount': 'Amount',
    'costDays.unvollstaendig': '{betrag} (incomplete — a model without a price)',

    'costs.empty':
      'No model was called in this period. Numbers appear with the first chat turn.',
  },
};
