/**
 * Alles über das Struktur-Schema: die Vorlagen für „Auftrag" und „Struktur",
 * und die Prüfung dessen, was am Ende im Feld steht.
 *
 * Beides zusammen, weil beides sich aus demselben Grund ändert — wenn sich
 * ändert, was ein gültiges Schema ist. Der Deckel unten gilt für die Vorlagen
 * genauso wie für Handarbeit; `scripts/check-schemas.mjs` prüft beide dagegen.
 *
 * An ihnen wird die eine Sache sichtbar, die man leicht übersieht: **die
 * `description`-Texte liest das Modell.** Sie sind Anweisung, nicht Notiz für
 * die Gastseite. „Die Vokabular-URI, nicht der Klartext" steht dort, weil sonst
 * „Physik" zurückkommt.
 *
 * Dasselbe gilt für den Auftrag: wo eine Aufgabe ein bestimmtes Werkzeug
 * braucht (`lookup_wlo_vocabulary`, `search_skill`, `get_compendium_text`),
 * steht es ausdrücklich darin. Ohne diesen Hinweis rät das Modell aus dem
 * Gedächtnis, statt nachzusehen — und rät bei URIs zuverlässig falsch.
 *
 * Das Backend deckelt das Schema bei 10 000 Zeichen (serialisiert) und lehnt
 * darüber mit 422 ab, statt zu kürzen.
 */

/** Wiederkehrend in vier Schemata: was das Modell NICHT prüfen konnte. Lieber
 *  benannt als geraten — der Systemprompt verlangt es ohnehin. */
const NICHT_PRUEFBAR = {
  type: 'array',
  items: { type: 'string' },
  description:
    'Was du NICHT prüfen konntest, je ein Satz. Lieber hier nennen als raten. '
    + 'Leer, wenn du alles prüfen konntest.',
};

