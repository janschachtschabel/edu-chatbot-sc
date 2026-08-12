import { describe, expect, it, vi } from 'vitest';

import { DE } from '../i18n/de';
import { EN } from '../i18n/en';
import { createTranslator } from '../i18n/dictionary';
import type { PreparedWriteOut } from '../grouping/message-types';
import {
  ANONYMOUS_AUTHORITY, identityPathFor, isAllowedPreparedWrite,
  preparedWriteMessageKey, runPreparedWrite,
} from './prepared-write';

const t = createTranslator(DE, DE);

const ABLEGEN: PreparedWriteOut = {
  method: 'PUT',
  path: '/edu-sharing/rest/collection/v1/collections/-home-'
    + '/11111111-2222-3333-4444-555555555555'
    + '/references/66666666-7777-8888-9999-000000000000',
  body: null,
  done_message: 'Das Material liegt jetzt in der Sammlung.',
};

const ENTFERNEN: PreparedWriteOut = { ...ABLEGEN, method: 'DELETE' };

/** Metadaten vorschlagen — die dritte erlaubte Anfrage, und die erste mit
 *  Rumpf. `type=AI` ist die Herkunftsangabe, die das Repositorium mitspeichert. */
const VORSCHLAG: PreparedWriteOut = {
  method: 'POST',
  path: '/edu-sharing/rest/suggestions/v1/-home-'
    + '/11111111-2222-3333-4444-555555555555?type=AI&version=wlo-mcp',
  body: '[{"propertyId":"cclom:general_description","value":"Ein Arbeitsblatt."}]',
  done_message: 'Als Vorschlag hinterlegt — der Datensatz ist unverändert.',
};

/** Antwort-Attrappe: nur das, was der Ausführer liest. */
function antwort(ok: boolean, koerper?: unknown): Response {
  return {
    ok,
    json: async () => {
      if (koerper === undefined) throw new SyntaxError('kein JSON');
      return koerper;
    },
  } as unknown as Response;
}

const ANGEMELDET = antwort(true, { person: { authorityName: 'max.muster' } });
const GAST = antwort(true, { person: { authorityName: ANONYMOUS_AUTHORITY } });

const HERKUNFT = 'https://repository.example';

function lauf(over: {
  write?: PreparedWriteOut;
  identitaet?: Response | (() => never);
  schreiben?: Response | (() => never);
  translate?: typeof t;
  origin?: string;
} = {}) {
  const gesagt: string[] = [];
  const aufrufe: Array<{ url: string; init?: RequestInit }> = [];
  const fetchImpl = vi.fn(async (url: unknown, init?: RequestInit) => {
    aufrufe.push({ url: String(url), init });
    const stufe = aufrufe.length === 1 ? over.identitaet ?? ANGEMELDET : over.schreiben ?? antwort(true, {});
    if (typeof stufe === 'function') stufe();
    return stufe as Response;
  });
  const ergebnis = runPreparedWrite(over.write ?? ABLEGEN, {
    origin: () => over.origin ?? HERKUNFT,
    say: (s: string) => { gesagt.push(s); },
    translate: over.translate ?? t,
    fetchImpl: fetchImpl as unknown as typeof fetch,
  });
  return { ergebnis, gesagt, aufrufe, fetchImpl };
}

