// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from 'vitest';

import {
  MCP_ACCESS_HEADER,
  MCP_ACCESS_STORAGE_KEY,
  accessBlockHeaders,
  clearAccessBlock,
  isWellFormedAccessBlock,
  readAccessBlock,
  writeAccessBlock,
} from './mcp-access';

const BLOCK = 'wlo2.QUJD-_x=.aXY.Y3Q';

beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
});

describe('isWellFormedAccessBlock', () => {
  it('accepts the two shapes the MCP server issues', () => {
    // wlo2.<b64u>.<b64u>.<b64u> (AUTH.md §3) und der Anonym-Block (§5b).
    expect(isWellFormedAccessBlock(BLOCK)).toBe(true);
    expect(isWellFormedAccessBlock('wlo-anon.v1')).toBe(true);
  });

  it('rejects a block that arrived with the word Bearer', () => {
    // AUTH.md §5a: genau dafür hat die /auth-Seite zwei Kopier-Knöpfe.
    expect(isWellFormedAccessBlock('Bearer ' + BLOCK)).toBe(false);
  });

  it('rejects foreign credentials and control characters', () => {
    expect(isWellFormedAccessBlock('Basic aGFsbG86d2VsdA==')).toBe(false);
    expect(isWellFormedAccessBlock('wlo2.abc\r\nX-Schmuggel: ja')).toBe(false);
    expect(isWellFormedAccessBlock('wlo2.' + 'a'.repeat(9000))).toBe(false);
    expect(isWellFormedAccessBlock('')).toBe(false);
    expect(isWellFormedAccessBlock(null)).toBe(false);
  });
});

describe('Ablage', () => {
  it('legt den Block in sessionStorage, nicht in localStorage', () => {
    // Der Block verschlüsselt ein WLO-Passwort und läuft NICHT ab (AUTH.md §5b).
    // Er darf deshalb nicht neben der Sitzungskennung liegen, die absichtlich
    // langlebig und über ?bsid= teilbar ist.
    expect(writeAccessBlock(BLOCK)).toBe(true);
    expect(sessionStorage.getItem(MCP_ACCESS_STORAGE_KEY)).toBe(BLOCK);
    expect(localStorage.getItem(MCP_ACCESS_STORAGE_KEY)).toBeNull();
    expect(readAccessBlock()).toBe(BLOCK);
  });

  it('speichert einen unbrauchbaren Wert gar nicht erst', () => {
    expect(writeAccessBlock('Basic aGk=')).toBe(false);
    expect(readAccessBlock()).toBeNull();
  });

  it('verwirft einen unbrauchbaren Wert auch beim Lesen', () => {
    // Fremder Code auf der Gastgeberseite teilt sich diesen Speicher.
    sessionStorage.setItem(MCP_ACCESS_STORAGE_KEY, 'Basic aGk=');
    expect(readAccessBlock()).toBeNull();
  });

  it('räumt beim Abmelden wirklich auf', () => {
    writeAccessBlock(BLOCK);
    clearAccessBlock();
    expect(readAccessBlock()).toBeNull();
    expect(sessionStorage.getItem(MCP_ACCESS_STORAGE_KEY)).toBeNull();
  });
});

describe('accessBlockHeaders', () => {
  it('gibt ohne Anmeldung ein leeres Objekt — keine leere Kopfzeile', () => {
    // Eine leere Kopfzeile würde das Backend als „vorgelegt, aber unbrauchbar"
    // melden und für jeden anonymen Zug eine Warnung protokollieren.
    expect(accessBlockHeaders()).toEqual({});
  });

  it('trägt den Block unter der vereinbarten Kopfzeile', () => {
    writeAccessBlock(BLOCK);
    expect(accessBlockHeaders()).toEqual({ [MCP_ACCESS_HEADER]: BLOCK });
  });

  it('nutzt NICHT die Authorization-Kopfzeile', () => {
    // Die gilt dem Server, den man anspricht; dieser Block gilt dem
    // MCP-Server dahinter.
    writeAccessBlock(BLOCK);
    expect(Object.keys(accessBlockHeaders())).not.toContain('Authorization');
  });
});