export const VORLAGEN = [
  {
    id: 'fach-stufe',
    name: 'Fach und Stufe zuordnen',
    auftrag:
      'Welches Fach und welche Stufe würdest Du dem Inhalt zuordnen? '
      + 'Löse beides über das WLO-Vokabular auf (lookup_wlo_vocabulary mit '
      + '"discipline" bzw. "educationalContext") und gib die URIs zurück, '
      + 'nicht nur die Namen.',
    schema: {
      type: 'object',
      properties: {
        discipline_uri: {
          type: 'string',
          description:
            'Vokabular-URI des Fachs, z.B. '
            + 'http://w3id.org/openeduhub/vocabs/discipline/460 — NICHT der '
            + 'Klartext. Über lookup_wlo_vocabulary auflösen, nicht raten.',
        },
        discipline_label: { type: 'string', description: 'Der Klartext dazu, z.B. "Physik".' },
        educational_context_uris: {
          type: 'array',
          items: { type: 'string' },
          description:
            'Die URIs, die lookup_wlo_vocabulary(vocabulary="educationalContext") '
            + 'liefert — unverändert übernommen, nicht aus dem Label gebaut. '
            + 'Mehrere sind erlaubt: Inhalte passen oft in zwei Stufen.',
        },
        educational_context_labels: {
          type: 'array', items: { type: 'string' },
          description: 'Die Klartexte dazu, z.B. ["Sekundarstufe I"].',
        },
        begruendung: {
          type: 'string',
          description: 'Woran du es festmachst, zwei Sätze. Nenne, worauf du dich stützt.',
        },
        sicherheit: {
          type: 'number',
          description: 'Wie sicher bist du, 0 bis 1. Rate nicht hoch.',
        },
        nicht_pruefbar: NICHT_PRUEFBAR,
      },
      required: ['discipline_uri', 'discipline_label', 'educational_context_labels'],
    },
  },

  {
    id: 'kuratierung',
    name: 'Kuratierung: Metadatensatz bilden',
    auftrag:
      'Unterstütze mich bei der Kuratierung: bilde für diesen Inhalt einen '
      + 'vollständigen Metadatensatz — Titel, Beschreibungstext, Keywords, '
      + 'wwwurl, Fach, Bildungsstufe und Inhaltstyp. Fach, Bildungsstufe und '
      + 'Inhaltstyp löst du über das WLO-Vokabular auf '
      + '(lookup_wlo_vocabulary mit "discipline", "educationalContext" bzw. '
      + '"lrt") und gibst die URIs mit an. Was du nicht belegen kannst, lässt '
      + 'du weg und nennst es unter nicht_pruefbar.',
    schema: {
      type: 'object',
      properties: {
        titel: {
          type: 'string',
          description:
            'Sprechender Titel (cclom:title), höchstens 80 Zeichen. Kein '
            + 'Dateiname, keine ID — so, wie er in einer Trefferliste steht.',
        },
        beschreibung: {
          type: 'string',
          description:
            'Beschreibungstext (cclom:general_description), 3–5 Sätze: worum '
            + 'es geht, für wen, was man damit tut. Keine Werbung, keine '
            + 'Wiederholung des Titels.',
        },
        keywords: {
          type: 'array',
          items: { type: 'string' },
          description:
            'Schlagworte (cclom:general_keyword), 5–10 Stück, klein '
            + 'geschrieben, keine Dopplung des Titels und keine Stufen- oder '
            + 'Fachnamen (die stehen schon in den Feldern darunter).',
        },
        wwwurl: {
          type: 'string',
          description:
            'Die Quell-Adresse des Inhalts (ccm:wwwurl) — die Seite selbst, '
            + 'NICHT die WLO-Seite darüber. Leer lassen, wenn du sie nicht '
            + 'sicher kennst; eine geratene URL ist schlimmer als keine.',
        },
        fach: {
          type: 'object',
          properties: {
            uri: {
              type: 'string',
              description:
                'Vokabular-URI, z.B. http://w3id.org/openeduhub/vocabs/'
                + 'discipline/460 (ccm:taxonid). Über lookup_wlo_vocabulary '
                + 'auflösen, nicht raten.',
            },
            label: { type: 'string', description: 'Der Klartext, z.B. "Physik".' },
          },
          required: ['label'],
        },
        bildungsstufe: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              uri: {
                type: 'string',
                description:
                  'Die URI, die lookup_wlo_vocabulary(vocabulary='
                  + '"educationalContext") zu diesem Label liefert '
                  + '(ccm:educationalcontext). Übernimm sie unverändert — '
                  + 'baue sie NICHT aus dem Label zusammen.',
              },
              label: { type: 'string', description: 'z.B. "Sekundarstufe I".' },
            },
            required: ['label'],
          },
          description: 'Mehrere sind erlaubt — Inhalte passen oft in zwei Stufen.',
        },
        inhaltstyp: {
          type: 'object',
          properties: {
            uri: {
              type: 'string',
              description:
                'Die URI, die lookup_wlo_vocabulary(vocabulary="lrt") zu '
                + 'diesem Label liefert (ccm:oeh_lrt). Gemessene Form: '
                + 'http://w3id.org/openeduhub/vocabs/new_lrt_aggregated/… — '
                + 'übernimm sie, wie sie kommt, statt sie zu bauen.',
            },
            label: {
              type: 'string',
              description: 'z.B. "Arbeitsblatt", "Video", "Unterrichtsplanung".',
            },
          },
          required: ['label'],
        },
        passende_sammlungen: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              titel: { type: 'string' },
              node_id: { type: 'string', description: 'Die echte ID aus der Suche, nicht erfunden.' },
              warum: { type: 'string' },
            },
            required: ['titel'],
          },
          description: 'Gefundene Sammlungen, in die der Inhalt passt. Leer ist erlaubt.',
        },
        nicht_pruefbar: NICHT_PRUEFBAR,
      },
      required: ['titel', 'beschreibung', 'keywords', 'fach', 'bildungsstufe', 'inhaltstyp'],
    },
  },

  {
    id: 'qualitaet',
    name: 'Qualitätsprüfung mit Skills',
    auftrag:
      'Führe eine Qualitätsprüfung mit den passenden Skills durch. Suche '
      + 'zuerst mit search_skill nach einer Anleitung, die zu dieser Aufgabe '
      + 'passt, hole sie mit get_skill und arbeite DANACH — statt den Ablauf '
      + 'selbst zu erfinden. Sag ausdrücklich, wenn du keine passende '
      + 'Anleitung gefunden hast.',
    schema: {
      type: 'object',
      properties: {
        genutzte_skills: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              titel: { type: 'string' },
              node_id: { type: 'string', description: 'Die nodeId aus dem Treffer.' },
            },
            required: ['titel'],
          },
          description:
            'Die Anleitungen, nach denen du tatsächlich gearbeitet hast. '
            + 'LEER, wenn du keine gefunden hast — nicht füllen, um die Liste '
            + 'zu füllen.',
        },
        ergebnis: {
          type: 'string',
          enum: ['bestanden', 'mit_auflagen', 'nicht_bestanden', 'nicht_pruefbar'],
          description: 'Das Gesamturteil.',
        },
        befunde: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              kriterium: { type: 'string', description: 'Woran du geprüft hast.' },
              bewertung: { type: 'string', enum: ['erfuellt', 'teilweise', 'nicht_erfuellt'] },
              beleg: { type: 'string', description: 'Worauf du dich stützt — konkret.' },
            },
            required: ['kriterium', 'bewertung'],
          },
        },
        nicht_pruefbar: NICHT_PRUEFBAR,
      },
      required: ['ergebnis', 'genutzte_skills'],
    },
  },

  {
    id: 'sachlich',
    name: 'Sachlich richtig? (gegen das Kompendium)',
    auftrag:
      'Ist der Inhalt sachlich richtig oder widerspricht er dem Kompendium? '
      + 'Hole den Kompendiumstext (get_compendium_text) und vergleiche Aussage '
      + 'für Aussage. Behaupte nichts aus dem Gedächtnis.',
    schema: {
      type: 'object',
      properties: {
        urteil: {
          type: 'string',
          enum: ['stimmt_ueberein', 'teilweise', 'widerspricht', 'nicht_pruefbar'],
          description:
            'nicht_pruefbar, wenn es kein Kompendium gibt oder du es nicht '
            + 'laden konntest — das ist KEIN "stimmt_ueberein".',
        },
        widersprueche: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              aussage_im_inhalt: { type: 'string', description: 'Wörtlich oder eng paraphrasiert.' },
              aussage_im_kompendium: { type: 'string' },
              schwere: { type: 'string', enum: ['klein', 'mittel', 'gross'] },
            },
            required: ['aussage_im_inhalt', 'aussage_im_kompendium'],
          },
          description: 'Leer, wenn es keine gibt.',
        },
        bestaetigt: {
          type: 'array', items: { type: 'string' },
          description: 'Aussagen, die das Kompendium ausdrücklich stützt.',
        },
        nicht_pruefbar: NICHT_PRUEFBAR,
      },
      required: ['urteil'],
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
          type: 'array', items: { type: 'string' },
          description: 'Drei bis acht Schlagworte, klein geschrieben.',
        },
      },
      required: ['titel', 'zusammenfassung'],
    },
  },
];

