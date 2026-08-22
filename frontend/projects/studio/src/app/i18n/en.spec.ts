import { I18n } from '@boerdi/ui';
import { describe, expect, it } from 'vitest';

import { STUDIO_DE } from './de';
import { STUDIO_EN } from './en';

/**
 * Der englische Studio-Katalog (C1-d1) — dieselben Prüfungen wie beim Widget
 * (`ui/src/i18n/en.spec.ts`), aus demselben Grund: den Wortlaut kann ein Test
 * nicht beurteilen, das still Schiefgehende schon.
 *
 * Bewusst keine gemeinsame Prüf-Hilfsfunktion mit dem Widget-Katalog: die
 * Erlaubnislisten sind je Katalog verschieden, und eine geteilte Hilfe hiesse,
 * eine Prüfung an einer Stelle zu lockern und sie an beiden zu verlieren.
 */
describe('STUDIO_EN', () => {
  it('hat genau die Schlüssel des deutschen Katalogs', () => {
    expect(Object.keys(STUDIO_EN).sort()).toEqual(Object.keys(STUDIO_DE).sort());
  });

  it('jeder Text trägt dieselben Platzhalter wie sein deutsches Gegenstück', () => {
    const platzhalter = (s: string) => (s.match(/\{(\w+)\}/g) ?? []).sort();
    for (const key of Object.keys(STUDIO_DE)) {
      expect(platzhalter(STUDIO_EN[key]), `Platzhalter weichen ab: ${key}`)
        .toEqual(platzhalter(STUDIO_DE[key]));
    }
  });

  it('kein Text ist unübersetzt aus dem Deutschen stehengeblieben', () => {
    for (const [key, text] of Object.entries(STUDIO_EN)) {
      expect(text, `deutscher Rest in ${key}: ${text}`).not.toMatch(/[äöüÄÖÜß]/);
    }
  });

  it('kein Text ist eine wörtliche Kopie des deutschen — ausser den benannten', () => {
    const gleichErlaubt = new Set([
      'studio.title',           // Produktname
      'studio.nav.label',       // „Navigation" ist in beiden Sprachen dasselbe Wort
      'studio.status.offline',  // „Offline" ebenso — im Deutschen ein Lehnwort
      'login.passwordEnv',      // Name der Umgebungsvariablen, kein Satz
      'areas.importCmd',        // ein Shell-Befehl, ebenso wenig ein Satz
      'snapshots.title',        // „Snapshots" ist im deutschen Studio das Fachwort
      // Vier Ansichts-/Gruppennamen, die im deutschen Studio bereits das
      // englische Fachwort tragen — eine „Übersetzung" wäre hier eine Erfindung.
      'view.patterns.label',
      'view.sessions.label',
      'view.evaluation.label',
      'nav.group.system',
      // Zwei Wörter, die auf Deutsch und Englisch gleich geschrieben werden:
      // „Name" und „Text". Eine Abweichung wäre hier eine Erfindung.
      'mcp.field.name',
      'rag.ingest.source.text',
      // Zwei Fachwörter, die das deutsche Studio ohnehin englisch führt —
      // dieselbe Lage wie `view.patterns.label`.
      'curated.dimensionen.personas.label',
      'curated.dimensionen.intents.label',
      // Fünf aus der Startseite (C1-d4a). „Status", „Backend" und „Guardrails"
      // schreiben sich in beiden Sprachen gleich; „Score" und „Always-on RAG"
      // führt das deutsche Studio ohnehin englisch.
      'overview.status.title',
      'overview.backend',
      'overview.eval.score',
      'overview.layer.identitaet.tag.guardrails',
      'overview.layer.wissen.tag.alwaysOn',
      // Drei aus der Evaluation (C1-d4b). „Evaluation", „Trends" und „Status"
      // schreiben sich in beiden Sprachen gleich.
      'eval.label',
      'eval.tab.trends',
      'evalRuns.filter.label',
      // Fünf aus dem Lauf-Detail (C1-d4b2). „Status", „Config", „Persona",
      // „Intent" und „Judge" schreiben sich in beiden Sprachen gleich — die
      // letzten drei führt das deutsche Studio ohnehin englisch.
      'evalDetail.fact.status',
      'evalDetail.fact.config',
      'evalDetail.cat.persona',
      'evalDetail.cat.intent',
      'evalDetail.judge',
      // Fünf aus der Pattern-Nutzung (C1-d4b3). Vier Spaltenköpfe und die
      // voreingestellte Einheit der Balken-Tabelle: „Pattern", „Intent",
      // „Persona" und „Turns" führt das deutsche Studio durchgehend englisch
      // — dieselbe Lage wie bei `evalDetail.cat.persona`.
      'evalPattern.col.pattern',
      'evalPattern.col.intent',
      'evalPattern.col.persona',
      'evalPattern.col.turns',
      'bars.unit',
      // Fünf aus Trends und den Start-Panels (C1-d4c). „Turns", „Pattern",
      // „Flows", „Personas" und „Intents" führt das deutsche Studio
      // durchgehend englisch — dieselbe Lage wie bei
      // `curated.dimensionen.personas.label`.
      'evalTrends.col.turns',
      'evalTrends.patterns.col.pattern',
      'evalStart.gold.legend',
      'evalStart.gen.personas',
      'evalStart.gen.intents',
      // Fünf aus der Analyse (C1-d4d1). Vier Lehnwörter, die das deutsche
      // Studio ohnehin englisch führt — und `qual.diag.counts`, das gar kein
      // Wort enthält: es setzt zwei fertige Wortgruppen zusammen und legt damit
      // nur Trenner und Reihenfolge fest.
      'qual.tab.logs',
      'qual.diag.pattern',
      'qual.diag.persona',
      'qual.diag.confidence',
      'qual.diag.counts',
      // Zwölf aus Matrix, Fluss und Logs (C1-d4d2). Zwei enthalten gar kein
      // Wort (`qualMatrix.cell`, `qualDetail.head`) und legen nur Trenner und
      // Reihenfolge fest; die übrigen zehn sind Lehnwörter, die das deutsche
      // Studio ohnehin englisch führt — „Phase" schreibt sich in beiden
      // Sprachen gleich.
      'qualMatrix.cell',
      'qualDetail.head',
      'qualDetail.persona',
      'qualDetail.intent',
      'qualDetail.state',
      'qualDetail.session',
      'qualLogs.confidence',
      'qualLogs.degradation',
      'qualLogs.label',
      'qualLogs.filter.pattern',
      'qualLogs.filter.intent',
      'qualLogs.filter.session',
      // Acht aus dem Lasttest (C1-d4e1). `ltRun.totals` enthält gar kein Wort
      // — es setzt zwei fertige Wortgruppen zusammen. Die übrigen sieben sind
      // die Kopfzeile der Stufen-Tabelle samt Legende: „p50", „p95", „max",
      // „RPS" und „OK" sind Fachkürzel, „parallel" schreibt sich in beiden
      // Sprachen gleich, und „Requests" führt das deutsche Studio ohnehin
      // englisch.
      'ltRun.totals',
      'ltRun.p50',
      'ltRun.p95',
      'ltRun.col.concurrency',
      'ltRun.col.requests',
      'ltRun.col.ok',
      'ltRun.col.max',
      'ltRun.col.rps',
      // Drei aus den Sessions (C1-d4e2). „BOERDi" ist der Produktname; „Intent"
      // und „Persona" führt das deutsche Studio ohnehin englisch — dieselbe
      // Lage wie bei `evalDetail.cat.persona`.
      'st.role.assistant',
      'st.fact.intent',
      'st.fact.persona',
      // Drei aus den Safety-Logs (C1-d4e3). „Rate-limited" ist der Fachbegriff,
      // den auch das deutsche Studio führt (zweimal: als Kennzahl und als
      // Marker der Zeile); `sd.session` ist „Session: {id}" — dasselbe Wort und
      // derselbe Platzhalter in beiden Sprachen.
      'sfl.kpi.rateLimited',
      'sfl.marker.rateLimited',
      'sd.session',
      // Einer aus der Architektur-Referenz (C1-d5a1): „Element" ist in beiden
      // Sprachen dasselbe Wort. Die übrigen acht Spaltenköpfe derselben Reihe
      // unterscheiden sich, dieser nicht — auffällig genug, um ihn hier zu
      // nennen, statt ihn zu verbiegen.
      'arch.col.element',
      // Sieben aus den Zeilen derselben Referenz (C1-d5a2), in drei Gruppen:
      // vier Namen der Input-Dimensionen sind Lehnwörter, die auch das deutsche
      // Studio englisch führt (dieselbe Lage wie `st.fact.persona`); eine Zelle
      // zählt Enum-Werte auf statt sie zu beschreiben; und zwei Zellen der
      // Quellen-Spalte sind Bezeichner aus dem Code. Letztere stehen im Katalog
      // und nicht in den Daten, weil zwei ihrer vier Nachbarzellen Prosa sind —
      // eine Spalte, ein Weg.
      'arch.row.dim.persona.name',
      'arch.row.dim.intent.name',
      'arch.row.dim.entities.name',
      'arch.row.dim.state.name',
      'arch.row.dim.turnType.desc',
      'arch.row.sel.1.source',
      'arch.row.sel.2.source',
      // Drei weitere, vom Wächter selbst gefunden statt vorher geahnt:
      // „3. Fallback", „4. Modulation" und „3 — Patterns" bestehen aus Wörtern,
      // die das deutsche Studio unverändert englisch führt.
      'arch.row.sel.3.step',
      'arch.row.sel.4.step',
      'arch.row.layer.3.name',
      // Einer aus dem Wissens-Abschnitt (C1-d5b1): „Snapshots" ist die
      // Überschrift der Karte und in beiden Sprachen dasselbe Wort — das
      // deutsche Studio nennt sie überall so.
      'rk.snap.snapshots',
      // Zehn aus dem Widget-Vertrag (C1-d5b2), in vier Gruppen — alle vier sind
      // Sachen, die in einer HTML-Seite genauso stehen wie in dieser Tabelle:
      // Fachwörter der Weboberfläche („Event", „Payload", „Default"), zwei
      // Gruppennamen, die im Deutschen englisch heissen, zwei Zellen, die eine
      // Attribut-Schreibweise ZEIGEN statt sie zu beschreiben, und zwei
      // Beschreibungen, die nur die erlaubten Werte aufzählen.
      'rw.col.default',
      'rw.col.event',
      'rw.col.payload',
      'rw.eventsTitle',
      'rw.group.session',
      'rw.group.integration',
      'rw.when.guideSuggestion',
      'rw.when.routingDebug',
      'rw.attr.position',
      'rw.attr.initialState',
      // Zehn aus dem Fluss-Abschnitt (C1-d5c1): fünf Karten-Überschriften und
      // fünf Namen von Turn-Abschnitten. Es sind die Namen der Bauteile selbst
      // — `Persona`, `Intent`, `Entities`, `State`, `Pattern`, `Safety`,
      // `Policy`, `Modulation`, `Prompt`, `LLM + MCP` —, und die trägt das
      // deutsche Studio genauso. Übersetzt wird davon nur „Signale" → „Signals"
      // und „Klassifikation" / „Pattern-Wahl" / „Antwort".
      'rf.inf.persona.title',
      'rf.inf.intent.title',
      'rf.inf.entities.title',
      'rf.inf.state.title',
      'rf.inf.pattern.title',
      'rf.step.safety.stage',
      'rf.step.policy.stage',
      'rf.step.modulation.stage',
      'rf.step.prompt.stage',
      'rf.step.llm.stage',
      // Zwei aus den Referenz-Katalogen (C1-d5c2): `rc.mat.caption` enthält gar
      // kein Wort — es setzt zwei fertige Wortgruppen zusammen, wie
      // `ltRun.totals`; „ID" ist in beiden Sprachen dieselbe Abkürzung.
      'rc.mat.caption',
      'rc.mat.col.id',
      // GV5: „Engine" ist in beiden Sprachen dasselbe Fachwort, der Rest der
      // Zeile ist ein Platzhalter.
      'evalDetail.engine',
    ]);
    const kopien = Object.keys(STUDIO_DE)
      .filter((k) => !gleichErlaubt.has(k) && STUDIO_EN[k] === STUDIO_DE[k]);
    expect(kopien, 'unübersetzt aus DE kopiert').toEqual([]);
  });

  it('beide `format.htmlLang` sind gültige Sprachkürzel', () => {
    // Das Studio schreibt diesen Wert nach `<html lang>` — ein Tippfehler wäre
    // für einen Screenreader die falsche Aussprache, sichtbar für niemanden.
    expect(STUDIO_DE['format.htmlLang']).toBe('de');
    expect(STUDIO_EN['format.htmlLang']).toBe('en');
  });

  it('beide `format.locale` sind Kürzel, die `Intl` wirklich kennt', () => {
    // Ein Tippfehler wäre hier keine Ausnahme, sondern eine stille Rückkehr zur
    // Standardsprache der Laufzeit — Datum und Zahlen sähen dann irgendwie aus.
    for (const [sprache, katalog] of [['de', STUDIO_DE], ['en', STUDIO_EN]] as const) {
      const tag = katalog['format.locale'];
      expect(Intl.NumberFormat.supportedLocalesOf([tag]), `${sprache}: ${tag}`).toEqual([tag]);
      expect(tag.startsWith(katalog['format.htmlLang'])).toBe(true);
    }
  });

  it('als aktiver Katalog braucht er den deutschen Rückfall nirgends', () => {
    // Über `I18n` und nicht über `createTranslator`: so läuft die Prüfung durch
    // genau den Weg, den das Studio im Betrieb nimmt — und der Kern braucht
    // seinen Übersetzer-Bauer nicht öffentlich zu machen.
    const i18n = new I18n(STUDIO_DE, { en: STUDIO_EN });
    i18n.setLocale('en');
    for (const key of Object.keys(STUDIO_DE)) {
      expect(i18n.t(key), `${key} fiel auf Deutsch zurück`).toBe(STUDIO_EN[key]);
    }
  });
});
