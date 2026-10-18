/**
 * Karte „Werk und eigene Fassung“ der Ansicht „Sicherung“ (Paket 12).
 *
 * Die Werksfassung kommt mit jeder Version aus dem Repository (Seed im Abbild); die gelebte steht
 * in der Datenbank. Die Sätze versprechen nur, was der Server tut: Umschalten verliert nichts (die
 * andere Fassung liegt still), der Werksabgleich fasst Angepasstes nie an.
 */
import type { CataloguePart } from './catalogue-part';

export const FASSUNGEN: CataloguePart = {
  de: {
    'fassungen.title': 'Werk und eigene Fassung',
    'fassungen.lead':
      'Die Werksfassung kommt mit jeder Version aus dem Repository. Bereiche, die du nicht '
      + 'angepasst hast, folgen ihr beim nächsten Start von selbst; angepasste behalten deine '
      + 'Fassung. Je Bereich kannst du wechseln — die andere Fassung bleibt erhalten und lässt '
      + 'sich zurückholen.',
    'fassungen.unavailable':
      'Dieses Abbild bringt keine Werksfassung mit (CONFIG_SEED_DIR zeigt auf kein Verzeichnis).',
    'fassungen.summary':
      '{werk} auf der Werksfassung · {eigen} angepasst, davon {neu} mit neuer Werksfassung',
    'fassungen.filter.legend': 'Anzeigen',
    'fassungen.filter.angepasst': 'Angepasst',
    'fassungen.filter.neu': 'Neue Werksfassung',
    'fassungen.filter.alle': 'Alle',
    'fassungen.empty.angepasst': 'Nichts angepasst — alle Bereiche stehen auf der Werksfassung.',
    'fassungen.empty.neu': 'Keine angepasste Fassung wartet auf eine neue Werksfassung.',
    'fassungen.empty.alle': 'Keine Bereiche.',
    'fassungen.status.werk': 'Werk',
    'fassungen.status.werk-veraltet': 'Werk · neue Fassung kommt beim nächsten Start',
    'fassungen.status.eigen': 'Angepasst',
    'fassungen.status.eigen-neues-werk': 'Angepasst · neue Werksfassung verfügbar',
    'fassungen.status.nur-eigen': 'Nur eigen (kein Werksbereich)',
    'fassungen.status.werk-entfernt': 'Werksbereich gelöscht',
    'fassungen.status.werk-fehlt': 'Werksbereich fehlt',
    'fassungen.eigeneLiegt': 'Eine eigene Fassung liegt still.',
    'fassungen.aktiv': 'Aktiv:',
    'fassungen.wahl.werk': 'Werksfassung',
    'fassungen.wahl.eigen': 'Eigene Fassung',
    'fassungen.schalterHint':
      'Umschalten verliert nichts: die andere Fassung bleibt erhalten und lässt sich mit demselben '
      + 'Schalter zurückholen.',
    'fassungen.ohneEigene':
      'Noch keine eigene Fassung — sie entsteht, wenn du den Bereich im Editor änderst.',
    'fassungen.aktualisieren': 'Jetzt aktualisieren',
    'fassungen.keinWerk': 'Für diesen Bereich gibt es keine Werksfassung — er entstand im Studio.',
    'fassungen.zweiEigene':
      'Werksfassung erst nach dem Tausch — sonst ginge eine der beiden eigenen Fassungen '
      + 'verloren.',
    'fassungen.tauschen': 'Mit stillgelegter tauschen',
    'fassungen.imEditor': 'Im Editor öffnen',
    'fassungen.felderCaption.gelebt': 'Unterschiede je Feld',
    'fassungen.felderCaption.eigene': 'Stillgelegte Fassung je Feld',
    'fassungen.felderRegion.gelebt': 'Unterschiede je Feld für {area}',
    'fassungen.felderRegion.eigene': 'Stillgelegte Fassung von {area} je Feld',
    'fassungen.spalte.feld': 'Feld',
    'fassungen.spalte.werk': 'Werksfassung',
    'fassungen.spalte.gelebt': 'Eigene Fassung',
    'fassungen.spalte.eigene': 'Stillgelegt',
    'fassungen.feldFehlt': '— fehlt',
    'fassungen.felderWeitere.one': '{count} weiteres Feld weicht ab — siehe Rohansicht.',
    'fassungen.felderWeitere.other': '{count} weitere Felder weichen ab — siehe Rohansicht.',
    'fassungen.rohansicht.gelebt': 'Rohansicht (Zeilen-Vergleich)',
    'fassungen.rohansicht.eigene': 'Rohansicht der stillgelegten Fassung',
    'fassungen.restore': 'Werksfassung wiederherstellen',
    'fassungen.diffShow': 'Unterschied zeigen',
    'fassungen.diffHide': 'Unterschied ausblenden',
    'fassungen.diffLegend': '− Werksfassung · + gelebte Fassung',
    'fassungen.diffNone': 'Kein Unterschied.',
    'fassungen.diffRegion': 'Unterschied für {area}',
    'fassungen.diffEigeneLegend': 'Stillgelegte Fassung gegen die Werksfassung (− Werksfassung · + stillgelegt)',
    'fassungen.diffEigeneRegion': 'Stillgelegte Fassung von {area}',
    'fassungen.switching': 'Wird umgeschaltet …',
    'fassungen.switchedWerk': '{area}: Werksfassung aktiv, deine Fassung liegt still.',
    'fassungen.updatedWerk': '{area}: auf die aktuelle Werksfassung aktualisiert.',
    'fassungen.switchedGeprueft':
      '{area}: deine Fassung bleibt, die aktuelle Werksfassung gilt als gesehen.',
    'fassungen.markGeprueft': 'Als geprüft markieren',
    'fassungen.geprueftHint':
      '„Als geprüft markieren“ behält deine Fassung und merkt die aktuelle Werksfassung als gesehen — bis zur nächsten neuen.',
    'fassungen.switchedEigen': '{area}: deine Fassung ist wieder aktiv.',
    'fassungen.restored': '{area}: Werksfassung wiederhergestellt.',
    'fassungen.abgleich': 'Werksabgleich starten',
    'fassungen.abgleichRunning': 'Werksabgleich läuft …',
    'fassungen.abgleichHint':
      'Läuft auch bei jedem Start von selbst. Legt Fehlendes an, hebt Unberührtes auf die '
      + 'neue Werksfassung und fasst Angepasstes und Gelöschtes nicht an.',
    'fassungen.abgleichDone':
      'Werksabgleich: {neu} neu, {aktualisiert} aktualisiert, {neues_werk} angepasst mit '
      + 'neuer Werksfassung.',
    'fassungen.abgleichNachtrag':
      '{uebersprungen} übersprungen (inzwischen geändert — der nächste Abgleich sieht sie neu), '
      + '{konflikt} nicht angelegt, weil ihre Kennung nicht verwendbar ist (schon vergeben '
      + 'oder ungültig).',
    'fassungen.backupHinweis':
      'Sicherungen und Snapshots enthalten die gelebte Fassung, nicht die stillgelegte eigene.',
  },
  en: {
    'fassungen.title': 'Factory and own version',
    'fassungen.lead':
      'The factory version ships with every release from the repository. Areas you have not '
      + 'customized follow it on the next start; customized ones keep your version. You can '
      + 'switch per area — the other version is kept and can be brought back.',
    'fassungen.unavailable':
      'This image ships no factory version (CONFIG_SEED_DIR points to no directory).',
    'fassungen.summary':
      '{werk} on the factory version · {eigen} customized, {neu} of them with a new factory '
      + 'version',
    'fassungen.filter.legend': 'Show',
    'fassungen.filter.angepasst': 'Customized',
    'fassungen.filter.neu': 'New factory version',
    'fassungen.filter.alle': 'All',
    'fassungen.empty.angepasst': 'Nothing customized — every area is on the factory version.',
    'fassungen.empty.neu': 'No customized version is waiting for a new factory version.',
    'fassungen.empty.alle': 'No areas.',
    'fassungen.status.werk': 'Factory',
    'fassungen.status.werk-veraltet': 'Factory · new version arrives on the next start',
    'fassungen.status.eigen': 'Customized',
    'fassungen.status.eigen-neues-werk': 'Customized · new factory version available',
    'fassungen.status.nur-eigen': 'Own only (no factory area)',
    'fassungen.status.werk-entfernt': 'Factory area deleted',
    'fassungen.status.werk-fehlt': 'Factory area missing',
    'fassungen.eigeneLiegt': 'An own version is set aside.',
    'fassungen.aktiv': 'Active:',
    'fassungen.wahl.werk': 'Factory version',
    'fassungen.wahl.eigen': 'Own version',
    'fassungen.schalterHint':
      'Switching loses nothing: the other version is kept and comes back with the same switch.',
    'fassungen.ohneEigene':
      'No own version yet — it appears once you change the area in the editor.',
    'fassungen.aktualisieren': 'Update now',
    'fassungen.keinWerk': 'There is no factory version of this area — it was created in the studio.',
    'fassungen.zweiEigene':
      'Factory version only after the swap — otherwise one of the two own versions would be '
      + 'lost.',
    'fassungen.tauschen': 'Swap with the one set aside',
    'fassungen.imEditor': 'Open in editor',
    'fassungen.felderCaption.gelebt': 'Differences per field',
    'fassungen.felderCaption.eigene': 'Version set aside, per field',
    'fassungen.felderRegion.gelebt': 'Differences per field for {area}',
    'fassungen.felderRegion.eigene': 'Version of {area} set aside, per field',
    'fassungen.spalte.feld': 'Field',
    'fassungen.spalte.werk': 'Factory version',
    'fassungen.spalte.gelebt': 'Own version',
    'fassungen.spalte.eigene': 'Set aside',
    'fassungen.feldFehlt': '— missing',
    'fassungen.felderWeitere.one': '{count} more field differs — see the raw view.',
    'fassungen.felderWeitere.other': '{count} more fields differ — see the raw view.',
    'fassungen.rohansicht.gelebt': 'Raw view (line comparison)',
    'fassungen.rohansicht.eigene': 'Raw view of the version set aside',
    'fassungen.restore': 'Restore factory version',
    'fassungen.diffShow': 'Show differences',
    'fassungen.diffHide': 'Hide differences',
    'fassungen.diffLegend': '− factory version · + live version',
    'fassungen.diffNone': 'No differences.',
    'fassungen.diffRegion': 'Differences for {area}',
    'fassungen.diffEigeneLegend': 'Version set aside against the factory version (− factory · + set aside)',
    'fassungen.diffEigeneRegion': 'Version of {area} set aside',
    'fassungen.switching': 'Switching …',
    'fassungen.switchedWerk': '{area}: factory version active, your version is set aside.',
    'fassungen.updatedWerk': '{area}: updated to the current factory version.',
    'fassungen.switchedGeprueft':
      '{area}: your version stays, the current factory version counts as seen.',
    'fassungen.markGeprueft': 'Mark as reviewed',
    'fassungen.geprueftHint':
      '“Mark as reviewed” keeps your version and records the current factory version as seen — until the next new one.',
    'fassungen.switchedEigen': '{area}: your version is active again.',
    'fassungen.restored': '{area}: factory version restored.',
    'fassungen.abgleich': 'Run factory sync',
    'fassungen.abgleichRunning': 'Factory sync running …',
    'fassungen.abgleichHint':
      'Also runs on every start. Creates what is missing, lifts untouched areas to the new '
      + 'factory version and leaves customized and deleted ones alone.',
    'fassungen.abgleichDone':
      'Factory sync: {neu} new, {aktualisiert} updated, {neues_werk} customized with a new '
      + 'factory version.',
    'fassungen.abgleichNachtrag':
      '{uebersprungen} skipped (changed meanwhile — the next sync sees them again), {konflikt} '
      + 'not created because their id cannot be used (already taken or invalid).',
    'fassungen.backupHinweis':
      'Backups and snapshots hold the live version, not the own version set aside.',
  },
};
