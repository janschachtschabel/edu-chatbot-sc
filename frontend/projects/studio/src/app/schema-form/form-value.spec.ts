import { describe, expect, it } from 'vitest';

import { getAt, removeAt, renameKeyAt, setAt } from './form-value';

describe('getAt', () => {
  const doc = { welcome: { greeting: 'Moin', quick_replies: ['a', 'b'] } };

  it('returns the document itself for an empty path', () => {
    expect(getAt(doc, [])).toBe(doc);
  });

  it('reads through objects and arrays', () => {
    expect(getAt(doc, ['welcome', 'greeting'])).toBe('Moin');
    expect(getAt(doc, ['welcome', 'quick_replies', 1])).toBe('b');
  });

  it('returns undefined for a missing key or index', () => {
    expect(getAt(doc, ['nope'])).toBeUndefined();
    expect(getAt(doc, ['welcome', 'quick_replies', 9])).toBeUndefined();
  });

  it('returns undefined instead of throwing when it hits a non-container', () => {
    expect(getAt(doc, ['welcome', 'greeting', 'deeper'])).toBeUndefined();
    expect(getAt(null, ['a'])).toBeUndefined();
  });
});

describe('setAt', () => {
  it('replaces the whole document for an empty path', () => {
    expect(setAt({ a: 1 }, [], { b: 2 })).toEqual({ b: 2 });
  });

  it('writes a nested value', () => {
    const doc = { welcome: { greeting: 'Moin' } };
    expect(setAt(doc, ['welcome', 'greeting'], 'Servus')).toEqual({
      welcome: { greeting: 'Servus' },
    });
  });

  it('writes into an array by index', () => {
    const doc = { qr: ['a', 'b'] };
    expect(setAt(doc, ['qr', 1], 'x')).toEqual({ qr: ['a', 'x'] });
  });

  it('leaves the input untouched', () => {
    const doc = { welcome: { greeting: 'Moin' } };
    setAt(doc, ['welcome', 'greeting'], 'Servus');
    expect(doc.welcome.greeting).toBe('Moin');
  });

  it('keeps untouched branches identical by reference', () => {
    // this is what preserves the 357 unpinned config paths: the form only
    // rebuilds the spine down to the edited value, never the whole document
    const doc = { a: { deep: 1 }, b: { untouched: true } };
    const next = setAt(doc, ['a', 'deep'], 2);
    expect(next.b).toBe(doc.b);
    expect(next.a).not.toBe(doc.a);
  });

  it('creates a missing object on the way down', () => {
    expect(setAt({}, ['welcome', 'greeting'], 'Moin')).toEqual({
      welcome: { greeting: 'Moin' },
    });
  });

  it('creates a missing array when the next segment is an index', () => {
    expect(setAt({}, ['qr', 0], 'a')).toEqual({ qr: ['a'] });
  });

  it('replaces a non-container standing where a container is needed', () => {
    expect(setAt({ welcome: 'oops' }, ['welcome', 'greeting'], 'Moin')).toEqual({
      welcome: { greeting: 'Moin' },
    });
  });

  it('writes a NAMED key even when an array stands in the way', () => {
    // `arr[Number('greeting')]` would set a "NaN" property that JSON.stringify
    // drops: the edit would vanish AND the dirty check would stay false
    const next = setAt({ welcome: [] }, ['welcome', 'greeting'], 'Moin');
    expect(JSON.parse(JSON.stringify(next))).toEqual({ welcome: { greeting: 'Moin' } });
  });

  it('writes an INDEXED key even when an object stands in the way', () => {
    const next = setAt({ qr: { a: 1 } }, ['qr', 0], 'x');
    expect(JSON.parse(JSON.stringify(next))).toEqual({ qr: ['x'] });
  });

  it('keeps a __proto__ key as an own property instead of polluting', () => {
    // config data is user input; a path helper that writes it through
    // Object.assign or by mutation would reach Object.prototype
    const next = setAt({}, ['__proto__', 'polluted'], true) as Record<string, unknown>;
    expect(Object.hasOwn(next, '__proto__')).toBe(true);
    expect(({} as Record<string, unknown>)['polluted']).toBeUndefined();
    const renamed = renameKeyAt({ a: 1 }, [], 'a', '__proto__') as Record<string, unknown>;
    expect(Object.hasOwn(renamed, '__proto__')).toBe(true);
    expect(({} as Record<string, unknown>)['a']).toBeUndefined();
  });
});

describe('removeAt', () => {
  it('deletes an object key', () => {
    expect(removeAt({ a: 1, b: 2 }, ['a'])).toEqual({ b: 2 });
  });

  it('splices an array entry so later ones shift down', () => {
    expect(removeAt({ qr: ['a', 'b', 'c'] }, ['qr', 1])).toEqual({ qr: ['a', 'c'] });
  });

  it('leaves the input untouched', () => {
    const doc = { qr: ['a', 'b'] };
    removeAt(doc, ['qr', 0]);
    expect(doc.qr).toEqual(['a', 'b']);
  });

  it('is a no-op for a path that is not there', () => {
    const doc = { a: 1 };
    expect(removeAt(doc, ['nope'])).toBe(doc);
    expect(removeAt(doc, ['a', 'deeper'])).toBe(doc);
  });

  it('is a no-op for an array index outside the list', () => {
    const doc = { qr: ['a', 'b'] };
    expect(removeAt(doc, ['qr', 2])).toBe(doc);
    expect(removeAt(doc, ['qr', -1])).toBe(doc);
    expect(removeAt(doc, ['qr', 'nope'])).toBe(doc);
  });

  it('refuses an empty path rather than returning nothing', () => {
    const doc = { a: 1 };
    expect(removeAt(doc, [])).toBe(doc);
  });
});

describe('renameKeyAt', () => {
  it('renames a key of a nested map in place', () => {
    const doc = { areas: { FAQ: { mode: 'always' }, OER: { mode: 'on-demand' } } };
    expect(renameKeyAt(doc, ['areas'], 'FAQ', 'Fragen')).toEqual({
      areas: { Fragen: { mode: 'always' }, OER: { mode: 'on-demand' } },
    });
  });

  it('keeps the original position so the list does not jump while typing', () => {
    const doc = { a: 1, b: 2, c: 3 };
    expect(Object.keys(renameKeyAt(doc, [], 'b', 'x') as object)).toEqual(['a', 'x', 'c']);
  });

  it('is a no-op when the name is unchanged', () => {
    const doc = { a: 1 };
    expect(renameKeyAt(doc, [], 'a', 'a')).toBe(doc);
  });

  it('refuses to overwrite an existing key', () => {
    const doc = { a: 1, b: 2 };
    expect(renameKeyAt(doc, [], 'a', 'b')).toBe(doc);
  });

  it('is a no-op when the key or the container is missing', () => {
    const doc = { a: 1 };
    expect(renameKeyAt(doc, [], 'nope', 'x')).toBe(doc);
    expect(renameKeyAt(doc, ['nope'], 'a', 'x')).toBe(doc);
  });
});
