import { describe, expect, it } from 'vitest';

import { chatAntwort, codeVon, gelesenAus, namenAntwort, wiederholbar } from './upload-chat';
import { erfasse, type Quelle } from './upload-erfassen';
import { setzeRolle } from './upload-rollen';

/** Plan 2026-11-17, Paket U4 (Teil b): „Hier im Chat“ — Regeln ohne DOM. */
function q(relPfad: string, size = 10, type = 'application/pdf'): Quelle<null> {
  return { relPfad, name: relPfad.split('/').pop() ?? relPfad, size, type, handle: null };
}
const ID = '11111111-2222-4333-8444-555555555555';

describe('Hier im Chat (Paket U4)', () => {
  it('ein Befund gilt nur mit einer upload_id in der Form des Vertrags', () => {
    expect(gelesenAus({ upload_id: ID, rolle: 'inhalt', angaben: { titel: 'x' } })).toBe(ID);
    expect(gelesenAus({ upload_id: 'abc' })).toBeNull();
    expect(gelesenAus({})).toBeNull();
  });

  it('die Antwort `bereitgestellt` mit Ort chat trägt je gelesener Datei i, Rolle und upload_id', () => {
    let e = erfasse([q('P/Lehrplan.pdf'), q('P/a.pdf'), q('P/b.pptx')]);
    e = setzeRolle(e, 0, 'struktur');
    const a = chatAntwort(e, [{ i: 0, rolle: 'struktur', upload_id: ID }]);
    expect(a).toMatchObject({ aktion: 'bereitgestellt', ort: 'chat', dateien: [{ i: 0, rolle: 'struktur', upload_id: ID }] });
    expect(a.zahlen).toMatchObject({ inhalte: 2, strukturdokumente: 1 });
    expect(a).not.toHaveProperty('ablage');
    expect(a).not.toHaveProperty('dokument');
  });

  it('„Nur Namen senden“: Ort namen ohne Dateien und ohne Ablage', () => {
    const a = namenAntwort(erfasse([q('P/a.pdf')]));
    expect(a).toMatchObject({ aktion: 'bereitgestellt', ort: 'namen' });
    expect(a).not.toHaveProperty('dateien');
    expect(a).not.toHaveProperty('ablage');
  });

  it('Codes: 429 gedrosselt, 413 ohne Code zu groß; die Grenzen der Sitzung kommen als Code', () => {
    expect(codeVon({ status: 429 })).toBe('gedrosselt');
    expect(codeVon({ status: 413 })).toBe('zu_gross');
    expect(codeVon({ status: 413, code: 'grenze_gesamt' })).toBe('grenze_gesamt');
    expect(codeVon({ status: 409, code: 'grenze_anzahl' })).toBe('grenze_anzahl');
    expect(codeVon({ code: '<b>' })).toBe('fehler');
  });

  it('ein neuer Versuch nur, wo er helfen kann — nicht an der Grenze der Sitzung', () => {
    expect(wiederholbar('netz')).toBe(true);
    expect(wiederholbar('ausgelastet')).toBe(true);
    expect(wiederholbar('grenze_anzahl')).toBe(false);
    expect(wiederholbar('grenze_gesamt')).toBe(false);
    expect(wiederholbar('kein_text')).toBe(false);
  });
});
