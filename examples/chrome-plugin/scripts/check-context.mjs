/**
 * Prüfung für `context.js` — die einzige Stelle im Plugin mit echter Logik.
 *
 * Kein Test-Rahmenwerk: der Ordner hat bewusst keinen Build und keine
 * Abhängigkeiten. `node scripts/check-context.mjs` genügt, und ein Beispiel,
 * das sein eigenes package.json mitbrächte, wäre kein Beispiel mehr.
 *
 *     node scripts/check-context.mjs
 */
import { ausUrl, baueKontext } from '../context.js';

let geprueft = 0;
const fehler = [];

function gleich(was, ist, soll) {
  geprueft++;
  const a = JSON.stringify(ist);
  const b = JSON.stringify(soll);
  if (a !== b) fehler.push(`${was}\n    ist:  ${a}\n    soll: ${b}`);
}

// ── ausUrl: was die Adresse allein hergibt ─────────────────────────

gleich('Sammlung im Pfad',
  ausUrl('https://wirlernenonline.de/sammlung/abc-123'),
  { page_kind: 'collection', collection_id: 'abc-123' });

gleich('Material im Pfad',
  ausUrl('https://wirlernenonline.de/material/xyz-9'),
  { page_kind: 'content', node_id: 'xyz-9' });

gleich('edu-sharing-Render-Adresse',
  ausUrl('https://repo.test/edu-sharing/components/render/a1b2c3d4e5'),
  { page_kind: 'content', node_id: 'a1b2c3d4e5' });

gleich('Themenseite',
  ausUrl('https://wirlernenonline.de/themenseite/optik'),
  { page_kind: 'topic', topic_page_slug: 'optik' });

gleich('Fachportal ohne Themenseite',
  ausUrl('https://wirlernenonline.de/fachportal/physik'),
  { page_kind: 'topic', subject_slug: 'physik' });

gleich('Fachportal mit Themenseite',
  ausUrl('https://wirlernenonline.de/fachportal/physik/optik'),
  { page_kind: 'topic', subject_slug: 'physik', topic_page_slug: 'optik' });

gleich('Suchbegriff aus ?q=',
  ausUrl('https://wirlernenonline.de/suche?q=br%C3%BCche'),
  { page_kind: 'search', search_query: 'brüche' });

// Der Grund, aus dem im Widget dieselbe Regel steht (Befund 2026-08-14): in der
// Seitenleiste ist die eigene Adresse `chrome-extension://<id>` — daraus einen
// „Host" zu machen erzeugte den Satz „das gehört nicht zu WLO".
gleich('eigene Erweiterungs-Adresse trägt NICHTS bei',
  ausUrl('chrome-extension://dcchajcmmghejkhjmllhnmaggocmmjck/panel.html'), {});
gleich('about:blank trägt nichts bei', ausUrl('about:blank'), {});
gleich('leere Adresse trägt nichts bei', ausUrl(''), {});
gleich('kaputte Adresse wirft nicht', ausUrl('http://['), {});

gleich('Anfrage-Parameter schlagen den Pfad',
  ausUrl('https://wirlernenonline.de/sammlung/aus-dem-pfad?collection=aus-der-anfrage'),
  { page_kind: 'collection', collection_id: 'aus-der-anfrage' });

// ── baueKontext: die drei Betriebsarten der Steuerleiste ───────────

gleich('aus: gar kein Kontext, auch wenn der Tab etwas hergäbe',
  baueKontext({ modus: 'aus', tabUrl: 'https://wirlernenonline.de/sammlung/abc' }),
  {});

gleich('auto: Tab-Adresse plus Titel',
  baueKontext({
    modus: 'auto',
    tabUrl: 'https://wirlernenonline.de/sammlung/abc',
    tabTitel: 'Optik',
  }),
  { page_kind: 'collection', collection_id: 'abc', document_title: 'Optik' });

gleich('auto mit Seitentext',
  baueKontext({
    modus: 'auto',
    tabUrl: 'https://wirlernenonline.de/sammlung/abc',
    seitentext: 'Licht und Schatten',
  }),
  { page_kind: 'collection', collection_id: 'abc', page_text: 'Licht und Schatten' });

gleich('manuell: nur die getippten Felder, der Tab bleibt außen vor',
  baueKontext({
    modus: 'manuell', art: 'collection', collectionId: 'manuell-1',
    tabUrl: 'https://wirlernenonline.de/sammlung/aus-dem-tab',
  }),
  { page_kind: 'collection', collection_id: 'manuell-1' });

gleich('manuell: leere Felder fallen weg statt als "" mitzureisen',
  baueKontext({ modus: 'manuell', art: 'collection', collectionId: '  ', nodeId: '' }),
  { page_kind: 'collection' });

gleich('manuell: Einzelinhalt',
  baueKontext({ modus: 'manuell', art: 'content', nodeId: 'n-7' }),
  { page_kind: 'content', node_id: 'n-7' });

gleich('manuell: Suche',
  baueKontext({ modus: 'manuell', art: 'search', suche: 'brüche' }),
  { page_kind: 'search', search_query: 'brüche' });

gleich('manuell: Themenseite',
  baueKontext({ modus: 'manuell', art: 'topic', topicSlug: 'optik' }),
  { page_kind: 'topic', topic_page_slug: 'optik' });

gleich('manuell: Art "none" gibt einen leeren Kontext',
  baueKontext({ modus: 'manuell', art: 'none', collectionId: 'wird-ignoriert' }),
  {});

// Der Seitentext gilt in BEIDEN Betriebsarten — er beschreibt, was zu sehen
// ist, nicht woher der Kontext kommt.
gleich('manuell mit Seitentext',
  baueKontext({ modus: 'manuell', art: 'content', nodeId: 'n-7', seitentext: 'Text' }),
  { page_kind: 'content', node_id: 'n-7', page_text: 'Text' });

// ── Ausgabe ────────────────────────────────────────────────────────

if (fehler.length) {
  console.error(`\n  ${fehler.length} von ${geprueft} Prüfungen fehlgeschlagen:\n`);
  for (const f of fehler) console.error(`  ✗ ${f}\n`);
  process.exit(1);
}
console.log(`  ${geprueft} Prüfungen bestanden.`);
