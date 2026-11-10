/**
 * Die sechs Abschnitte des Debug-Panels als DOM (Paket BU-3; bis dahin das Template von
 * `debug-panel.component.ts`, ALT-Port `chat.component.html:422-607` — Zeilen und Texte gleich).
 * Fremdtext (alles aus dem Debug-Block) steht immer als Text, nie als HTML.
 */
import type { DebugInfo } from '../../grouping/message-types';

type Inhalt = Node | string;
// Der Debug-Block ist ein loses Diagnose-Objekt (ALT-Port) — die Modulationen sind frei geformt.
type Frei = Record<string, any>;

export function el<K extends keyof HTMLElementTagNameMap>(tag: K, klasse = '', ...inhalt: Inhalt[]): HTMLElementTagNameMap[K] {
  const e = document.createElement(tag);
  if (klasse) e.className = klasse;
  e.append(...inhalt);
  return e;
}

/** Wie Angulars Interpolation: `null` und `undefined` werden zu leerem Text, nie zu „undefined“
 *  (Review BU-3, Befund 1 — etwa `phase3_modulations: {}` bei Tour, Begrüßung, Fehlerpfaden). */
export const txt = (wert: unknown): string => (wert == null ? '' : String(wert));

const titel = (text: string) => el('div', 'debug-section-title', text);
const zeile = (label: string, ...inhalt: Inhalt[]) =>
  el('div', 'debug-row', el('span', 'debug-label', label), ' ', ...inhalt);
const liste = (wert: unknown): unknown[] => (Array.isArray(wert) ? wert : []);
const gefuellt = (wert: unknown): wert is unknown[] => Array.isArray(wert) && wert.length > 0;

/** Wie Angulars ``DecimalPipe`` (en-US, ``1.<min>-<stellen>``): gerundet wird auf den
 *  Dezimalziffern (0.825 → 0.83 — ``Intl`` allein rundete den Binärwert auf 0.82), dann mit
 *  Tausendertrennern und festen Stellen. Kein Wert → leer. */
export function zahl(wert: unknown, stellen: number, min = stellen): string {
  if (typeof wert !== 'number' && typeof wert !== 'string') return '';
  const n = Number(wert);
  if (wert === '' || !Number.isFinite(n)) return '';
  const verschoben = Number(`${Math.abs(n)}e${stellen}`);
  const gerundet = Number.isFinite(verschoben)
    ? Math.sign(n) * Number(`${Math.round(verschoben)}e-${stellen}`)
    : n;
  // `|| 0`: was auf Null rundet, trägt wie bei DecimalPipe kein Minus („-0.00“).
  return (gerundet || 0).toLocaleString('en-US', { minimumFractionDigits: min, maximumFractionDigits: stellen });
}

/** Wie Angulars ``KeyValuePipe``: die Einträge nach Schlüssel sortiert. */
export function eintraege<T>(o: Readonly<Record<string, T>> | null | undefined): { key: string; value: T }[] {
  return o ? Object.keys(o).sort().map((key) => ({ key, value: o[key] })) : [];
}

function gekuerzt(text: string, laenge: number): string {
  return text.slice(0, laenge) + (text.length > laenge ? '…' : '');
}

export function gespraechsPhase(d: DebugInfo): Node[] {
  const teile: Node[] = [titel('🌀 Gesprächs-Phase'), zeile('State:', d.state || '–')];
  const t = d.state_transition;
  if (t) {
    const reihe = zeile('Übergang:', el('span', t.plausible === false ? 'debug-warn' : '', `${t.prev || '(start)'} → ${txt(t.next)}`));
    if (t.plausible === false) {
      reihe.append(' ', el('span', 'debug-warn', `⚠ implausibel · erwartet: ${liste(t.expected_next_likely).join(', ')}`));
    }
    if (t.plausible === true) reihe.append(' ', el('span', 'debug-ok', '✓ plausibel'));
    teile.push(reihe);
  }
  teile.push(zeile('Turn-Typ:', d.turn_type || '–'));
  return teile;
}

