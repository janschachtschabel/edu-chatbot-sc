/** Die Texte des Themenbaums, de und en (Plan §3.5: eigene Texte in der Komponente). */
export const TEXTE = {
  de: {
    ueberschrift: (t: string) => (t ? `Unterthemen von ${t}` : 'Unterthemen'),
    // U2: Herkunft im Kopf und die Brücke zum Entwurf.
    marke: 'Aus WLO',
    alsEntwurf: 'Als Entwurf bearbeiten',
    leer: 'Hier gibt es keine Unterthemen.',
    // Review U1-h, Befund 11: ein nachgeladener Zweig ist selbst gedeckelt — „mehr“, nicht „alle“.
    gekuerzt: 'Nicht alle Unterthemen passen in diese Übersicht. Zweige mit „weitere“ laden beim Aufklappen mehr; vollständig zeigt sie WLO.',
    wurzelMehr: 'Es gibt mehr Unterthemen, als hier stehen.',
    alleAnsehen: 'Alle in WLO ansehen',
    mehr: 'weitere',
    anzahl: (n: number) => (n === 1 ? '1 Inhalt' : `${n.toLocaleString('de-DE')} Inhalte`),
    aktionen: (t: string) => `Aktionen für ${t}`,
    inhalte: 'Inhalte anzeigen',
    oeffnen: 'In WLO öffnen',
    // U1-h: Nachladen im Baum
    zustand: {
      laedt: 'lädt …', fehler: 'nicht geladen', gedrosselt: 'zu viele Anfragen – bitte kurz warten', leer: 'keine Unterthemen',
      // N5: vom Server gemeldet — Ausfall (Aufklappen lädt neu) und abgelehnt (bleibt so).
      ungelesen: 'Unterthemen gerade nicht lesbar – Aufklappen lädt neu', gesperrt: 'Unterthemen nicht zugänglich',
    },
    erneut: 'Erneut laden',
    geladen: (n: number, t: string) => (n === 1 ? `1 Unterthema von ${t} geladen.` : `${n} Unterthemen von ${t} geladen.`),
    keine: (t: string) => `${t} hat keine Unterthemen.`,
    fehler: (t: string) => `Die Unterthemen von ${t} ließen sich nicht laden.`,
    gedrosselt: (t: string) => `Zu viele Anfragen – bitte kurz warten und die Unterthemen von ${t} dann erneut laden.`,
    nichtLesbar: (t: string) => `Die Unterthemen von ${t} sind nicht zugänglich.`,
  },
  en: {
    ueberschrift: (t: string) => (t ? `Subtopics of ${t}` : 'Subtopics'),
    marke: 'From WLO',
    alsEntwurf: 'Edit as draft',
    leer: 'There are no subtopics here.',
    gekuerzt: 'Not all subtopics fit into this overview. Branches marked “more” load more when expanded; WLO shows all of them.',
    wurzelMehr: 'There are more subtopics than shown here.',
    alleAnsehen: 'See all in WLO',
    mehr: 'more',
    anzahl: (n: number) => (n === 1 ? '1 item' : `${n.toLocaleString('en-GB')} items`),
    aktionen: (t: string) => `Actions for ${t}`,
    inhalte: 'Show contents',
    oeffnen: 'Open in WLO',
    zustand: {
      laedt: 'loading …', fehler: 'not loaded', gedrosselt: 'too many requests – please wait a moment', leer: 'no subtopics',
      ungelesen: 'subtopics could not be read just now – expand to retry', gesperrt: 'subtopics not accessible',
    },
    erneut: 'Retry loading',
    geladen: (n: number, t: string) => (n === 1 ? `1 subtopic of ${t} loaded.` : `${n} subtopics of ${t} loaded.`),
    keine: (t: string) => `${t} has no subtopics.`,
    fehler: (t: string) => `The subtopics of ${t} could not be loaded.`,
    gedrosselt: (t: string) => `Too many requests – please wait a moment, then retry loading the subtopics of ${t}.`,
    nichtLesbar: (t: string) => `The subtopics of ${t} are not accessible.`,
  },
} as const;
