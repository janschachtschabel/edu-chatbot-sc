import { describe, expect, it, vi } from 'vitest';

import { HistoryMessage } from '../stream/chat-api';
import { antwortAuf, antwortAusVerlauf, antwortAusVerlaufHolen } from './antwort-aus-verlauf';

/**
 * Paket 7 (P2, P5-2): bricht der Strom ab, NACHDEM der Server die Frage
 * angenommen hat, rechnet er sie zu Ende und speichert die Antwort. Das Widget
 * schickt die Frage dann nicht noch einmal, sondern holt die Antwort aus dem
 * Verlauf.
 */
let naechsteId = 1;
const u = (content: string, id = naechsteId++): HistoryMessage => ({ id, role: 'user', content });
const a = (content: string, id = naechsteId++): HistoryMessage => ({ id, role: 'assistant', content });

/** Ein Warten ohne Uhr, das mitschreibt — mit stehender Uhr: ohne `jetzt` zählte `Date.now`,
 *  und eine Millisekunde des Testlaufs verschob das Restbudget (CI: 99 999 statt 100 000). */
function uhr() {
  const gewartet: number[] = [];
  return {
    gewartet,
    warten: (ms: number) => { gewartet.push(ms); return Promise.resolve(); },
    jetzt: () => 0,
  };
}

describe('antwortAuf', () => {
  it('nimmt die Bot-Nachricht nach der letzten gleichen Frage', () => {
    expect(antwortAuf([u('Hallo'), a('Hi'), u('Frage'), a('Antwort')], 'Frage')?.content)
      .toBe('Antwort');
  });

  it('wartet, solange die letzte gleiche Frage noch keine Antwort hat', () => {
    // Dieselbe Frage früher schon einmal beantwortet: das ist nicht die gesuchte.
    expect(antwortAuf([u('Frage'), a('alt'), u('Frage')], 'Frage')).toBeNull();
  });

  it('kennt die Frage nicht — keine Antwort', () => {
    expect(antwortAuf([u('anders'), a('x')], 'Frage')).toBeNull();
  });

  it('mit der ID vor dem Zug zählt eine frühere gleiche Frage nicht (Review C-4)', () => {
    // „Ja“ wurde schon einmal beantwortet; die neue Frage ist noch nicht
    // gespeichert. Ohne die ID käme sofort die alte Antwort.
    const alt = [u('Ja', 1), a('alte Antwort', 2)];
    expect(antwortAuf(alt, 'Ja', 2)).toBeNull();
    expect(antwortAuf([...alt, u('Ja', 3), a('neue Antwort', 4)], 'Ja', 2)?.content)
      .toBe('neue Antwort');
  });
});

