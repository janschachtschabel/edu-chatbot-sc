/**
 * Drei Vorlagen für das Feld „Struktur".
 *
 * Sie stehen hier, damit man beim Ausprobieren nicht erst ein JSON-Schema
 * tippen muss — und weil an ihnen die eine Sache sichtbar wird, die man leicht
 * übersieht: **die `description`-Texte liest das Modell.** Sie sind Anweisung,
 * nicht Notiz für die Gastseite. „Die Vokabular-URI, nicht der Klartext" steht
 * dort, weil das Modell sonst „Physik" zurückgibt.
 *
 * Das Backend deckelt das Schema bei 10 000 Zeichen (serialisiert) und lehnt
 * darüber mit 422 ab, statt zu kürzen.
 */
export const VORLAGEN = [
  {
    id: 'taxonid',
    name: 'Fachzuordnung (taxonid)',
    auftrag: 'Welchem Fach ordnest du diese Seite zu? Nutze das WLO-Vokabular.',
    schema: {
      type: 'object',
      properties: {
        taxon_id: {
          type: 'string',
          description:
            'Die Vokabular-URI der Fachzuordnung, z.B. '
            + 'http://w3id.org/openeduhub/vocabs/discipline/460 — NICHT der '
            + 'Klartext-Name des Fachs.',
        },
        label: { type: 'string', description: 'Der Klartext-Name, z.B. "Physik".' },
        confidence: {
          type: 'number',
          description: 'Wie sicher bist du, 0 bis 1. Rate nicht hoch.',
        },
      },
      required: ['taxon_id', 'label'],
    },
  },
  {
    id: 'zusammenfassung',
    name: 'Zusammenfassung + Schlagworte',
    auftrag: 'Fasse zusammen, worum es auf dieser Seite geht.',
    schema: {
      type: 'object',
      properties: {
        titel: { type: 'string', description: 'Ein Satz, höchstens 80 Zeichen.' },
        zusammenfassung: { type: 'string', description: 'Drei bis fünf Sätze.' },
        schlagworte: {
          type: 'array',
          items: { type: 'string' },
          description: 'Drei bis acht Schlagworte, klein geschrieben.',
        },
      },
      required: ['titel', 'zusammenfassung'],
    },
  },
  {
    id: 'pruefung',
    name: 'Sammlung prüfen',
    auftrag:
      'Prüfe diese Sammlung: Gibt es Anleitungen (Skills) daran? Wie viele '
      + 'Materialien? Halte dich an eine passende Anleitung, falls es eine gibt.',
    schema: {
      type: 'object',
      properties: {
        anzahl_materialien: { type: 'integer', description: 'Gezählt, nicht geschätzt.' },
        skills: {
          type: 'array',
          items: { type: 'string' },
          description: 'Die Titel der freigegebenen Anleitungen. Leer, wenn es keine gibt.',
        },
        befund: { type: 'string', description: 'Was dir aufgefallen ist, in zwei Sätzen.' },
        nicht_pruefbar: {
          type: 'array',
          items: { type: 'string' },
          description: 'Was du NICHT prüfen konntest. Lieber hier nennen als raten.',
        },
      },
      required: ['anzahl_materialien', 'befund'],
    },
  },
];

/** Vorlage nach Kennung; `null` wenn es sie nicht gibt. */
export function vorlage(id) {
  return VORLAGEN.find((v) => v.id === id) || null;
}
