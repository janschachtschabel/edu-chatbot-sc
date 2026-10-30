import { describe, expect, it } from 'vitest';

import { StreamHttpError, StreamServerError } from '../stream/stream-client';
import { fehlerKurz, fehlernummer } from './fehler-kurz';

// Paket 18E: was in die Konsole der Gastseite geht, trägt keinen Inhalt — nur die Art des
// Fehlers, den HTTP-Status und die Fehlernummer (die im Studio zum Zug führt).
const MARKE = 'KANARIE7Q';

describe('fehlerKurz', () => {
  it('nennt die Fehlerart, nie den Text', () => {
    const kurz = fehlerKurz(new TypeError(`kann ${MARKE} nicht lesen`));
    expect(kurz).toBe('TypeError');
  });

  it('nennt den HTTP-Status', () => {
    expect(fehlerKurz(new StreamHttpError(429))).toBe('StreamHttpError status=429');
    const verlauf = Object.assign(new Error(`History error: 503 ${MARKE}`), { status: 503 });
    expect(fehlerKurz(verlauf)).toBe('Error status=503');
  });

  it('nennt die Fehlernummer, nicht die Meldung des Servers', () => {
    const fehler = new StreamServerError('internal', `Antwort zu ${MARKE} gescheitert`,
                                         '1a2b3c4d5e6f');
    expect(fehlerKurz(fehler)).toBe('StreamServerError nummer=1a2b3c4d5e6f');
  });

  it('übergeht Status und Nummer, die nicht so aussehen', () => {
    const fremd = Object.assign(new Error('x'), { status: `${MARKE}`, nummer: `${MARKE} Text` });
    expect(fehlerKurz(fremd)).toBe('Error');
    expect(fehlerKurz(Object.assign(new Error('x'), { status: 99999 }))).toBe('Error');
  });

  it('nimmt den Namen nur von echten Fehlern — ein geworfenes Objekt kann alles tragen', () => {
    expect(fehlerKurz({ name: MARKE, message: MARKE })).toBe('object');
    expect(fehlerKurz(`${MARKE} als Text geworfen`)).toBe('string');
    expect(fehlerKurz(undefined)).toBe('undefined');
    expect(fehlerKurz(null)).toBe('null');
  });

  it('übergeht einen Namen, der kein Bezeichner ist', () => {
    const fehler = new Error('x');
    fehler.name = `${MARKE} mit Leerzeichen`;
    expect(fehlerKurz(fehler)).toBe('Error');
  });

  it('kennt DOMException-Namen wie AbortError', () => {
    expect(fehlerKurz(new DOMException('abgebrochen', 'AbortError'))).toBe('AbortError');
  });

  it('enthält in keinem Fall das Markierwort', () => {
    // Eine Nummer im Zeichenvorrat der Trace-ID gilt als Fehlernummer — so soll es sein;
    // hier also eine, die keine sein kann.
    const faelle: unknown[] = [
      new Error(MARKE), new StreamServerError(MARKE, MARKE, `${MARKE} Text`),
      { status: 500, name: MARKE },
      MARKE, [MARKE], Object.assign(new Error(MARKE), { status: 500, nummer: 'abc' }),
    ];
    for (const fall of faelle) expect(fehlerKurz(fall)).not.toContain(MARKE);
  });
});

describe('fehlernummer', () => {
  it('nimmt nur den Zeichenvorrat der Trace-ID', () => {
    expect(fehlernummer('1a2b3c4d5e6f')).toBe('1a2b3c4d5e6f');
    expect(fehlernummer('mit Leerzeichen')).toBe('');
    expect(fehlernummer(42)).toBe('');
    expect(fehlernummer(undefined)).toBe('');
  });
});
