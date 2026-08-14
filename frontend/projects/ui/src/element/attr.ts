/**
 * Web-Component-Attribut-Koerzierung. Custom-Element-Attribute kommen immer als
 * String herein (`emit-guide-suggestion="true"`), im Angular-Consumer aber als
 * echtes `boolean`. `_attrIsTrue` normalisiert beide Formen — leerer String
 * (reines Vorhandensein des Attributs, `<x flag>`) sowie `true`/`1`/`yes` gelten
 * als true.
 *
 * Verbatim aus ALT `chat/chat-text-utils.ts` (kein Standalone-Spec dort).
 * NEU (boerdi-chat): aus 8-5 vorgezogen, weil der host-events-Prereq (8-4S-0a)
 * ihn schon braucht; erster Konsument = host-events, die Element-Definition
 * (8-5) reimportiert ihn von hier.
 */
export function _attrIsTrue(v: boolean | string | undefined): boolean {
  if (v === true) return true;
  if (typeof v === 'string') {
    const s = v.trim().toLowerCase();
    return s === '' || s === 'true' || s === '1' || s === 'yes';
  }
  return false;
}

/**
 * Aufzählungs-Attribut auf einen erlaubten Wert normalisieren (U1/U2/U4:
 * `embed-mode`, `size`, `show-cards`, `theme`).
 *
 * Der Wert stammt aus einer FREMDEN Seite und ist damit ungeprüfte Eingabe: ein
 * Tippfehler darf das Widget nicht in einen undefinierten Zustand bringen,
 * sondern fällt auf `fallback`.
 *
 * Anders als bei `_attrIsTrue` ist der leere String hier KEIN „Attribut
 * vorhanden = an": `<boerdi-chat embed-mode>` sagt nicht, welcher Modus gemeint
 * ist, also gilt die Vorgabe.
 */
export function _attrEnum<T extends string>(
  v: string | undefined, allowed: readonly T[], fallback: T,
): T {
  const s = (v ?? '').trim().toLowerCase();
  return (allowed as readonly string[]).includes(s) ? (s as T) : fallback;
}

/**
 * Gemeinsamer Kopf der JSON-Attribute: trimmen, leer → `null`, Parse-Fehler →
 * eine Zeile in der Konsole und `null`.
 *
 * Die Hülle `{ wert }` statt eines nackten `unknown` hat einen Grund: `null`
 * ist selbst ein gültiger JSON-Wert. Ohne die Hülle ließe sich „kaputt" nicht
 * von „hat wirklich `null` ergeben" unterscheiden, und der Aufrufer meldete den
 * Tippfehler ein zweites Mal.
 */
function _jsonAttr(v: string | undefined): { wert: unknown } | null {
  const s = (v ?? '').trim();
  if (!s) return null;
  try {
    return { wert: JSON.parse(s) };
  } catch (err) {
    console.warn('boerdi: Attribut ist kein gültiges JSON und wird ignoriert', err);
    return null;
  }
}

/**
 * JSON-Objekt-Attribut lesen (`result-schema`, 2026-08-14). `null` heißt „kein
 * brauchbarer Wert" — leer, kaputt, oder kein Objekt.
 *
 * Wie `_attrEnum` behandelt dies den Wert als UNGEPRÜFTE Eingabe einer fremden
 * Seite: ein vergessenes Anführungszeichen darf die Zusatzfunktion kosten, nie
 * den Chat. Deshalb wird der Fehler gefangen — aber nicht verschluckt: die
 * `console.warn`-Zeile ist die einzige Stelle, an der die Gastseite ihren
 * Tippfehler bemerken kann, denn nach außen sieht ein kaputtes Attribut sonst
 * genauso aus wie ein weggelassenes.
 *
 * Arrays und Skalare fallen mit durch: ein JSON-Schema ist ein Objekt, und
 * `[1,2,3]` weiter zu reichen hieße, den Fehler ans Backend zu delegieren.
 */
export function _attrJsonObject(v: string | undefined): Record<string, unknown> | null {
  const gelesen = _jsonAttr(v);
  if (!gelesen) return null;
  const wert = gelesen.wert;
  if (!wert || typeof wert !== 'object' || Array.isArray(wert)) {
    console.warn('boerdi: Attribut ist kein JSON-Objekt und wird ignoriert', wert);
    return null;
  }
  return wert as Record<string, unknown>;
}