/** Vorlage nach Kennung; `null` wenn es sie nicht gibt. */
export function vorlage(id) {
  return VORLAGEN.find((v) => v.id === id) || null;
}

/** Der Deckel des Backends (`MAX_RESULT_SCHEMA_CHARS` in `api/schemas.py`).
 *  Darüber lehnt es mit 422 ab, statt zu kürzen — ein halbes Schema wäre ein
 *  anderes Schema. */
export const MAX_SCHEMA_ZEICHEN = 10000;

/**
 * Was im Schema-Feld steht — geprüft, nicht geraten.
 *
 * **`gueltig` ist NICHT „es gibt ein Schema".** Ein leeres Feld ist gültig und
 * liefert `schema: null`: der Chat ohne strukturiertes Ergebnis ist ein
 * erlaubter Start. Ein Tippfehler ist ungültig und liefert ebenfalls `null` —
 * und genau diese beiden auseinanderzuhalten ist der Zweck des Feldes
 * `gueltig`. Ohne es startete ein kaputtes Schema einen vollen Agent-Zug (bis
 * 12 Runden, 90 s Frist), der garantiert kein Ergebnis liefern kann.
 *
 * @param {string} roh — der Feldinhalt
 * @returns {{schema: object|null, gueltig: boolean, text: string}} `text` ist
 *   für Menschen und geht so, wie er ist, in die Leiste.
 */
export function pruefeSchema(roh) {
  const s = String(roh ?? '').trim();
  if (!s) {
    return {
      schema: null, gueltig: true,
      text: 'Kein Schema — der Chat läuft ohne strukturiertes Ergebnis.',
    };
  }
  let wert;
  try {
    wert = JSON.parse(s);
  } catch (err) {
    return { schema: null, gueltig: false, text: `Kein gültiges JSON: ${err.message}` };
  }
  if (!wert || typeof wert !== 'object' || Array.isArray(wert)) {
    return {
      schema: null, gueltig: false,
      text: 'Ein JSON-Schema muss ein Objekt sein (kein Array, keine Zahl).',
    };
  }
  const laenge = JSON.stringify(wert).length;
  if (laenge > MAX_SCHEMA_ZEICHEN) {
    return {
      schema: null, gueltig: false,
      text: `${laenge} Zeichen — das Backend lehnt über ${MAX_SCHEMA_ZEICHEN} mit 422 ab.`,
    };
  }
  return { schema: wert, gueltig: true, text: `Gültig, ${laenge} Zeichen.` };
}
