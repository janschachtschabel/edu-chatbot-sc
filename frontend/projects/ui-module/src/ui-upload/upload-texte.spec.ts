import { describe, expect, it } from 'vitest';

import manifest from './manifest.json';
import { groesse, texte } from './upload-texte';
import { uebertragenTexte } from './upload-uebertragen-texte';

/** Alle Texte eines Katalogs: Zeichenketten direkt, Funktionen über ihren Quelltext (Vorlagen). */
function alleTexte(wert: unknown): string[] {
  if (typeof wert === 'string') return [wert];
  if (typeof wert === 'function') return [String(wert)];
  if (wert && typeof wert === 'object') return Object.values(wert).flatMap(alleTexte);
  return [];
}

describe('Texte ui_upload (U3-1a)', () => {
  it('jede Warnung und jede Rolle gibt es auf Deutsch und Englisch, nicht gleich', () => {
    const de = texte('de');
    const en = texte('en');
    expect(Object.keys(en.warnung).sort()).toEqual(Object.keys(de.warnung).sort());
    for (const k of Object.keys(de.warnung) as (keyof typeof de.warnung)[]) {
      expect(de.warnung[k](3)).not.toBe(en.warnung[k](3));
    }
    expect(Object.keys(en.rolle).sort()).toEqual(Object.keys(de.rolle).sort());
  });

  it('Einzahl und Mehrzahl, Zahlen je Sprache formatiert', () => {
    expect(texte('de').dateien(1)).toBe('1 Datei');
    expect(texte('de').dateien(1234)).toBe('1.234 Dateien');
    expect(texte('en').dateien(1234)).toBe('1,234 files');
    expect(texte('en').ordner(1)).toBe('1 folder');
  });

  it('Größen in kB und MB mit einer Nachkommastelle', () => {
    expect(groesse('de', 1_500_000)).toBe('1,5 MB');
    expect(groesse('en', 1_500_000)).toBe('1.5 MB');
    expect(groesse('de', 12_300)).toBe('12 kB');
    expect(groesse('de', 10)).toBe('1 kB');
  });

  // Plan 2026-11-16, TG-1 (G-E4): das Upload-Feld stellt nur bereit — kein Knopf und kein Text nennt
  // ein Ziel wie den Themenbaum; was mit den Daten geschieht, klären Ablauf oder KI danach.
  it('TG-1: kein Text des Moduls nennt einen Themenbaum (de/en)', () => {
    for (const sprache of ['de', 'en'] as const) {
      const saetze = [...alleTexte(texte(sprache)), ...alleTexte(uebertragenTexte(sprache))];
      expect(saetze.length).toBeGreaterThan(50);
      expect(saetze.filter((s) => /themenbaum|topic.?tree/i.test(s))).toEqual([]);
    }
  });

  // Plan 2026-11-17, Paket U4: ein Weg. Plan 2026-11-20, P2 (§4 Wortlaut): Frage, Orte und ein Knopf je Ort —
  // „Hier lesen“ (Chat), „Weiter zur Vorschau“ (WLO, der Klick legt noch nichts ab)
  it('P2: Frage, Orte und Knöpfe nach §4 (de/en)', () => {
    const de = texte('de');
    const en = texte('en');
    expect([de.frage, de.ort.chat, de.ort.wlo, de.ortWloAblegen, de.hierLesen, de.zurVorschau, de.nurNamen]).toEqual([
      'Wo sollen die Dateien verarbeitet werden?', 'Nur hier im Chat lesen', 'In WLO ablegen und erschließen',
      'In WLO ablegen', 'Hier lesen', 'Weiter zur Vorschau', 'Nur die Dateinamen senden (der Inhalt bleibt auf deinem Gerät)']);
    expect([en.frage, en.ort.chat, en.ort.wlo, en.ortWloAblegen, en.hierLesen, en.zurVorschau, en.nurNamen]).toEqual([
      'Where should the files be processed?', 'Only read here in the chat', 'Store and index in WLO', 'Store in WLO',
      'Read here', 'Continue to preview', 'Send file names only (the content stays on your device)']);
    // zweites Review, 2: die Frist beginnt bei jeder Nutzung neu; Review der Oberfläche, 9: „ohne Anmeldung“
    // nur, wenn die Schalter es tragen; Paket C: „auch von Scans“ nur mit Texterkennung
    expect(de.erklaerChat(10, 24, true, true)).toBe('Nichts wird in WLO gespeichert, keine Anmeldung nötig. Der Chat '
      + 'liest den Text (auch von Scans) und vergisst ihn spätestens 24 Stunden nach der letzten Nutzung. Bis 10 Dateien.');
    expect(de.erklaerChat(1, 1, false, false)).toBe('Nichts wird in WLO gespeichert. Der Chat liest den Text und '
      + 'vergisst ihn spätestens 1 Stunde nach der letzten Nutzung. Bis 1 Datei.');
    expect(en.erklaerChat(10, 24, false, false)).toBe('Nothing is stored in WLO. The chat reads the text and forgets '
      + 'it at the latest 24 hours after last use. Up to 10 files.');
    expect(de.erklaerWlo(true)).toBe('Deine Dateien werden Inhalte in deinem persönlichen Bereich in WLO und bleiben dort. '
      + 'WLO liest den Text und erzeugt Titel, Beschreibung, Fach, Stufe und Schlagworte. Dauert ein paar Minuten.');
    expect(de.erklaerWlo(false)).toBe('Deine Dateien werden Inhalte in deinem persönlichen Bereich in WLO und bleiben dort.');
    // Review P2, Befund 3: der Grund in Klammern (Plan §4), ohne Code ohne Klammer
    expect(de.erklaerWloOhne(null)).toBe('Deine Dateien werden Inhalte in deinem persönlichen Bereich in WLO und bleiben dort. '
      + 'Metadaten kann WLO gerade nicht erzeugen.');
    expect(de.erklaerWloOhne(de.ohneFlow.flow_nicht_freigegeben)).toContain('erzeugen (in diesem Chat nicht freigegeben).');
    expect(en.erklaerWloOhne(en.ohneFlow.dienst_nicht_erreichbar))
      .toContain('WLO cannot create metadata right now (the service for it cannot be reached right now).');
    expect(Object.keys(en.ohneFlow)).toEqual(Object.keys(de.ohneFlow));
    expect([de.haken, de.hakenHinweis]).toEqual(['Metadaten von WLO erzeugen lassen',
      'WLO setzt dabei Titel, Beschreibung, Fach, Stufe und Schlagworte neu – der Dateiname bleibt nicht der Titel.']);
    // Review P2, Befund 3: der Weg zur Anmeldung ist der Konto-Knopf in der Eingabezeile
    expect(de.nichtWaehlbar(de.gesperrt.nur_angemeldet)).toBe('nicht wählbar – melde dich über den Konto-Knopf unten an');
    expect(en.nichtWaehlbar(en.gesperrt.nur_angemeldet)).toBe('not available – sign in with the account button below');
    // Review P2, Befund 4: „ignorieren“ heißt in der Oberfläche „Nicht verwenden“
    expect(de.zuVieleStapel(200)).toBe('höchstens 200 Dateien auf einmal – bitte einige auf „Nicht verwenden“ stellen');
    expect(en.zuVieleStapel(200)).toBe("at most 200 files at once – please set some to “Don't use”");
    expect(de.mitAnmeldung(de.zuVieleHier(10))).toBe('zu viele Dateien für hier (höchstens 10) – mit Anmeldung über WLO');
    // Review TG-1, m4: der Name von „Weiter“ trägt die Beschriftung und sagt, was gesendet wird
    expect(de.weiterNachLesenName.startsWith(de.weiterNachLesen)).toBe(true);
    expect(en.weiterNachLesenName.startsWith(en.weiterNachLesen)).toBe(true);
  });

  // Review P1, NIT 7: die Sammelknöpfe heißen wie die Option „Nicht verwenden“
  it('P1-Review: „Nicht verwenden“ auch an den Sammelknöpfen (de/en)', () => {
    const de = texte('de');
    const en = texte('en');
    expect([de.alleIgnorieren, de.wiederEinschliessen, de.alleIgnorierenIn('A'), de.wiederEinschliessenIn('A')])
      .toEqual(['Alle nicht verwenden', 'Wieder verwenden', 'Alle Dateien in A nicht verwenden', 'Dateien in A wieder verwenden']);
    expect([en.alleIgnorieren, en.wiederEinschliessen, en.alleIgnorierenIn('A'), en.wiederEinschliessenIn('A')])
      .toEqual(["Don't use any", 'Use again', "Don't use any files in A", 'Use files in A again']);
  });

  it('U4: jeder Fehlercode „Hier im Chat“ auf Deutsch und Englisch, die Grenzen der Sitzung dabei', () => {
    expect(Object.keys(texte('en').chatFehler).sort()).toEqual(Object.keys(texte('de').chatFehler).sort());
    expect(Object.keys(texte('de').chatFehler)).toEqual(expect.arrayContaining(['grenze_anzahl', 'grenze_gesamt']));
  });

  it('Review der Oberfläche, 1: die Sätze an der Grenze nennen keinen Weg, den es dort nicht gibt', () => {
    for (const t of [texte('de'), texte('en')]) {
      // kein Satz schickt mehr nach WLO; „nur mit Namen“ hängt die Ansicht nur an, wo es den Knopf gibt
      expect(t.chatFehler.grenze_anzahl).not.toMatch(/WLO|Namen|names/);
      expect(t.chatFehler.grenze_gesamt).not.toMatch(/WLO|Namen|names/);
    }
    expect(texte('de').chatFehler.grenze_gesamt).toContain('Mach ohne diese weiter');
  });

  it('zweites Review, 2 und 5: Frist nach der letzten Nutzung, Entwurf im Arbeitsstand, Ausweg bei voller Sitzung', () => {
    const de = texte('de');
    const en = texte('en');
    for (const satz of [de.datenschutzChat(24), de.bleibenHier(24)]) {
      expect(satz).toContain('24 Stunden nach der letzten Nutzung');
      expect(satz).toContain('ein daraus erstellter Entwurf bleibt im Arbeitsstand');
    }
    for (const satz of [en.datenschutzChat(24), en.bleibenHier(24)]) {
      expect(satz).toContain('24 hours after last use');
      expect(satz).toContain('a draft made from them stays in your work in progress');
    }
    expect(de.sitzungVoll(24, true)).toBe('hier im Chat ist für dieses Gespräch kein Platz mehr – wieder frei nach 24 Stunden '
      + 'ohne Nutzung oder mit „Arbeitsstand löschen“ – oder in WLO ablegen');
    expect(en.sitzungVoll(1, false)).toBe('no room left here in the chat for this conversation – free again after 1 hour '
      + 'without use or with “Delete work in progress”');
    expect(de.dateiVon(2, 3)).toBe('Datei 2 von 3');
    expect(en.dateiVon(2, 3)).toBe('File 2 of 3');
  });

  // Plan 2026-11-16, TG-3a (G-E1): seit dem Teil `struktur` gehen auch die Dateinamen an den Chat.
  // Paket U4: der Satz richtet sich nach dem Ort und sagt, was wohin geht und wie lange
  it('U4: der Datenschutzsatz je Ort nennt Namen, Ziel und Dauer', () => {
    for (const t of [texte('de'), texte('en')]) {
      for (const satz of [t.datenschutz, t.datenschutzChat(24), t.datenschutzWlo, t.datenschutzWloOhne]) {
        expect(satz).toMatch(/^(Ordner- und Dateinamen gehen an den Chat|Folder and file names go to the chat)/);
      }
    }
    expect(texte('de').datenschutzChat(6)).toContain('bis zu 6 Stunden nach der letzten Nutzung');
    expect(texte('en').datenschutzChat(6)).toContain('up to 6 hours after last use');
    expect(texte('de').datenschutzWlo).toContain('bis du sie löschst');
    expect(texte('de').datenschutzWloOhne).not.toContain('Titel');
    // P2: „Weiter zur Vorschau“ legt nichts ab — erst der Knopf mit dem Namen des Orts
    expect(texte('de').datenschutzWlo).toContain('erst „In WLO ablegen und erschließen“ legt die Dateien');
    expect(texte('de').datenschutzWloOhne).toContain('erst „In WLO ablegen“ legt die Dateien');
    expect(texte('en').datenschutzWlo).toContain('only “Store and index in WLO” stores the files');
    expect(texte('de').datenschutzChat(6)).toContain('„Hier lesen“ schickt');
    for (const t of [texte('de'), texte('en')]) expect(alleTexte(t).join(' ')).not.toMatch(/„Hochladen“|“Upload”/);
  });
});

