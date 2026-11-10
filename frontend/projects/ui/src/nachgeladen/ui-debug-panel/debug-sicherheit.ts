/**
 * Abschnitt 6 des Debug-Panels — Safety, Policy, Context, Trace, Tie-Breaker und Token (Paket BU-3;
 * bis dahin das Template von `debug-panel.component.ts`, Zeilen und Texte gleich). Fremdtext steht
 * immer als Text.
 */
import type { DebugInfo } from '../../grouping/message-types';
import { eintraege, el, txt, zahl } from './debug-abschnitte';

type Inhalt = Node | string;
type Frei = Record<string, any>;

const zeile = (label: string, ...inhalt: Inhalt[]) =>
  el('div', 'debug-row', el('span', 'debug-label', label), ' ', ...inhalt);
const sub = (...inhalt: Inhalt[]) => el('div', 'debug-sub', ...inhalt);
const gefuellt = (wert: unknown): wert is unknown[] => Array.isArray(wert) && wert.length > 0;
const zusatz = (text: string) => el('span', '', text);

function safety(s: NonNullable<DebugInfo['safety']>): Node {
  const reihe = zeile('Safety:', `Risk=${txt(s.risk_level)}`);
  if (gefuellt(s.stages_run)) reihe.append(zusatz(` · stages=${s.stages_run.join('→')}`));
  if (s.escalated) reihe.append(zusatz(' · 🤖 escalated'));
  if (gefuellt(s.flagged_categories)) reihe.append(zusatz(` · flagged=${s.flagged_categories.join(',')}`));
  if (gefuellt(s.legal_flags)) reihe.append(zusatz(` · legal=${s.legal_flags.join(',')}`));
  if (s.enforced_pattern) reihe.append(zusatz(` · enforced=${s.enforced_pattern}`));
  if (gefuellt(s.blocked_tools)) reihe.append(zusatz(` · blocked=${s.blocked_tools.join(', ')}`));
  if (gefuellt(s.reasons)) reihe.append(zusatz(` · ${s.reasons.join(', ')}`));
  return reihe;
}

function policy(p: NonNullable<DebugInfo['policy']>): Node {
  const reihe = zeile('Policy:', p.allowed ? 'allowed' : 'BLOCKED');
  if (gefuellt(p.matched_rules)) reihe.append(zusatz(` · rules=${p.matched_rules.join(', ')}`));
  if (gefuellt(p.blocked_tools)) reihe.append(zusatz(` · blocked=${p.blocked_tools.join(', ')}`));
  if (gefuellt(p.required_disclaimers)) reihe.append(zusatz(` · disclaimers=${p.required_disclaimers.length}`));
  return reihe;
}

/** Ein Trace-Eintrag: parallel als Balken mit relativem Versatz und Breite, sonst eine Zeile. */
function traceEintrag(t: Frei): Node {
  const box = el('div', 'debug-trace-entry');
  const daten: Frei = t['data'] ?? {};
  // Kleinigkeit 8 (Review BU-3): ohne Gesamtdauer keine Maße — wie zuvor, als NaN verworfen wurde
  const dauer = Number(t['duration_ms']);
  const gesamt = Number.isFinite(dauer) ? Math.max(dauer, 1) : null;
  if (daten['parallel'] === true && gefuellt(daten['tasks'])) {
    box.append(el('div', 'debug-sub debug-parallel-header', `⟨ ${txt(t['label'] || t['step'])} – Gesamt ${txt(t['duration_ms'])}ms ⟩`));
    const stapel = el('div', 'debug-parallel-stack');
    for (const task of daten['tasks'] as Frei[]) {
      const balken = el('div', 'debug-parallel-task',
        el('span', 'debug-parallel-task__label', String(task['label'] || task['name'] || '')),
        el('span', 'debug-parallel-task__time', `${txt(task['duration_ms'])}ms`));
      if (gesamt !== null) {
        balken.style.marginLeft = `${(task['started_at_ms'] / gesamt) * 100}%`;
        balken.style.width = `${Math.max((task['duration_ms'] / gesamt) * 100, 2)}%`;
      }
      // wie zuvor per Verkettung (das alte Template schrieb hier selbst „undefined“)
      balken.title = `${task['label']} — Start +${task['started_at_ms']}ms · Dauer ${task['duration_ms']}ms`;
      stapel.append(balken);
    }
    box.append(stapel);
  } else {
    box.append(sub(`· [${txt(t['step'])}] ${txt(t['label'])} – ${txt(t['duration_ms'])}ms`));
  }
  return box;
}

