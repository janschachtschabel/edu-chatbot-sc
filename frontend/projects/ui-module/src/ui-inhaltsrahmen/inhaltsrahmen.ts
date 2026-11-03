/**
 * Reine Hilfen des Inhaltsrahmens: Art → Symbol und Bezeichnung, Dateiname und Inhalt des
 * Markdown-Downloads. Symbole und Bezeichnungen der ersten fünf Arten wie in der früheren
 * Dokument-Box (bis U1-b3 `ui/src/inline-doc/`, ALT-Port).
 */
import { ICONS } from '@boerdi/ui/icons/icons';

type Sprache = 'de' | 'en';

interface ArtEintrag {
  readonly symbol: string;
  readonly de: string;
  readonly en: string;
}

export const ARTEN: Readonly<Record<string, ArtEintrag>> = {
  lernpfad: { symbol: ICONS.route, de: 'Lernpfad', en: 'Learning path' },
  ki_material: { symbol: ICONS.article, de: 'Material', en: 'Material' },
  edit: { symbol: ICONS.edit, de: 'Bearbeitete Version', en: 'Edited version' },
  bericht: { symbol: ICONS.description, de: 'Bericht', en: 'Report' },
  remix: { symbol: ICONS.refresh, de: 'Remix', en: 'Remix' },
  stundenplanung: { symbol: ICONS.list, de: 'Stundenplanung', en: 'Lesson plan' },
  unterrichtsreihe: { symbol: ICONS.topic, de: 'Unterrichtsreihe', en: 'Teaching unit' },
  zeugnis: { symbol: ICONS.school, de: 'Zeugnis', en: 'Report card' },
  dokument: { symbol: ICONS.description, de: 'Dokument', en: 'Document' },
  kompendialtext: { symbol: ICONS.auto_stories, de: 'Fachtext', en: 'Subject text' },
  volltext: { symbol: ICONS.menu_book, de: 'Volltext', en: 'Full text' },
  // Eine vorgeschlagene, noch nicht ausgeführte Änderung — bewusst kein Haken.
  schreib_vorschau: { symbol: ICONS.edit_note, de: 'Vorgeschlagene Änderung', en: 'Proposed change' },
};

const RUECKFALL: ArtEintrag = { symbol: ICONS.description, de: 'Inhalt', en: 'Content' };

/** Die Art kommt aus Modell und Verlauf — zur Laufzeit nicht sicher ein Text, und Namen wie
 *  `constructor` träfen sonst `Object.prototype`. */
function eintrag(art: string): ArtEintrag {
  const schluessel = typeof art === 'string' ? art.toLowerCase() : '';
  return Object.hasOwn(ARTEN, schluessel) ? ARTEN[schluessel] : RUECKFALL;
}

export function artSymbol(art: string): string {
  return eintrag(art).symbol;
}

export function artBezeichnung(art: string, sprache: Sprache): string {
  return eintrag(art)[sprache];
}

const UMLAUTE: Readonly<Record<string, string>> = { ä: 'ae', ö: 'oe', ü: 'ue', ß: 'ss' };
const NAME_HOECHSTENS = 60;

/** `Übung für Größe!` → `uebung-fuer-groesse.md`; ohne verwertbaren Titel `inhalt.md`. */
export function dateiname(titel: string): string {
  const stamm = (titel || '')
    .toLowerCase()
    .replace(/[äöüß]/g, (z) => UMLAUTE[z])
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .slice(0, NAME_HOECHSTENS)
    .replace(/^-+|-+$/g, '');
  return `${stamm || 'inhalt'}.md`;
}

/** Der Inhalt der Markdown-Datei: Titel als Überschrift, wenn er nicht schon vorne steht. */
export function markdownDatei(titel: string, markdown: string): string {
  const kopf = `# ${titel}`;
  const rumpf = (markdown ?? '').trimEnd();
  if (!rumpf.trim()) return `${kopf}\n`;
  return (rumpf.trimStart().startsWith(`${kopf}\n`) || rumpf.trim() === kopf ? rumpf : `${kopf}\n\n${rumpf}`) + '\n';
}