// Plan 2026-11-16, TG-1: das Manifest kennt kein Ziel mehr — `zweck` neutral, der alte Wert bleibt gültig.
describe('Manifest ui_upload (TG-1)', () => {
  const antwort = manifest.antwort as unknown as {
    properties: { aktion: { enum: string[] }; dokument: { required: string[]; properties: Record<string, unknown> } };
  };
  const zweck = (s: unknown) => (s as { properties: { zweck: { enum: string[] } } }).properties.zweck.enum;

  it('kein ziel am Dokument, keine Aktion ordner_als_entwurf', () => {
    // Plan 2026-11-17, Paket U4: dazu bereitgestellt (ein Upload-Weg, Feld ort)
    expect(antwort.properties.aktion.enum).toEqual(['erfasst', 'dokument', 'uebertragen', 'bereitgestellt']);
    expect(antwort.properties.dokument.required).not.toContain('ziel');
    expect(Object.keys(antwort.properties.dokument.properties)).not.toContain('ziel');
  });

  it('zweck bereitstellen, sammlungsstruktur bleibt gültig (Rückwärts)', () => {
    expect(zweck(manifest.eingabe)).toEqual(['bereitstellen', 'sammlungsstruktur']);
    expect(zweck(manifest.dienst.parameter)).toEqual(['bereitstellen', 'sammlungsstruktur']);
    expect(manifest.beispiele.every((b) => b.daten.zweck === 'bereitstellen')).toBe(true);
  });

  it('Beschreibung und wann ohne Themenbaum-Anweisung', () => {
    const text = [manifest.beschreibung, ...manifest.wann].join(' ');
    expect(text).not.toMatch(/themenbaum|entwurf/i);
  });
});