export function klassifikation(d: DebugInfo): Node[] {
  const teile: Node[] = [
    titel('🎯 Klassifikation'),
    zeile('Persona:', String(d.persona ?? '')),
    zeile('Intent:', String(d.intent ?? '')),
    zeile('Signale:', liste(d.signals).join(', ') || '–'),
    zeile('Entities:', el('code', '', JSON.stringify(d.entities, null, 2) ?? '')),
  ];
  if (d.confidence !== undefined) teile.push(zeile('Confidence:', zahl(d.confidence || 0, 2)));
  return teile;
}

export function patternEngine(d: DebugInfo): Node[] {
  const m: Frei = d.phase3_modulations ?? {};
  const teile: Node[] = [titel('🧩 Pattern-Engine'), zeile('Pattern:', String(d.pattern ?? ''))];
  if (d.pattern_id_hint) {
    const reihe = zeile('LLM-Hint:', d.pattern_id_hint);
    if (d.llm_engine_match === true) reihe.append(' ', el('span', 'debug-ok', '✓ stimmt mit Engine überein'));
    if (d.llm_engine_match === false) reihe.append(' ', el('span', 'debug-warn', '⚠ weicht von Engine ab'));
    teile.push(reihe);
  }
  if (d.pattern_reasoning) teile.push(zeile('Reasoning:', gekuerzt(d.pattern_reasoning, 160)));
  if (gefuellt(d.phase1_eliminated)) teile.push(zeile('Phase 1 eliminiert:', d.phase1_eliminated.join(', ')));
  if (d.phase2_scores) {
    teile.push(zeile('Phase 2 Scores:', ...eintraege(d.phase2_scores)
      .map((e) => el('span', 'debug-score', ` ${e.key}=${zahl(e.value, 2)} `))));
  }
  if (m['degradation']) {
    const reihe = zeile('Degradation:', el('span', 'debug-warn', '⚠'),
      ` fehlende Slots=${liste(m['missing_slots']).join(', ') || '–'}`);
    if (gefuellt(m['blocked_patterns'])) reihe.append(el('span', '', ` · blockiert=${m['blocked_patterns'].length} Patterns`));
    teile.push(reihe);
  }
  return teile;
}

export function modulation(d: DebugInfo): Node[] {
  const m: Frei = d.phase3_modulations ?? {};
  const form = zeile('Ton/Form:', `Ton=${txt(m['tone'])}, Formalität=${txt(m['formality'])}, Länge=${txt(m['length'])}, Detail=${txt(m['detail_level'])}`);
  for (const k of ['skip_intro', 'one_option', 'add_sources']) if (m[k]) form.append(el('span', '', ` · ${k}`));
  const teile: Node[] = [
    titel('🎨 Modulation'),
    form,
    zeile('Response:', `Typ=${txt(m['response_type'])}, Format=${txt(m['format_primary'])}, `
      + `Follow-up=${txt(m['format_follow_up'])}, Kacheln=${txt(m['card_text_mode'])}, Max=${txt(m['max_items'])}`),
  ];
  if (m['core_rule']) teile.push(zeile('Core-Rule:', gekuerzt(String(m['core_rule']), 120)));
  return teile;
}

export function toolsUndWissen(d: DebugInfo): Node[] {
  const m: Frei = d.phase3_modulations ?? {};
  const teile: Node[] = [titel('🔧 Tools & Wissen'), zeile('Tools aufgerufen:', liste(d.tools_called).join(', ') || '–')];
  if (gefuellt(m['tools'])) teile.push(zeile('Pattern-Tools (erlaubt):', m['tools'].join(', ')));
  teile.push(zeile('Quellen:', liste(m['sources']).join(', ') || '–'));
  if (gefuellt(m['rag_areas'])) teile.push(zeile('RAG-Areas:', m['rag_areas'].join(', ')));
  return teile;
}