describe('antwortAusVerlauf', () => {
  it('fragt nach, bis die Antwort da ist', async () => {
    const staende = [[u('Frage', 5)], [u('Frage', 5)], [u('Frage', 5), a('Fertig', 6)]];
    let i = 0;
    const { gewartet, warten, jetzt } = uhr();
    const antwort = await antwortAusVerlauf(
      () => Promise.resolve(staende[Math.min(i++, staende.length - 1)]), 'Frage',
      { nachId: 4, warten, jetzt },
    );
    expect(antwort?.content).toBe('Fertig');
    expect(gewartet).toHaveLength(2);
  });

  it('der Abstand wächst, höchstens 15 Abrufe je Minute (Review C-3)', async () => {
    // Das Ratenlimit gilt je IP und Route (Vorgabe 20/min) — hinter einer
    // Schul-NAT teilen es sich alle Widgets. Der alte 2-s-Takt brauchte 30.
    let abrufe = 0;
    const { gewartet, warten, jetzt } = uhr();
    await antwortAusVerlauf(
      () => { abrufe++; return Promise.resolve([u('Frage', 9)]); }, 'Frage', { nachId: 8, warten, jetzt },
    );
    let t = 0;
    const zeitpunkte = [0, ...gewartet.map((ms) => (t += ms))];
    for (const start of zeitpunkte) {
      expect(zeitpunkte.filter((z) => z >= start && z < start + 60_000).length).toBeLessThanOrEqual(15);
    }
    expect(gewartet.slice(0, 3)).toEqual([...gewartet.slice(0, 3)].sort((x, y) => x - y));
    expect(abrufe).toBe(zeitpunkte.length);
  });

  it('gibt nach der Gesamtfrist auf (wie der Stale-Wächter: 100 s)', async () => {
    const { gewartet, warten, jetzt } = uhr();
    const antwort = await antwortAusVerlauf(
      () => Promise.resolve([u('Frage', 9)]), 'Frage', { nachId: 8, warten, jetzt },
    );
    expect(antwort).toBeNull();
    const summe = gewartet.reduce((s, ms) => s + ms, 0);
    expect(summe).toBeLessThanOrEqual(100_000);
    expect(summe).toBeGreaterThan(80_000);
  });

  it('steht die Frage nach der Frist nicht im Verlauf, kommt auch keine Antwort', async () => {
    // Beschäftigte Sitzung oder ein Absturz vor dem Speichern: der Zug endet,
    // ohne die Frage abzulegen. Die Sperre wartet höchstens 20 s.
    const { gewartet, warten, jetzt } = uhr();
    const antwort = await antwortAusVerlauf(
      () => Promise.resolve([u('Ja', 1), a('alt', 2)]), 'Ja', { nachId: 2, warten, jetzt },
    );
    expect(antwort).toBeNull();
    const summe = gewartet.reduce((s, ms) => s + ms, 0);
    expect(summe).toBeGreaterThanOrEqual(40_000);
    expect(summe).toBeLessThan(60_000);
  });

  it('beachtet ein 429 samt Retry-After und fragt danach weiter', async () => {
    let i = 0;
    const { gewartet, warten, jetzt } = uhr();
    const antwort = await antwortAusVerlauf(() => {
      i++;
      if (i === 1) return Promise.reject(Object.assign(new Error('429'), { status: 429, retryAfterMs: 30_000 }));
      return Promise.resolve([u('Frage', 9), a('Fertig', 10)]);
    }, 'Frage', { nachId: 8, warten, jetzt });
    expect(antwort?.content).toBe('Fertig');
    expect(gewartet).toEqual([30_000]);
  });

  it('ein Netzfehler beim Nachfragen ist kein Ende', async () => {
    let i = 0;
    const { warten, jetzt } = uhr();
    const antwort = await antwortAusVerlauf(() => (++i === 1
      ? Promise.reject(new Error('network'))
      : Promise.resolve([u('Frage', 9), a('Fertig', 10)])), 'Frage', { nachId: 8, warten, jetzt });
    expect(antwort?.content).toBe('Fertig');
  });

  it('hört auf, sobald der Zug nicht mehr zählt (Neustart, Widget weg)', async () => {
    let abrufe = 0;
    let weg = false;
    const antwort = await antwortAusVerlauf(
      () => { abrufe++; weg = true; return Promise.resolve([u('Frage', 9)]); }, 'Frage',
      { nachId: 8, abgebrochen: () => weg, warten: () => Promise.resolve() },
    );
    expect(antwort).toBeNull();
    expect(abrufe).toBe(1);
  });

  it('eine Antwort, die nach dem Ende der Nachfrage eintrifft, zählt nicht (Paket 9)', async () => {
    // Review Paket 7 (MINOR 24): geprüft wurde nur am Schleifenanfang — eine späte
    // Antwort nach Neustart oder Entfernen lief noch in `_onResult` (Vorlesen,
    // Ereignisse an die Gastseite).
    let weg = false;
    const antwort = await antwortAusVerlauf(
      () => { weg = true; return Promise.resolve([u('Frage', 9), a('Fertig', 10)]); }, 'Frage',
      { nachId: 8, abgebrochen: () => weg, warten: () => Promise.resolve() },
    );
    expect(antwort).toBeNull();
  });

  it('ein abgebrochenes Signal beendet die Nachfrage (Paket 9)', async () => {
    const steuerung = new AbortController();
    const antwort = await antwortAusVerlauf(
      () => { steuerung.abort(); return Promise.resolve([u('Frage', 9), a('Fertig', 10)]); },
      'Frage', { nachId: 8, signal: steuerung.signal, warten: () => Promise.resolve() },
    );
    expect(antwort).toBeNull();
  });

  it('die Frist zählt auch die Zeit der Abrufe (Paket 9)', async () => {
    // Review Paket 7 (MINOR 23): gezählt wurden nur die Pausen — ein Abruf, der
    // 30 s hängt, verlängerte die Nachfrage um 30 s.
    let uhrzeit = 0;
    let abrufe = 0;
    const antwort = await antwortAusVerlauf(
      () => { abrufe++; uhrzeit += 30_000; return Promise.resolve([u('Frage', 9)]); }, 'Frage',
      { nachId: 8, warten: () => Promise.resolve(), jetzt: () => uhrzeit },
    );
    expect(antwort).toBeNull();
    expect(abrufe).toBeLessThanOrEqual(4);
  });

  it('ein hängender Abruf wird nach seiner Frist abgebrochen (Paket 9)', async () => {
    vi.useFakeTimers();
    try {
      const signale: AbortSignal[] = [];
      const laden = (signal?: AbortSignal): Promise<HistoryMessage[]> => {
        signale.push(signal!);
        if (signale.length > 1) return Promise.resolve([u('Frage', 9), a('Fertig', 10)]);
        return new Promise((_, ablehnen) => signal!.addEventListener('abort', () => ablehnen(new Error('abgebrochen'))));
      };
      const laufend = antwortAusVerlauf(laden, 'Frage', { nachId: 8, warten: () => Promise.resolve() });
      await vi.advanceTimersByTimeAsync(20_000);
      expect((await laufend)?.content).toBe('Fertig');
      expect(signale[0].aborted).toBe(true);
    } finally {
      vi.useRealTimers();
    }
  });

  it('Retry-After 0 hält den gewohnten Takt (Paket 9)', async () => {
    let i = 0;
    const { gewartet, warten, jetzt } = uhr();
    await antwortAusVerlauf(() => (++i === 1
      ? Promise.reject(Object.assign(new Error('429'), { status: 429, retryAfterMs: 0 }))
      : Promise.resolve([u('Frage', 9), a('Fertig', 10)])), 'Frage', { nachId: 8, warten, jetzt });
    expect(gewartet).toEqual([2_000]);
  });

  it('ein langes Retry-After nutzt das Restbudget statt sofort aufzugeben (Paket 9)', async () => {
    let i = 0;
    const { gewartet, warten, jetzt } = uhr();
    const antwort = await antwortAusVerlauf(() => (++i === 1
      ? Promise.reject(Object.assign(new Error('429'), { status: 429, retryAfterMs: 300_000 }))
      : Promise.resolve([u('Frage', 9), a('Fertig', 10)])), 'Frage', { nachId: 8, warten, jetzt });
    expect(antwort?.content).toBe('Fertig');
    expect(gewartet).toEqual([100_000]);
  });
});