describe('Riegel — Erlaubnisliste aus Methode und Pfadmuster', () => {
  it('lässt genau die beiden Anfragen durch, die E2 vorbereiten kann', () => {
    expect(isAllowedPreparedWrite(ABLEGEN)).toBe(true);
    expect(isAllowedPreparedWrite(ENTFERNEN)).toBe(true);
  });

  it('weist eine andere Methode auf demselben Pfad ab', () => {
    // Die Liste paart Methode UND Muster. Ein POST auf dieselbe Adresse ist
    // eine andere Handlung, auch wenn die Adresse stimmt.
    expect(isAllowedPreparedWrite({ ...ABLEGEN, method: 'POST' })).toBe(false);
    expect(isAllowedPreparedWrite({ ...ABLEGEN, method: 'GET' })).toBe(false);
  });

  it.each([
    ['fremder Endpunkt', '/edu-sharing/rest/node/v1/nodes/-home-/abc/metadata'],
    ['Sammlung selbst', '/edu-sharing/rest/collection/v1/collections/-home-/abc'],
    ['protokoll-relativ', '//boese.example/rest/collection/v1/collections/-home-/a/references/b'],
    ['Rückstrich', '/\\boese.example/rest/collection/v1/collections/-home-/a/references/b'],
    ['absolute Adresse', 'https://boese.example/edu-sharing/rest/collection/v1/collections/-home-/a/references/b'],
    ['Aufstieg im Pfad', '/edu-sharing/rest/collection/v1/collections/-home-/../../node/v1/references/b'],
    ['angehängte Abfrage', '/edu-sharing/rest/collection/v1/collections/-home-/a/references/b?force=true'],
    ['angehängter Pfadteil', '/edu-sharing/rest/collection/v1/collections/-home-/a/references/b/children'],
    ['leer', ''],
  ])('weist ab: %s', (_name, pfad) => {
    expect(isAllowedPreparedWrite({ ...ABLEGEN, path: pfad })).toBe(false);
  });

  it('lässt den Metadaten-Vorschlag durch (Nutzer-Entscheid 2026-08-12)', () => {
    expect(isAllowedPreparedWrite(VORSCHLAG)).toBe(true);
  });

  it.each([
    ['ohne Herkunftsangabe', VORSCHLAG.path.replace('type=AI&', '')],
    ['mit behaupteter Menschen-Herkunft', VORSCHLAG.path.replace('type=AI', 'type=HUMAN')],
    ['mit angehängtem dritten Parameter', `${VORSCHLAG.path}&status=ACCEPTED`],
    ['ohne Abfrage', VORSCHLAG.path.split('?')[0]],
  ])('weist den Vorschlag ab: %s', (_name, pfad) => {
    expect(isAllowedPreparedWrite({ ...VORSCHLAG, path: pfad })).toBe(false);
  });

  it('weist eine andere Methode auf dem Vorschlags-Pfad ab', () => {
    for (const methode of ['PUT', 'DELETE']) {
      expect(isAllowedPreparedWrite({ ...VORSCHLAG, method: methode })).toBe(false);
    }
  });

  it('weist eine überlange Kennung ab', () => {
    const lang = 'a'.repeat(65);
    expect(isAllowedPreparedWrite({
      ...ABLEGEN,
      path: `/edu-sharing/rest/collection/v1/collections/-home-/${lang}/references/b`,
    })).toBe(false);
  });

  it('erträgt einen Datensatz, der gar keiner ist', () => {
    // Das Feld kommt über die Leitung; ein fehlerhaftes Backend oder ein
    // manipulierter Zwischenstand darf hier nicht werfen, sondern muss
    // abgewiesen werden.
    for (const müll of [null, undefined, {}, { method: 'PUT' }, { path: 42 }]) {
      expect(isAllowedPreparedWrite(müll as unknown as PreparedWriteOut)).toBe(false);
    }
  });
});

describe('Wer-bin-ich-Pfad', () => {
  it('leitet ihn aus der Wurzel der erlaubten Anfrage ab', () => {
    expect(identityPathFor(ABLEGEN)).toBe('/edu-sharing/rest/iam/v1/people/-home-/-me-');
  });

  it('folgt einer anders benannten Wurzel', () => {
    // Die Wurzel steht in der Konfiguration des MCP-Servers, nicht im Bündel.
    // Fest verdrahtet wäre sie in einer Installation still falsch.
    expect(identityPathFor({
      ...ABLEGEN,
      path: ABLEGEN.path.replace('/edu-sharing/', '/repositorium/'),
    })).toBe('/repositorium/rest/iam/v1/people/-home-/-me-');
  });

  it('gibt für eine abgewiesene Anfrage nichts heraus', () => {
    expect(identityPathFor({ ...ABLEGEN, method: 'POST' })).toBe('');
  });
});

describe('Ausgang → Satz', () => {
  it.each([
    ['done', 'prepared.done'],
    ['blocked', 'prepared.blocked'],
    ['signed-out', 'prepared.signedOut'],
    ['unreachable', 'prepared.unreachable'],
    ['failed', 'prepared.failed'],
  ] as const)('%s → %s', (ausgang, schluessel) => {
    expect(preparedWriteMessageKey(ausgang)).toBe(schluessel);
  });

  it('jeder Schlüssel steht in BEIDEN Katalogen', () => {
    for (const k of ['prepared.done', 'prepared.blocked', 'prepared.signedOut',
                     'prepared.unreachable', 'prepared.failed']) {
      expect(DE[k], `DE fehlt ${k}`).toBeTruthy();
      expect(EN[k], `EN fehlt ${k}`).toBeTruthy();
    }
  });
});

