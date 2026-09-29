/**
 * Ein Bereichs-Formular in aufklappbare Abschnitte schneiden (S5).
 *
 * Anlass (Nutzer, 2026-08-13): „sehr lange formulare". Muster haben seit A7b
 * fünf Reiter aus einer handgeschriebenen Tabelle; die übrigen 33 Bereiche
 * rendern ein einziges Fieldset — `01-base/safety-config` mit elf Blöcken.
 *
 * Hier steht bewusst KEINE Tabelle je Bereich: der Schnitt folgt der Form des
 * Dokuments. Ein neues Feld im Modell erscheint damit von selbst am richtigen
 * Platz, statt bis zur nächsten Tabellenpflege im Auffangkorb zu liegen.
 *
 * Aufklappbar und nicht Reiter (Nutzer-Entscheid). Der Unterschied ist nicht
 * bloss optisch: der Reiter-Schnitt rendert nur den aktiven Reiter, die übrigen
 * Felder sind gar nicht im Dokument. Ein zugeklapptes `<details>` ist da —
 * aktuelle Chrome- und Firefox-Fassungen klappen es bei der Seitensuche sogar
 * selbst auf. Und der Schnitt braucht keine Tabelle je Bereich.
 */
import type { FieldKind, SchemaField } from './schema-to-fields';

export interface FormSection {
  /** Stabil über Neuzeichnungen — Grundlage von `track`. */
  readonly id: string;
  /** Der Config-Schlüssel. Leer beim Sammel-Abschnitt; die Ansicht setzt dort
   *  ihre eigene Beschriftung ein, weil es keinen Schlüssel gibt zu zeigen. */
  readonly key: string;
  /** Die Dokument-Pfade dieses Abschnitts, absolut und punktgetrennt. */
  readonly paths: readonly string[];
  /** Wo `field` im Dokument sitzt — leer, oder der Schlüssel der Hülle. */
  readonly basePath: readonly string[];
  /** Der Teilbaum, den die Ansicht rendert (relativ zu `basePath`). */
  readonly field: SchemaField;
}

/** Feldarten, die in eine Zeile passen — sie bekommen keinen eigenen Abschnitt. */
const COMPACT: ReadonlySet<FieldKind> = new Set<FieldKind>([
  'text', 'select', 'number', 'integer', 'boolean',
]);

/** Unter zwei Abschnitten lohnt der Aufwand nicht: ein einziges Aufklapp-Element
 *  um das ganze Formular ist nur ein Klick mehr. */
const MIN_SECTIONS = 2;

/** Die Kennung des Sammel-Abschnitts. Ohne Schlüssel-Anhang, damit ein Feld,
 *  das zufällig `basics` heisst, nicht dieselbe `track`-Kennung bekommt. */
const BASICS_ID = 'sec';

/**
 * Die Abschnitte dieses Formulars, oder `[]` wenn nicht gegliedert werden soll.
 *
 * Reihenfolge ist die des Schemas — mit **zwei** bewussten Ausnahmen: die
 * einfachen Felder werden zu einem Sammel-Abschnitt zusammengezogen, auch wenn
 * sie im Schema verstreut stehen. Sie einzeln aufzuklappen wäre absurd, und zwei
 * gleich benannte Sammel-Abschnitte wären verwirrend. Dieselbe Freiheit nimmt
 * sich der Reiter-Schnitt in `pattern-field-tabs.ts`. Und seit ST-4 stehen
 * Blöcke, die das Modell als Inhalt markiert (`x-primary`: Begrüßungstext,
 * Regeltext), VOR diesem Sammel-Abschnitt — offen ist der erste, und das soll
 * der Inhalt sein, nicht die Technik.
 */
export function formSections(root: SchemaField): readonly FormSection[] {
  const scope = sectionScope(root);
  const basePath = scope === root ? [] : [scope.key];

  const basics: string[] = [];
  const content: string[] = [];
  const blocks: string[] = [];
  for (const child of scope.children ?? []) {
    if (COMPACT.has(child.kind)) basics.push(child.key);
    else (child.primary ? content : blocks).push(child.key);
  }
  if (content.length + blocks.length < MIN_SECTIONS) return [];

  const cut = (key: string) => ({ id: `sec-${key}`, key, keys: [key] });
  const cuts = [
    ...content.map(cut),
    ...(basics.length > 0 ? [{ id: BASICS_ID, key: '', keys: basics }] : []),
    ...blocks.map(cut),
  ];

  return cuts.map(({ id, key, keys }) => ({
    id,
    key,
    basePath,
    paths: keys.map((k) => [...basePath, k].join('.')),
    field: sectionRoot(scope, new Set(keys)),
  }));
}

/**
 * Auf welcher Ebene geschnitten wird: normalerweise die Wurzel, bei einer
 * einzelnen Hülle diese Hülle.
 *
 * Die meisten Bereiche packen alles in einen Block (`display_rules:`,
 * `context_actions:`, `welcome:` — 16 von 34). Auf der Wurzel entstünde dort
 * genau ein Abschnitt — die Wand bliebe, nur mit einem Klick davor.
 */
function sectionScope(root: SchemaField): SchemaField {
  const children = root.children ?? [];
  const [only] = children;
  const istHuelle = children.length === 1
    && only.kind === 'group'
    && (only.children?.length ?? 0) > 0;
  return istHuelle ? only : root;
}

/**
 * Der Rumpf eines Abschnitts: der Geltungsbereich auf seine Felder reduziert
 * und **ohne eigene Beschriftung**.
 *
 * Ohne das Streichen stünde über jedem Abschnitt der Name der Hülle — sechsmal
 * derselbe, dazu eine Einrückung, die nichts gliedert. Die Zusammenfassung des
 * Aufklapp-Elements ist die Überschrift; der Geltungsbereich selbst hat im
 * Abschnitt keine mehr. Dass er trotzdem im Baum bleibt, ist Absicht: die
 * Ansicht setzt ihn als `basePath` ein, damit die Felder unter ihm landen.
 */
function sectionRoot(scope: SchemaField, keys: ReadonlySet<string>): SchemaField {
  const children = (scope.children ?? []).filter((child) => keys.has(child.key));
  // Auch der Katalog-Schlüssel (ST-1) fällt weg: an ihm holte sich das Feld
  // seine Beschriftung sonst aus dem Katalog zurück.
  return { ...scope, key: '', label: '', textKey: undefined, children };
}