function tokens(u: Frei): Node[] {
  const teile: Node[] = [];
  if (u['calls']) {
    const reihe = zeile('Tokens:', `prompt=${txt(u['prompt_tokens'])}, completion=${txt(u['completion_tokens'])}, cached=${txt(u['cached_tokens'])}`);
    if (u['prompt_tokens']) {
      reihe.append(zusatz(` (${zahl(((u['cached_tokens'] || 0) / u['prompt_tokens']) * 100, 0)}% cache) `));
    }
    reihe.append(` · ${txt(u['calls'])} call(s)`);
    teile.push(reihe);
  }
  if (u['per_phase']) {
    teile.push(zeile('Phasen:', ...eintraege(u['per_phase'] as Record<string, Frei>).map((p) => {
      const z = sub(`· ${p.key}: prompt=${txt(p.value['prompt'])}, cached=${txt(p.value['cached'])}`);
      if (p.value['prompt']) z.append(zusatz(` (${zahl(((p.value['cached'] || 0) / p.value['prompt']) * 100, 0)}%)`));
      return z;
    })));
  }
  return teile;
}

export function sicherheit(d: DebugInfo): Node[] {
  const m: Frei = d.phase3_modulations ?? {};
  const teile: Node[] = [el('div', 'debug-section-title', '🛡️ Safety, Policy & Context')];
  if (d.safety) teile.push(safety(d.safety));
  if (gefuellt(d.outcomes)) {
    teile.push(zeile('Outcomes:', ...(d.outcomes as Frei[]).map((o) => {
      const z = sub(`· ${txt(o['tool'])} → ${txt(o['status'])} (${txt(o['item_count'])} items, ${txt(o['latency_ms'])}ms)`);
      if (o['error']) z.append(zusatz(` – ${txt(o['error'])}`));
      return z;
    })));
  }
  if (d.policy) teile.push(policy(d.policy));
  if (d.context) {
    teile.push(zeile('Context:', `page=${txt(d.context.page)}, device=${txt(d.context.device)}, turn=${txt(d.context.turn_count)}`));
  }
  if (gefuellt(d.trace)) teile.push(zeile('Trace:', ...(d.trace as Frei[]).map(traceEintrag)));
  // Pattern-Hint (Shadow-Mode-Telemetrie) — die Vermutung des LLM-Klassifikators
  if (d.pattern_id_hint) {
    const reihe = zeile('LLM-Hint:', d.pattern_id_hint);
    if (d.llm_engine_match === true) reihe.append(el('span', 'debug-ok', ' ✓ Engine-Match'));
    if (d.llm_engine_match === false) reihe.append(el('span', 'debug-warn', ' ≠ Engine'));
    if (d.pattern_reasoning) {
      const grund = el('span', 'debug-sub', ` ${d.pattern_reasoning}`);
      grund.style.display = 'block';
      reihe.append(grund);
    }
    teile.push(reihe);
  }
  const tb: Frei | undefined = m['tie_breaker'];
  if (tb) {
    teile.push(zeile('Tie-Breaker:', tb['applied']
      ? zusatz(`⚡ ${txt(tb['from'])} → ${txt(tb['to'])} (gap=${txt(tb['score_gap'])})`)
      : zusatz(` evaluiert (gap=${txt(tb['score_gap'])}, applied=false) `)));
  }
  if (d.token_usage) teile.push(...tokens(d.token_usage as Frei));
  return teile;
}
