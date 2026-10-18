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
import { pickFields } from './pick-fields';
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
  /** Rundgang 3: die Beschriftung einer Feldgruppe (Katalog-Schlüssel). */
  readonly labelKey?: string;
}

/** Rundgang 3: eine benannte Feldgruppe — Feldpfade, punktgetrennt, wie `felder`. */
export interface FeldGruppe {
  readonly id: string;
  readonly labelKey: string;
  readonly felder: readonly string[];
}

/** Feldarten ohne eigenen Abschnitt. Seit Paket 15 auch Textflächen: auf „Tour & Lotse“
 *  stand jeder Text in einem eigenen Aufklapper (Nutzer-Rundgang 2026-10-17). */
const COMPACT: ReadonlySet<FieldKind> = new Set<FieldKind>([
  'text', 'select', 'number', 'integer', 'boolean', 'multiline',
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
    // Paket 15: ein Marker-Ziel zeigt sich nicht selbst — es darf keinen leeren Abschnitt füllen.
    if (child.markerZiel) continue;
    if (child.primary) content.push(child.key);
    else (COMPACT.has(child.kind) ? basics : blocks).push(child.key);
  }
  if (content.length + blocks.length < MIN_SECTIONS) return [];

  const cut = (key: string) => ({ id: `sec-${key}`, key, keys: [key] });
  const cuts = [
    ...content.map(cut),
    ...(basics.length > 0 ? [{ id: BASICS_ID, key: '', keys: basics }] : []),
    ...blocks.map(cut),
  ];

  return cuts.map(({ id, key, keys }) => {
    const paths = keys.map((k) => [...basePath, k].join('.'));
    const block = key ? scope.children?.find((c) => c.key === key) : undefined;
    // Paket 15: ein Block-Abschnitt rendert den Block selbst, ohne Legende — die
    // Zusammenfassung des Aufklappers nennt ihn schon; vorher stand der Name doppelt.
    if (block?.kind === 'group') {
      return { id, key, paths, basePath: [...basePath, key], field: { ...block, ohneLegende: true } };
    }
    return { id, key, basePath, paths, field: sectionRoot(scope, new Set(keys)) };
  });
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

/**
 * Rundgang 3: Abschnitte nach benannten Feldgruppen statt nach der Form des Dokuments —
 * für Seiten, auf denen die Form nicht zur Arbeit passt (Tour in Laufzeit-Reihenfolge,
 * Kontext-Aktionen nach Sprache). EIN Editor, ein Speichern; nur die Ansicht ist gegliedert.
 *
 * Jede Gruppe zeigt den auf ihre Pfade gekürzten Baum; eine einzelne Hülle wird aufgelöst wie
 * beim Block-Abschnitt (keine zweite Legende). Was keine Gruppe nennt, steht in „Weitere
 * Einstellungen“ — ein neues Feld im Modell geht so nicht verloren.
 */
export function gruppenSections(
  root: SchemaField, gruppen: readonly FeldGruppe[],
): readonly FormSection[] {
  const sections = gruppen.map((gruppe): FormSection => {
    const gekuerzt = pickFields(root, new Set(gruppe.felder));
    const [huelle, ...weitere] = gekuerzt.children ?? [];
    const base = { id: `grp-${gruppe.id}`, key: '', paths: gruppe.felder, labelKey: gruppe.labelKey };
    return huelle?.kind === 'group' && weitere.length === 0
      ? { ...base, basePath: [huelle.key], field: { ...huelle, ohneLegende: true } }
      : { ...base, basePath: [], field: { ...gekuerzt, key: '', label: '', textKey: undefined } };
  });

  const scope = sectionScope(root);
  const basePath = scope === root ? [] : [scope.key];
  const rest = restPfade(scope, basePath, gruppen.flatMap((g) => g.felder));
  if (rest.length === 0) return sections;
  return [...sections, {
    id: 'grp-rest', key: '', labelKey: 'schemaForm.weitere', basePath, paths: rest,
    field: { ...teilbaum(scope, basePath, new Set(rest)), key: '', label: '', textKey: undefined },
  }];
}

/**
 * Was keine Gruppe nennt — auf Blatt-Ebene (Review A-3): ein ganz ungenannter Zweig als
 * Ganzes, ein teilweise genannter wird durchsucht. Vorher galt ein Block als erledigt, sobald
 * eine Gruppe eines seiner Felder nannte; seine übrigen Felder verschwanden still.
 */
function restPfade(feld: SchemaField, pfad: readonly string[], genannt: readonly string[]): string[] {
  return (feld.children ?? []).flatMap((child) => {
    if (child.markerZiel) return [];
    const weg = [...pfad, child.key];
    const p = weg.join('.');
    if (genannt.some((f) => p === f || p.startsWith(`${f}.`))) return [];
    if (!genannt.some((f) => f.startsWith(`${p}.`))) return [p];
    return child.kind === 'group' ? restPfade(child, weg, genannt) : [];
  });
}

/** Der Baum, beschnitten auf `pfade` (beliebig tief) — die Reihenfolge bleibt die des Schemas. */
function teilbaum(
  feld: SchemaField, pfad: readonly string[], pfade: ReadonlySet<string>,
): SchemaField {
  const children = (feld.children ?? []).flatMap((child) => {
    const weg = [...pfad, child.key];
    const p = weg.join('.');
    if (pfade.has(p)) return [child];
    if (child.kind !== 'group' || ![...pfade].some((x) => x.startsWith(`${p}.`))) return [];
    return [{ ...teilbaum(child, weg, pfade), label: '', textKey: undefined }];
  });
  return { ...feld, children };
}