// Plan 2026-11-16, TG-3a: das Antwortschema kennt die Dateien je Ordner, das Manifest den Teil `struktur`.
describe('Manifest ui_upload (TG-3a)', () => {
  const antwort = manifest.antwort as unknown as {
    $defs: Record<string, { required?: string[]; properties: Record<string, { items?: { $ref?: string } }> }>;
    properties: { warnungen: { items: { enum: string[] } } };
  };

  it('jede Ordnerebene trägt `dateiliste` (nicht Pflicht — alte Antworten bleiben gültig)', () => {
    const ebenen = Object.entries(antwort.$defs).filter(([name]) => name.startsWith('ordner'));
    expect(ebenen).toHaveLength(9);
    for (const [, ebene] of ebenen) {
      expect(ebene.properties['dateiliste'].items?.$ref).toBe('#/$defs/datei');
      expect(ebene.required).not.toContain('dateiliste');
    }
    // Review TG-3a–c, R3-4: der Name ist Pflicht — außer bei Rolle „ignorieren“, dort verboten
    expect(antwort.$defs['datei'].required).toEqual(['i', 'endung', 'groesse', 'rolle']);
    const datei = antwort.$defs['datei'] as unknown as {
      if: { properties: { rolle: { const: string } } }; then: unknown; else: { required: string[] } };
    expect(datei.if.properties.rolle.const).toBe('ignorieren');
    expect(datei.then).toEqual({ not: { required: ['name'] } });
    expect(datei.else.required).toEqual(['name']);
  });

  it('die Warnung namen_gekuerzt und der Teil struktur', () => {
    expect(antwort.properties.warnungen.items.enum).toContain('namen_gekuerzt');
    expect((manifest as unknown as { vorgang: { schreibt: string[] } }).vorgang.schreibt)
      // Plan 2026-11-16, TG-3d: dazu die Verweise auf alle gelesenen Strukturdokumente
      // Paket U5: metadaten (quelle chatbot) aus „Hier im Chat“
      .toEqual(['structure', 'struktur', 'document', 'strukturdokument', 'metadaten']);
  });
});
