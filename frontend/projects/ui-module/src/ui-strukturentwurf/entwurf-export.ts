/**
 * Herunterladen des Strukturentwurfs (Paket U2-e, Plan 2026-11-04 T-12) — ohne Angular.
 *
 * JSON im Dokumenttyp `wlo.sammlungsstruktur@1` (Konzept §6.3; die Felder `vokabular`, `typ`,
 * `konfidenz`, `fuellstand` fehlen noch, siehe Plan „Offen“) und Markdown als
 * eingerückte Liste mit Beschreibung und Schlagworten. Die Übergabe an andere Dienste (Kestra,
 * B-API) bleibt offen; bis dahin ist die Datei die Übergabe.
 */
import type { Baum, EntwurfInhalt } from './entwurf-regeln';

export interface EntwurfDaten {
  readonly titel: string;
  readonly quelle: 'ki' | 'wlo' | 'ordner' | 'dokument';
  readonly thema?: string;
  readonly fach?: string;
  readonly bildungsstufe?: string;
  readonly wurzel_wlo_id?: string;
  readonly gekuerzt?: boolean;
  /** Nachprüfung TG-3d–f, MINOR 2: die block_id der Auswahl (`quelle: ordner`). */
  readonly quelle_block?: string;
  readonly knoten: Baum;
  /** Paket N3: Inhalte aus Materialien, die keinem Punkt zugeordnet sind. */
  readonly nicht_zugeordnet?: readonly EntwurfInhalt[];
}

export const DOKUMENTTYP = 'wlo.sammlungsstruktur@1';

export function alsJson(daten: EntwurfDaten): string {
  // Paket N3: die Verweise (`inhalte` je Punkt mit node_id, `nicht_zugeordnet`) reisen mit — so
  // sind die Inhalte in edu-sharing wiederzufinden
  const { titel, quelle, thema, fach, bildungsstufe, wurzel_wlo_id, gekuerzt, knoten, nicht_zugeordnet } = daten;
  const dokument = { typ: DOKUMENTTYP, titel, quelle, thema, fach, bildungsstufe, wurzel_wlo_id, gekuerzt, knoten,
    nicht_zugeordnet };
  return `${JSON.stringify(dokument, null, 2)}\n`;
}

/** Ein Text als Markdown-Inhalt (Review U2, Befund 7): eine Zeile, Auszeichnungs- und
 *  HTML-Zeichen maskiert — Titel der Person bauen die Liste nicht um. */
function md(text: string): string {
  return text.replace(/\s+/g, ' ').trim().replace(/[\\`*_[\]<>|~]/g, '\\$&');
}

function zeilen(baum: Baum, einzug: string, schlagworte: string): string[] {
  return baum.flatMap((k) => [
    `${einzug}- **${md(k.titel)}**${k.beschreibung ? ` — ${md(k.beschreibung)}` : ''}`,
    ...(k.keywords?.length ? [`${einzug}  ${schlagworte}: ${k.keywords.map(md).join(', ')}`] : []),
    ...zeilen(k.kinder ?? [], `${einzug}  `, schlagworte),
  ]);
}

/** `beschriftung`: die Wörter der Sprache („Fach“, „Bildungsstufe“, „Schlagworte“). */
export function alsMarkdown(
  daten: EntwurfDaten, beschriftung: { readonly fach: string; readonly stufe: string; readonly schlagworte: string },
): string {
  const angaben = [
    daten.fach ? `${beschriftung.fach}: ${md(daten.fach)}` : '',
    daten.bildungsstufe ? `${beschriftung.stufe}: ${md(daten.bildungsstufe)}` : '',
  ].filter(Boolean).join(' · ');
  return [`# ${md(daten.titel)}`, ...(angaben ? ['', angaben] : []), '',
    ...zeilen(daten.knoten, '', beschriftung.schlagworte), ''].join('\n');
}

const UMLAUTE: Readonly<Record<string, string>> = { ä: 'ae', ö: 'oe', ü: 'ue', ß: 'ss' };

/** `Optik in Klasse 8` → `optik-in-klasse-8.json`. Wie `ui-inhaltsrahmen/inhaltsrahmen.dateiname`
 *  (Module importieren einander nicht — eigene Kopie der acht Zeilen). */
export function dateiname(titel: string, endung: 'json' | 'md'): string {
  const stamm = (titel || '')
    .toLowerCase()
    .replace(/[äöüß]/g, (z) => UMLAUTE[z])
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .slice(0, 60)
    .replace(/^-+|-+$/g, '');
  return `${stamm || 'entwurf'}.${endung}`;
}
