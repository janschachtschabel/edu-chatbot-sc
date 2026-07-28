import { describe, expect, it } from 'vitest';

import { fieldPaths, pickFields } from './pick-fields';
import type { SchemaField } from './schema-to-fields';

function leaf(key: string): SchemaField {
  return { key, label: key, kind: 'text', required: false, nullable: false, blank: '' };
}

const ROOT: SchemaField = {
  key: '', label: '', kind: 'group', required: false, nullable: false, blank: {},
  children: [
    {
      key: 'frontmatter', label: 'frontmatter', kind: 'group', required: false,
      nullable: false, blank: {},
      children: [leaf('id'), leaf('label'), leaf('tools')],
    },
    leaf('body'),
  ],
};

describe('pickFields', () => {
  it('behält ein Wurzel-Feld ganz, wenn sein Pfad genannt ist', () => {
    const picked = pickFields(ROOT, new Set(['body']));
    expect(picked.children?.map((c) => c.key)).toEqual(['body']);
  });

  it('behält aus einer Gruppe nur die genannten Kinder — in Schema-Reihenfolge', () => {
    // Die Reihenfolge kommt aus dem Schema, nicht aus der Pfadliste: das
    // Formular soll überall gleich gelesen werden.
    const picked = pickFields(ROOT, new Set(['frontmatter.tools', 'frontmatter.id']));
    const group = picked.children?.[0];
    expect(group?.key).toBe('frontmatter');
    expect(group?.children?.map((c) => c.key)).toEqual(['id', 'tools']);
  });

  it('nimmt eine ganze Gruppe, wenn die Gruppe selbst genannt ist', () => {
    const picked = pickFields(ROOT, new Set(['frontmatter']));
    expect(picked.children?.[0].children?.map((c) => c.key)).toEqual(['id', 'label', 'tools']);
  });

  it('lässt Felder weg, die nicht genannt sind', () => {
    const picked = pickFields(ROOT, new Set(['frontmatter.id']));
    expect(picked.children?.map((c) => c.key)).toEqual(['frontmatter']);
    expect(picked.children?.[0].children?.map((c) => c.key)).toEqual(['id']);
  });

  it('ignoriert einen Pfad, den es im Schema nicht gibt', () => {
    // Eine veraltete Tab-Tabelle darf das Formular nicht kaputt machen.
    const picked = pickFields(ROOT, new Set(['frontmatter.gibtsnicht', 'body']));
    expect(picked.children?.map((c) => c.key)).toEqual(['body']);
  });

  it('liefert eine leere Wurzel, wenn nichts genannt ist', () => {
    expect(pickFields(ROOT, new Set()).children).toEqual([]);
  });

  it('rührt die Wurzel-Kennzeichen nicht an', () => {
    const picked = pickFields(ROOT, new Set(['body']));
    expect(picked.kind).toBe('group');
    expect(picked.key).toBe('');
  });
});

describe('fieldPaths', () => {
  it('nennt jedes Feld, das ein Tab aufnehmen kann — Gruppenkinder statt Gruppe', () => {
    // Grundlage der Vollständigkeits-Prüfung der Tab-Tabelle.
    expect(fieldPaths(ROOT)).toEqual([
      'frontmatter.id', 'frontmatter.label', 'frontmatter.tools', 'body',
    ]);
  });

  it('nennt eine Liste als ein Feld, nicht ihre Einträge', () => {
    const withList: SchemaField = {
      ...ROOT,
      children: [
        { key: 'items', label: 'items', kind: 'list', required: false, nullable: false, blank: [], item: leaf('') },
      ],
    };
    expect(fieldPaths(withList)).toEqual(['items']);
  });
});
