import { describe, expect, it } from 'vitest';

import { groupSignals, splitMaterialTypes } from './reference-catalogs';

const SIGNALS = [
  { id: 'zeitdruck', modulations: { dimension: 'D1-Zeit', label: 'Zeitdruck', tone: 'sachlich', length: 'kurz', skip_intro: true } },
  { id: 'unsicher', modulations: { dimension: 'D2-Sicherheit', label: 'Unsicher', tone: 'empathisch', length: 'mittel', one_option: true } },
  { id: 'effizient', modulations: { dimension: 'D1-Zeit', label: 'Effizient', tone: 'sachlich', length: 'kurz', skip_intro: true } },
];

describe('groupSignals', () => {
  it('gruppiert nach der Dimension aus der Konfiguration, in Schlüssel-Reihenfolge', () => {
    const groups = groupSignals(SIGNALS);
    expect(groups.map((g) => g.key)).toEqual(['D1-Zeit', 'D2-Sicherheit']);
    expect(groups[0].signals.map((s) => s.id)).toEqual(['zeitdruck', 'effizient']);
  });

  it('macht aus `D1-Zeit` eine lesbare Überschrift, ohne etwas dazuzudichten', () => {
    // ALT schrieb „D1 — Zeit & Druck"; „& Druck" steht nirgends in der Config.
    expect(groupSignals(SIGNALS)[0].heading).toBe('D1 — Zeit');
  });

  it('zeigt jede gesetzte Flagge, auch eine unbekannte', () => {
    const [group] = groupSignals([
      { id: 'x', modulations: { dimension: 'D9-Neu', tone: 't', length: 'l', show_more: true, brandneu: true } },
    ]);
    // A hand-written list of known flags would silently drop a flag added later —
    // exactly how ALT's table came to omit `skip_intro` on five signals.
    //
    // Seit C1-d5c2 liefert die Funktion Katalog-SCHLÜSSEL statt fertiger Wörter.
    // Der Durchfall ist derselbe geblieben und hier weiter gepinnt: bekanntes
    // Flag → sein Schlüssel, unbekanntes → es selbst. Am Bildschirm steht
    // deshalb weiterhin `brandneu`, denn `createTranslator` gibt einen
    // unbekannten Schlüssel unverändert aus — belegt in
    // `reference-catalogs.component.spec.ts`, in beiden Sprachen.
    expect(group.signals[0].flags).toEqual(['rc.flag.showMore', 'brandneu']);
  });

  it('lässt tone/length weg, wenn das Signal sie nicht setzt', () => {
    // `zielgerichtet` setzt in der Config KEINE Länge — eine erfundene Länge
    // wäre eine Behauptung über den Prompt, die er nicht macht.
    const [group] = groupSignals([
      { id: 'zielgerichtet', modulations: { dimension: 'D3-Haltung', tone: 'sachlich', skip_intro: true } },
    ]);
    expect(group.signals[0].length).toBe('');
    expect(group.signals[0].tone).toBe('sachlich');
  });

  it('überlebt eine Antwort ohne Modulationen', () => {
    expect(groupSignals([{ id: 'kaputt' }])).toEqual([]);
    expect(groupSignals([])).toEqual([]);
  });
});

describe('splitMaterialTypes', () => {
  const DOC = {
    material_types: [
      { id: 'auto', label: 'Automatisch', emoji: '🤖', category: 'didaktisch' },
      { id: 'arbeitsblatt', label: 'Arbeitsblatt', emoji: '📝', category: 'didaktisch' },
      { id: 'bericht', label: 'Bericht', emoji: '📊', category: 'analytisch' },
      { id: 'exotisch', label: 'Exotisch', emoji: '', category: 'neu' },
    ],
  };

  it('trennt nach der Kategorie aus der Konfiguration', () => {
    const split = splitMaterialTypes(DOC);
    expect(split.didaktisch.map((t) => t.id)).toEqual(['auto', 'arbeitsblatt']);
    expect(split.analytisch.map((t) => t.id)).toEqual(['bericht']);
  });

  it('lässt eine unbekannte Kategorie nicht unter den Tisch fallen', () => {
    // Stiller Verlust wäre schlimmer als eine dritte Spalte: die Datei ist
    // redaktionell pflegbar, eine neue Kategorie ist jederzeit möglich.
    expect(splitMaterialTypes(DOC).weitere.map((t) => t.id)).toEqual(['exotisch']);
  });

  it('zählt `auto` als Selektor, nicht als Typ', () => {
    // Der Grund für ALTs „Didaktisch (13)" über 12 echten Typen: `auto` ist der
    // „such du einen aus"-Eintrag und steht mit category didaktisch in der Liste.
    const split = splitMaterialTypes(DOC);
    expect(split.entries).toBe(4);
    expect(split.types).toBe(3);
  });

  it('überlebt eine Antwort ohne material_types', () => {
    const empty = splitMaterialTypes({});
    expect(empty.didaktisch).toEqual([]);
    expect(empty.entries).toBe(0);
  });
});