describe('antwortAusVerlaufHolen', () => {
  it('macht aus dem Verlaufseintrag eine Antwort, wie die Shell sie zeigt', async () => {
    const eintrag: HistoryMessage = {
      id: 2, role: 'assistant', content: 'Fertig', cards: [{ node_id: 'n1' }],
      webLinks: [{ title: 'WLO', url: 'https://wlo.de' }],
    };
    const resp = await antwortAusVerlaufHolen(
      () => Promise.resolve([u('Frage', 1), eintrag]), 'Frage', 'bb-1',
      { warten: () => Promise.resolve() },
    );
    expect(resp).toMatchObject({
      session_id: 'bb-1', content: 'Fertig', cards: [{ node_id: 'n1' }],
      web_links: [{ title: 'WLO', url: 'https://wlo.de' }], quick_replies: [],
    });
  });

  it('bringt die Ergebnis-Boxen und die Themenseite mit (Review C-2)', async () => {
    // Bei `zeige_dokument` steht im Text nur der Begleitsatz — die Box selbst
    // liegt am Verlaufseintrag unter `ui.dokumente` (Paket 18C/D).
    const themenseite = { variant_title: 'Optik', topic_page_url: 'https://wlo.de/t', swimlanes: [{ title: 'A' }] };
    const eintrag: HistoryMessage = {
      id: 2, role: 'assistant', content: 'Hier ist dein Arbeitsblatt.',
      ui: {
        dokumente: [
          { kind: 'ki_material', title: 'Arbeitsblatt', content: '# Linsen', gekuerzt: false },
          { kind: 'lernpfad', title: 'Pfad', content: '# Lang', gekuerzt: true },
          { kind: 'x', title: 'leer', content: '   ' },
        ],
        topic_page_view: themenseite,
      },
    };
    const resp = await antwortAusVerlaufHolen(
      () => Promise.resolve([u('Frage', 1), eintrag]), 'Frage', 'bb-1',
      { warten: () => Promise.resolve(), gekuerztHinweis: '(gekürzt)' },
    );
    expect(resp?.inline_documents).toEqual([
      { kind: 'ki_material', title: 'Arbeitsblatt', content: '# Linsen' },
      { kind: 'lernpfad', title: 'Pfad', content: '# Lang\n\n(gekürzt)' },
    ]);
    expect(resp?.topic_page).toEqual(themenseite);
  });

  it('bringt die vorbereitete Änderung mit — sonst führte die Seite sie nie aus (Paket 9)', async () => {
    // Review Paket 7 (MAJOR 7): reißt beim „ja“ der Strom ab, löst der Server den
    // Vorgang trotzdem ein. Ohne die Anfrage am Verlaufseintrag zeigte die Blase
    // „wird in der Seite ausgeführt“, und nichts geschah; der Vorgang war verbraucht.
    const anfrage = { method: 'PUT', path: '/edu-sharing/rest/x/n1', body: null, done_message: 'Erledigt.' };
    const eintrag: HistoryMessage = {
      id: 2, role: 'assistant', content: 'Wird in der Seite ausgeführt.',
      ui: { prepared_write: anfrage },
    };
    const resp = await antwortAusVerlaufHolen(
      () => Promise.resolve([u('ja', 1), eintrag]), 'ja', 'bb-1',
      { nachId: 0, warten: () => Promise.resolve() },
    );
    expect(resp?.prepared_write).toEqual(anfrage);
  });

  it('ohne sichere Zuordnung wird keine Antwort mit Änderung übernommen (Review Paket 9)', async () => {
    // Fehlt `after_id` (der Handschlag las die Datenbank nicht binnen 1 s), zählt nur der
    // Text — und der erste Abruf kommt, bevor die neue Frage gespeichert ist. Ein früheres
    // „Ja, so ausführen“ liefe samt Änderung noch einmal. Der ehrliche Hinweis ist besser
    // als eine fremde Antwort, die „wird ausgeführt“ sagt.
    const alt: HistoryMessage = {
      id: 2, role: 'assistant', content: 'Wird in der Seite ausgeführt.',
      ui: { prepared_write: { method: 'PUT', path: '/edu-sharing/rest/x/n1', body: null, done_message: '' } },
    };
    const resp = await antwortAusVerlaufHolen(
      () => Promise.resolve([u('Ja, so ausführen', 1), alt]), 'Ja, so ausführen', 'bb-1',
      { warten: () => Promise.resolve() },
    );
    expect(resp).toBeNull();
  });

  it('eine verbogene Anfrage am Verlaufseintrag wird nicht ausgeliefert', async () => {
    for (const roh of [{ method: 'PUT' }, { method: 1, path: '/x' }, 'PUT /x', { method: 'PUT', path: 'x' }]) {
      const eintrag: HistoryMessage = { id: 2, role: 'assistant', content: 'x', ui: { prepared_write: roh } };
      const resp = await antwortAusVerlaufHolen(
        () => Promise.resolve([u('ja', 1), eintrag]), 'ja', 'bb-1', { nachId: 0, warten: () => Promise.resolve() },
      );
      expect(resp?.prepared_write ?? null).toBeNull();
    }
  });

  it('ohne Antwort bleibt es bei null', async () => {
    const resp = await antwortAusVerlaufHolen(
      () => Promise.resolve([u('Frage', 1)]), 'Frage', 'bb-1',
      { nachId: 0, warten: () => Promise.resolve() },
    );
    expect(resp).toBeNull();
  });
});