/**
 * JSON-Array-Attribut mit Zeichenketten lesen (`start-replies`, 2026-08-14).
 * `null` heißt „nicht gesetzt", `[]` heißt „ausdrücklich keine".
 *
 * Diese Unterscheidung IST der Grund für die Rückgabe `string[] | null`: nur so
 * kann eine Einbettung die Studio-Chips abschalten. Gäbe es sie nicht, führe
 * jedes leere Ergebnis zurück in die Vorgabe, und „keine Chips" wäre nicht
 * sagbar.
 *
 * Warum JSON und nicht komma-getrennt wie `trusted-domains`: die Beschriftungen
 * sind ganze Sätze und enthalten regelmäßig Kommas („Ich suche Inhalte zu einem
 * Thema, bitte"). Eine Trennung am Komma zerschnitte sie still.
 *
 * Einträge werden getrimmt und leer-gefiltert — dieselbe Regel wie im
 * Config-Weg (`parseGuideModeConfig`, C13): ungetrimmte Beschriftungen ließen
 * den Tour-Chip-Vergleich in der Shell fehlschlagen. Nicht-Zeichenketten fallen
 * mit Meldung heraus, statt über `String()` als „[object Object]" auf einer
 * Schaltfläche zu landen.
 */
export function _attrJsonStringArray(v: string | undefined): string[] | null {
  const gelesen = _jsonAttr(v);
  if (!gelesen) return null;
  const wert = gelesen.wert;
  if (!Array.isArray(wert)) {
    console.warn('boerdi: Attribut ist kein JSON-Array und wird ignoriert', wert);
    return null;
  }
  const fremd = wert.filter((e) => typeof e !== 'string');
  if (fremd.length) {
    console.warn('boerdi: Einträge ohne Zeichenkette werden übergangen', fremd);
  }
  return wert
    .filter((e): e is string => typeof e === 'string')
    .map((e) => e.trim())
    .filter(Boolean);
}

/**
 * U2a — die beiden Größenstufen (`size`).
 *
 * Der Typ wohnt HIER und nicht bei `PanelState`, obwohl der Zustand dort liegt:
 * ihn brauchen die Hülle (`widget/`) UND die Eingabezeile (`shell/`), und diese
 * beiden Ordner hatten bisher keine Kante zueinander. Ein Import von `shell/`
 * nach `widget/` zeigte in die falsche Richtung — die Hülle setzt die Shell
 * zusammen, nicht umgekehrt. Beide zeigen aber schon auf `element/`, den
 * neutralen Wohnort des Host-Attribut-Vokabulars.
 */
export type PanelSizeStep = 'small' | 'large';

/** Erlaubte Werte des `size`-Attributs, für `_attrEnum`. */
export const PANEL_SIZE_STEPS = ['small', 'large'] as const;

/** U4a — die drei Werte des `theme`-Attributs. */
export const WIDGET_THEMES = ['auto', 'light', 'dark'] as const;
export type WidgetTheme = (typeof WIDGET_THEMES)[number];

/**
 * U4a — `theme` in einen `color-scheme`-Wert übersetzen; `null` heißt „nichts
 * setzen".
 *
 * Das Widget hatte bis hierher gar keinen eigenen Hell/Dunkel-Schalter: es
 * folgte dem geerbten `color-scheme` der Gastseite, und die
 * `light-dark()`-Aufrufe im Theme sind genau darauf gebaut (gemessen, siehe
 * `widget.component.scss`). Dieses Verhalten IST die Vorgabe — deshalb heißt
 * der Vorgabewert `auto` und ergibt `null`, nicht `'light'`. Ein Vorgabewert
 * `'light'` hätte die Vererbung stillschweigend abgeschaltet und jede
 * dunkle Gastseite hell gemacht.
 *
 * Der Rückgabewert geht als Inline-Stil an das Host-Element; `null` löscht ihn
 * wieder, sodass ein zur Laufzeit auf `auto` zurückgestelltes Attribut die
 * Vererbung wiederherstellt.
 */
export function resolveTheme(v: string | undefined): 'light' | 'dark' | null {
  const t = _attrEnum(v, WIDGET_THEMES, 'auto');
  return t === 'auto' ? null : t;
}
