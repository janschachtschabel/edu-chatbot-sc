/**
 * Geometrie des Säulendiagramms „Kosten je Tag“ (Paket 16, D2) — rein, ohne DOM, wie
 * `trend-chart.ts` und `loadtest-chart.ts`.
 *
 * Zwei Maße: der Betrag oder die LLM-Aufrufe je Tag. Die Achse reicht bis zum höchsten Tag. Ein
 * Tag ohne Preis hat im Betrag keine Säule (null wäre die Aussage „hat nichts gekostet“); der
 * Hinweis nennt ihn in Worten, und „Aufrufe“ zeigt jeden Tag als gewöhnliche Säule — Ersatzmarken
 * lasen sich in der gestreckten Zeichnung als Strichreihen (Studio-Rundgang 2026-10-18).
 */
import type { UsageDay } from '../core/usage-api.service';

const WIDTH = 600;
const HEIGHT = 120;
const PAD = 8;
/** Anteil der Lücke zwischen zwei Säulen an ihrem Platz. */
const LUECKE = 0.2;

export type CostDayMass = 'betrag' | 'aufrufe';

export interface DayBar {
  readonly tag: string;
  readonly x: number;
  readonly y: number;
  readonly width: number;
  readonly height: number;
  /** Der Wert im gewählten Maß; im Betrag `null` für einen Tag ohne Preis. */
  readonly value: number | null;
}

export interface CostDayChart {
  readonly width: number;
  readonly height: number;
  readonly pad: number;
  readonly bars: readonly DayBar[];
  readonly max: number;
}

export function costDayChart(days: readonly UsageDay[], mass: CostDayMass = 'betrag'): CostDayChart {
  const werte = days.map((d) => {
    if (mass === 'aufrufe') return d.calls;
    return d.amount === null ? null : Number(d.amount);
  });
  const max = Math.max(0, ...werte.map((w) => w ?? 0));
  const platz = (WIDTH - 2 * PAD) / Math.max(1, days.length);
  const breite = platz * (1 - LUECKE);
  const hoehe = HEIGHT - 2 * PAD;
  const bars = days.map((d, i) => {
    const wert = werte[i];
    // Mindestens ein Pixel, sobald etwas da ist — sonst sähe der Tag aus wie einer ohne Nutzung
    // (Review PR #18); den genauen Wert nennt die Tabelle.
    const h = wert === null || max === 0 || wert <= 0 ? 0 : Math.max(1, (wert / max) * hoehe);
    return {
      tag: d.tag,
      x: round(PAD + i * platz + (platz - breite) / 2),
      y: round(HEIGHT - PAD - h),
      width: round(breite),
      height: round(h),
      value: wert,
    };
  });
  return { width: WIDTH, height: HEIGHT, pad: PAD, bars, max };
}

function round(value: number): number {
  return Math.round(value * 100) / 100;
}
