/**
 * AS-0: der Zusatz einer Zeile in der Liste der Abläufe — Kennung, an/aus, Auslöser und was „Prüfen“
 * fände. Text statt Farbe (WCAG 1.4.1): ein ausgeschalteter oder fehlerhafter Ablauf steht so auch
 * vorgelesen und in Schwarzweiß fest.
 */
import type { AblaufZeile } from '../core/ablauf-api.service';

type T = (key: string, params?: Record<string, string | number>) => string;
type Plural = (key: string, count: number, params?: Record<string, string | number>) => string;

const AUSLOESER = ['knopf', 'text', 'agent', 'modul', 'extern', 'seite'] as const;

export function ablaufNotiz(zeile: AblaufZeile, t: T, plural: Plural): string {
  if (!zeile.lesbar) return `${zeile.id} · ${t('ablaeufe.notiz.unlesbar')}`;
  const teile = [zeile.id, t(zeile.aktiv ? 'ablaeufe.notiz.an' : 'ablaeufe.notiz.aus')];
  const arten = zeile.ausloeser.map((art) =>
    (AUSLOESER as readonly string[]).includes(art) ? t(`ablaeufe.ausloeser.${art}`) : art);
  if (arten.length) teile.push(arten.join(', '));
  // Review AS-0, Befund 8: welche Module der Ablauf zeigt — für den Weg von einem Modul zu seinen
  // Abläufen (die Suche der Liste findet sie).
  if (zeile.module.length) teile.push(t('ablaeufe.notiz.module', { module: zeile.module.join(', ') }));
  if (zeile.befunde) teile.push(plural('ablaeufe.notiz.befunde', zeile.befunde));
  return teile.join(' · ');
}
