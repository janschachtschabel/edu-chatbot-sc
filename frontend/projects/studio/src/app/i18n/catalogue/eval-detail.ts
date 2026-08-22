/**
 * Das Lauf-Detail samt Gold-Scorecard (C1-d4b2).
 *
 * Eigener Teil und nicht in `evaluation.ts`: die Evaluation hat fünf Ansichten,
 * und `evaluation.ts` trüge mit diesen Texten schon 240 Zeilen — mit C1-d4c
 * (Trends, Gold-Start, Generativ-Start) wären es über 400. Der Schnitt läuft
 * hier entlang der Ansicht, nicht entlang einer Zeilenzahl.
 *
 * **Fünf Sätze tragen Auszeichnung MITTEN im Satz** (`*so*` hebt hervor,
 * `` `so` `` ist Code). Sie stehen deshalb als GANZER Satz da und werden erst
 * beim Rendern geteilt — `splitRich` in `@boerdi/ui`, gerendert von
 * `<studio-rich>`. Je Bruchstück ein Eintrag wäre der Fehler, den C1-d3a beim
 * Zustands-Streifen abgestellt hat.
 *
 * NICHT hier: die drei Status-Wörter. Sie stehen seit C1-d4b1 in
 * `evaluation.ts` (`evalRuns.status.*`) und werden von beiden Ansichten über
 * `views/eval-status.ts` gelesen — die Liste und das Detail hatten bis C1-d4b2
 * je eine eigene Kopie derselben vier Zeilen.
 *
 * Entwurf: `docs/plans/2026-08-02-c1-i18n.md`.
 */
import type { CataloguePart } from './catalogue-part';

