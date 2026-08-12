import { describe, expect, it } from 'vitest';

import { STUDIO_DE } from '../i18n/de';
import { STUDIO_EN } from '../i18n/en';
import { PREVIEW_CONTEXT_KINDS, buildPreviewContext } from './preview-embed';

describe('PREVIEW_CONTEXT_KINDS', () => {
  it('bietet genau die Seitentypen an, auf die das Backend proaktiv reagiert', () => {
    // Gemessen, nicht gewählt: `_GREETABLE_KINDS = ("collection", "content",
    // "topic")` in graph/nodes/context_greeting.py:47. Für `subject` und
    // `search` gibt es Prompt-Text, aber weder Begrüßung noch Pills — sie hier
    // anzubieten würde eine Wirkung versprechen, die ausbleibt.
    expect(PREVIEW_CONTEXT_KINDS.map((k) => k.id)).toEqual([
      'kein', 'topic', 'collection', 'content',
    ]);
  });

  it('nennt zu jedem Seitentyp das Feld, das der Detektor mitschickt', () => {
    // Schlüsselpaare aus ui/src/page-context/page-context-detector.ts:79/101/110.
    expect(PREVIEW_CONTEXT_KINDS.map((k) => k.field)).toEqual([
      '', 'topic_page_slug', 'collection_id', 'node_id',
    ]);
  });

  it('nennt zu jedem Seitentyp Katalog-Schlüssel, die es wirklich gibt', () => {
    // Die Beschriftungen kommen seit C1-d3b aus dem Katalog. Ein Tippfehler im
    // Schlüssel bliebe sonst still: `t()` gibt den Schlüssel selbst aus, und im
    // Auswahlfeld stünde dann „preview.kind.topik".
    const schluessel = PREVIEW_CONTEXT_KINDS
      .flatMap((k) => [k.labelKey, k.fieldLabelKey])
      .filter(Boolean);
    for (const key of schluessel) {
      expect(STUDIO_DE[key], `fehlt im deutschen Katalog: ${key}`).toBeTypeOf('string');
      expect(STUDIO_EN[key], `fehlt im englischen Katalog: ${key}`).toBeTypeOf('string');
    }
  });
});

describe('buildPreviewContext', () => {
  it('baut den Themenseiten-Kontext wie der Detektor auf einer echten Seite', () => {
    expect(buildPreviewContext('topic', 'eiszeit')).toEqual({
      page_kind: 'topic',
      topic_page_slug: 'eiszeit',
      detection_source: 'studio:vorschau',
    });
  });

  it('legt Sammlung und Inhaltsseite auf ihre eigenen Schlüssel', () => {
    expect(buildPreviewContext('collection', 'abc-123')).toEqual({
      page_kind: 'collection',
      collection_id: 'abc-123',
      detection_source: 'studio:vorschau',
    });
    expect(buildPreviewContext('content', 'abc-123')).toEqual({
      page_kind: 'content',
      node_id: 'abc-123',
      detection_source: 'studio:vorschau',
    });
  });

  it('schickt ohne Wert gar keinen Kontext statt eines halben', () => {
    // `page_kind` ohne ID/Slug lässt das Backend nichts auflösen: die Begrüßung
    // bliebe aus und die Vorschau sähe aus, als sei die Konfiguration kaputt.
    expect(buildPreviewContext('topic', '')).toBeNull();
    expect(buildPreviewContext('topic', '   ')).toBeNull();
  });

  it('trimmt den Wert, weil kopierte IDs Leerzeichen mitbringen', () => {
    expect(buildPreviewContext('content', '  abc-123 ')).toEqual({
      page_kind: 'content',
      node_id: 'abc-123',
      detection_source: 'studio:vorschau',
    });
  });

  it('liefert für „kein Kontext" und für einen unbekannten Typ null', () => {
    expect(buildPreviewContext('kein', 'eiszeit')).toBeNull();
    expect(buildPreviewContext('erfunden', 'eiszeit')).toBeNull();
  });
});
