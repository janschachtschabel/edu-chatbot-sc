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