export const EVAL_DETAIL: CataloguePart = {
  de: {
    // ── Kopf ────────────────────────────────────────────────────────
    'evalDetail.title': 'Lauf {id}',
    'evalDetail.close': 'Schließen',
    /** Blosses Substantiv für den Zustands-Streifen — der Satz drumherum
     *  kommt aus `shared.ts`. */
    'evalDetail.state': 'Lauf',

    // ── Kennzahlen-Liste ────────────────────────────────────────────
    'evalDetail.fact.status': 'Status',
    'evalDetail.fact.mode': 'Art',
    'evalDetail.fact.started': 'Gestartet',
    'evalDetail.fact.finished': 'Beendet',
    'evalDetail.fact.turns': 'Bewertete Turns',
    'evalDetail.fact.score': 'Ø Score',
    'evalDetail.fact.config': 'Config',
    'evalDetail.fact.judgeModel': 'Judge-Modell',
    'evalDetail.fact.simulatorModel': 'Simulator-Modell',

    'evalDetail.mode.golden': 'Gold-Flows',
    'evalDetail.mode.generative': 'Generativ',

    // ── Laufender Lauf und Fehler ───────────────────────────────────
    'evalDetail.live': '*Momentaufnahme* — der Lauf läuft noch.',
    'evalDetail.liveWhy':
      'Die Lauf-Liste oben aktualisiert sich selbst; hier bewusst nicht, weil '
      + 'diese Antwort die vollständigen Transkripte mitbringt.',
    /** `{message}` ist der Wortlaut des Backends. Er wird eingesetzt, NACHDEM
     *  der Satz geteilt wurde — ein Stern darin kann keine Auszeichnung
     *  erzeugen. */
    'evalDetail.error': '*Fehler:* {message}',

    // ── Trefferquoten ───────────────────────────────────────────────
    'evalDetail.rates.title': 'Trefferquoten',
    'evalDetail.rates.summary':
      '{flows} Flows · {turns} Turns · harte Quote *{rate}* ({ok}/{total} Checks)',
    'evalDetail.rates.judge':
      'Judge-Schnitt *{score}* über {turns} Turns — separate Größe, sie fließt '
      + 'nicht in die harte Quote ein.',
    'evalDetail.rates.hostHint':
      '„Link-Host" ist ein weicher Check: eine falsch gesetzte `REPO_BASE_URL` '
      + 'lässt ihn für jeden Turn scheitern, ohne etwas über den Bot zu sagen. '
      + 'Er steht deshalb neben der harten Quote, nicht darin.',

    // ── Turn-Tabelle ────────────────────────────────────────────────
    'evalDetail.table.caption':
      'Turns je Flow, jede Gruppe mit ihrer eigenen harten Quote. Eine Zeile '
      + 'öffnen zeigt die Bot-Antwort und was gemessen wurde.',
    'evalDetail.col.turn': 'Flow · Turn',
    // v1-Läufe füllen die Kompaktspalten mit Persona/Intent, v2 mit
    // Tonalität/Struktur — die Beschriftung bleibt deshalb generisch.
    'evalDetail.col.expected': 'Soll',
    'evalDetail.col.observed': 'Ist / Muster',
    'evalDetail.col.message': 'Nachricht',
    /** Ein Satz, nicht sechs Bruchstücke. „Sie" und „du" bleiben auch auf
     *  Englisch stehen: gezählt werden die deutschen Anredeformen, die der
     *  Tonalitäts-Check prüft. */
    'evalDetail.turnDetail':
      '*Soll-Angebot:* {mustOffer} · Sie {sie} · du {du} · Karten {cards} '
      + '· Inline-Dokumente {idocs} · Quick-Replies {qr}',
    'evalDetail.flowTotal': '{flow} Gesamt',
    'evalDetail.flowRate': '{rate} · {ok}/{total} Checks',
    /** Kein „0 %": nichts geprüft heisst nicht alles gescheitert. */
    'evalDetail.flowNothing': 'nichts geprüft',
    'evalDetail.check.passed': 'bestanden',
    'evalDetail.check.failed': 'nicht bestanden',
    'evalDetail.check.skipped': 'nicht geprüft',

    // ── Kategorien der Scorecard ────────────────────────────────────
    // persona/intent nur noch für GESPEICHERTE v1-Läufe; v2 prüft sie nicht.
    'evalDetail.cat.persona': 'Persona',
    'evalDetail.cat.intent': 'Intent',
    'evalDetail.cat.register': 'Tonalität',
    'evalDetail.cat.structure': 'Struktur',
    'evalDetail.cat.tools_any': 'Werkzeug-Soll',
    'evalDetail.cat.qr': 'Quick-Replies',
    'evalDetail.cat.host': 'Link-Host',

    // ── GV4/GV5: Engine des Laufs + gezählte Judge-Ausfälle ─────────
    'evalDetail.engine': 'Engine: {engine}',
    'evalDetail.judgeFailed': 'Judge-Ausfälle: {count}',
    // Review-Befund 4: Züge, die der Chat nie beantwortet hat.
    'evalDetail.chatErrors': 'Chat-Fehler: {count} Züge ohne Antwort',

    // ── Transkript-Zweig ────────────────────────────────────────────
    'evalDetail.noMetrics':
      'Dieser Lauf trägt *keine Gold-Metriken* — die deterministische Scorecard '
      + 'entsteht nur bei Gold-Flows. Unten stehen die Transkripte, die der Lauf '
      + 'geschrieben hat.',
    'evalDetail.noTranscripts':
      'Auch keine Transkripte: der Lauf ist gestorben, bevor ein Turn fertig '
      + 'wurde.',
    // Feedback 2026-08-22: bei LAUFENDEM Lauf ist „gestorben" die falsche
    // Diagnose — Zwischenstände erscheinen je Flow, „Aktualisieren" holt sie.
    'evalDetail.noTranscriptsYet':
      'Noch keine Transkripte gespeichert — der Lauf schreibt seinen '
      + 'Zwischenstand je Flow; „Aktualisieren" holt ihn.',
    'evalDetail.conversation': 'Gespräch {num}',
    'evalDetail.speaker.user': 'Nutzer',
    'evalDetail.judge': 'Judge {score}',
    'evalDetail.noBotText': '(kein Antworttext gespeichert)',
  },

  en: {
    'evalDetail.title': 'Run {id}',
    'evalDetail.close': 'Close',
    'evalDetail.state': 'Run',

    'evalDetail.fact.status': 'Status',
    'evalDetail.fact.mode': 'Type',
    'evalDetail.fact.started': 'Started',
    'evalDetail.fact.finished': 'Finished',
    'evalDetail.fact.turns': 'Scored turns',
    'evalDetail.fact.score': 'Avg score',
    'evalDetail.fact.config': 'Config',
    'evalDetail.fact.judgeModel': 'Judge model',
    'evalDetail.fact.simulatorModel': 'Simulator model',

    'evalDetail.mode.golden': 'Gold flows',
    'evalDetail.mode.generative': 'Generative',

    'evalDetail.live': '*Snapshot* — the run is still going.',
    'evalDetail.liveWhy':
      'The run list above refreshes itself; this panel deliberately does not, '
      + 'because its answer carries the full transcripts.',
    'evalDetail.error': '*Error:* {message}',

    'evalDetail.rates.title': 'Hit rates',
    'evalDetail.rates.summary':
      '{flows} flows · {turns} turns · hard rate *{rate}* ({ok}/{total} checks)',
    'evalDetail.rates.judge':
      'Judge average *{score}* over {turns} turns — a separate figure, it does '
      + 'not feed the hard rate.',
    'evalDetail.rates.hostHint':
      '“Link host” is a soft check: a wrongly set `REPO_BASE_URL` fails it for '
      + 'every turn without saying anything about the bot. That is why it sits '
      + 'beside the hard rate, not inside it.',

    'evalDetail.table.caption':
      'Turns per flow, each group with its own hard rate. Opening a row shows '
      + 'the bot answer and what was measured.',
    'evalDetail.col.turn': 'Flow · turn',
    'evalDetail.col.expected': 'Expected',
    'evalDetail.col.observed': 'Actual / pattern',
    'evalDetail.col.message': 'Message',
    'evalDetail.turnDetail':
      '*Expected offer:* {mustOffer} · Sie {sie} · du {du} · cards {cards} '
      + '· inline documents {idocs} · quick replies {qr}',
    'evalDetail.flowTotal': '{flow} total',
    'evalDetail.flowRate': '{rate} · {ok}/{total} checks',
    'evalDetail.flowNothing': 'nothing checked',
    'evalDetail.check.passed': 'passed',
    'evalDetail.check.failed': 'not passed',
    'evalDetail.check.skipped': 'not checked',

    'evalDetail.cat.persona': 'Persona',
    'evalDetail.cat.intent': 'Intent',
    'evalDetail.cat.register': 'Register',
    'evalDetail.cat.structure': 'Structure',
    'evalDetail.cat.tools_any': 'Required tool',
    'evalDetail.cat.qr': 'Quick replies',
    'evalDetail.cat.host': 'Link host',

    'evalDetail.engine': 'Engine: {engine}',
    'evalDetail.judgeFailed': 'Judge failures: {count}',
    'evalDetail.chatErrors': 'Chat errors: {count} unanswered turns',

    'evalDetail.noMetrics':
      'This run carries *no gold metrics* — the deterministic scorecard only '
      + 'comes out of gold flows. Below are the transcripts the run wrote.',
    'evalDetail.noTranscripts':
      'No transcripts either: the run died before a single turn finished.',
    'evalDetail.noTranscriptsYet':
      'No transcripts stored yet — the run persists its progress per flow; '
      + '"Refresh" fetches it.',
    'evalDetail.conversation': 'Conversation {num}',
    'evalDetail.speaker.user': 'User',
    'evalDetail.judge': 'Judge {score}',
    'evalDetail.noBotText': '(no answer text stored)',
  },
};