describe('Ausführer', () => {
  it('setzt eine abgewiesene Anfrage gar nicht erst ab', async () => {
    const { ergebnis, gesagt, fetchImpl } = lauf({ write: { ...ABLEGEN, method: 'POST' } });
    await expect(ergebnis).resolves.toBe('blocked');
    expect(fetchImpl).not.toHaveBeenCalled();
    expect(gesagt).toEqual([DE['prepared.blocked']]);
  });

  it('fragt ZUERST, wer hier angemeldet ist', async () => {
    const { ergebnis, aufrufe } = lauf();
    await ergebnis;
    expect(aufrufe[0].url).toBe(`${HERKUNFT}/edu-sharing/rest/iam/v1/people/-home-/-me-`);
    expect(aufrufe[0].init?.method ?? 'GET').toBe('GET');
  });

  it('fragt nichts, wenn es keine Herkunft gibt', async () => {
    const { ergebnis, gesagt, fetchImpl } = lauf({ origin: '' });
    await expect(ergebnis).resolves.toBe('unreachable');
    expect(fetchImpl).not.toHaveBeenCalled();
    expect(gesagt).toEqual([DE['prepared.unreachable']]);
  });

  it('schreibt nichts, wenn die Sitzung abgelaufen ist', async () => {
    // Gemessen (§1 des Bauvorschlags): eine ungültige Sitzung antwortet 200 und
    // meldet `esguest`. Über den Statuscode sähe das wie ein Erfolg aus.
    const { ergebnis, gesagt, aufrufe } = lauf({ identitaet: GAST });
    await expect(ergebnis).resolves.toBe('signed-out');
    expect(aufrufe).toHaveLength(1);
    expect(gesagt).toEqual([DE['prepared.signedOut']]);
  });

  it.each([
    ['Antwort ohne Namen', antwort(true, { person: {} })],
    ['nicht ok', antwort(false, {})],
    ['kein JSON (fremde Seite)', antwort(true)],
  ])('schreibt nichts, wenn die Frage nach der Person scheitert: %s', async (_n, res) => {
    const { ergebnis, gesagt, aufrufe } = lauf({ identitaet: res });
    const ausgang = await ergebnis;
    expect(aufrufe).toHaveLength(1);
    expect(['signed-out', 'unreachable']).toContain(ausgang);
    expect(gesagt).toEqual([DE[preparedWriteMessageKey(ausgang)]]);
  });

  it('meldet einen Netzfehler als „nicht geklärt", nicht als Erfolg', async () => {
    const { ergebnis, gesagt } = lauf({
      identitaet: () => { throw new TypeError('Failed to fetch'); },
    });
    await expect(ergebnis).resolves.toBe('unreachable');
    expect(gesagt).toEqual([DE['prepared.unreachable']]);
  });

  it('setzt die Anfrage mit Methode, Pfad und Anmeldung der Seite ab', async () => {
    const { ergebnis, aufrufe } = lauf({
      write: { ...ENTFERNEN, body: '{"x":1}' },
    });
    await ergebnis;
    expect(aufrufe).toHaveLength(2);
    const [url, init] = [aufrufe[1].url, aufrufe[1].init!];
    // Die Herkunft kommt aus der SEITE, nie aus der Anfrage: so kann nichts
    // umgelenkt werden — auch nicht durch ein `<base href>` der Gastgeberseite,
    // dem eine relative Anfrage folgen würde.
    expect(url).toBe(`${HERKUNFT}${ENTFERNEN.path}`);
    expect(init.method).toBe('DELETE');
    expect(init.credentials).toBe('same-origin');
    expect(init.body).toBe('{"x":1}');
  });

  it('schickt ohne Rumpf auch keinen Inhaltstyp', async () => {
    const { ergebnis, aufrufe } = lauf();
    await ergebnis;
    expect(aufrufe[1].init?.body).toBeUndefined();
    expect(aufrufe[1].init?.headers ?? {}).not.toHaveProperty('Content-Type');
  });

  it('sagt den Satz des Werkzeugs an, das die Änderung kennt', async () => {
    const { ergebnis, gesagt } = lauf();
    await expect(ergebnis).resolves.toBe('done');
    expect(gesagt).toEqual([ABLEGEN.done_message]);
  });

  it('fällt auf den Katalog zurück, wenn das Werkzeug nichts mitgibt', async () => {
    const { ergebnis, gesagt } = lauf({ write: { ...ABLEGEN, done_message: '  ' } });
    await expect(ergebnis).resolves.toBe('done');
    expect(gesagt).toEqual([DE['prepared.done']]);
  });

  it.each([
    ['abgelehnt', antwort(false, {})],
    ['geworfen', (() => { throw new Error('Netz weg'); }) as () => never],
  ])('meldet ein gescheitertes Schreiben ehrlich: %s', async (_n, schreiben) => {
    const { ergebnis, gesagt } = lauf({ schreiben });
    await expect(ergebnis).resolves.toBe('failed');
    expect(gesagt).toEqual([DE['prepared.failed']]);
  });

  it('spricht die eingestellte Sprache', async () => {
    const { ergebnis, gesagt } = lauf({
      write: { ...ABLEGEN, done_message: '' },
      translate: createTranslator(EN, DE),
    });
    await ergebnis;
    expect(gesagt).toEqual([EN['prepared.done']]);
  });
});
