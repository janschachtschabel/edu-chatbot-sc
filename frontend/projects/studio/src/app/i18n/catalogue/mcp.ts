/**
 * Die MCP-Registry (C1-d3c): welche Werkzeug-Server der Bot rufen darf, und
 * die Prüfung einer Adresse, bevor sie in die Liste kommt.
 *
 * Eigener Teil und nicht zusammen mit dem Wissen (`knowledge.ts`): beide sitzen
 * zwar auf der Seite „Wissen", sind aber verschiedene Sachen — Werkzeug-Server
 * gegen eigene Dokumente. Wer eine Beschriftung sucht, sucht in einem von
 * beiden, nicht in einer Datei mit 68 Einträgen.
 */
import type { CataloguePart } from './catalogue-part';

export const MCP: CataloguePart = {
  de: {
    'mcp.loading': 'Die Registry wird geladen …',

    // ── Ein Server-Eintrag ──────────────────────────────────────────
    'mcp.field.active': 'Aktiv',
    'mcp.field.id': 'Kennung',
    'mcp.field.name': 'Name',
    'mcp.field.url': 'Adresse',
    'mcp.field.description': 'Beschreibung',
    /** Der Name der Umgebungsvariablen reist als Platzhalterwert und steht
     *  nicht im Satz — Muster von `login.passwordEnv`. Kostet die
     *  `<code>`-Auszeichnung und hält den Satz als Ganzes übersetzbar. */
    'mcp.urlFromEnv': 'Kommt aus der Umgebungsvariable {env} und wird hier nicht gespeichert.',
    'mcp.noTools': 'Keine Werkzeuge gemeldet — der Server war beim Laden nicht erreichbar.',
    /** Paket 7 (S5): Werkzeuge je Server an- und abschalten. */
    'mcp.tool.offer': '{name} anbieten',
    'mcp.tool.unknown': 'kennt der Chatbot nicht — wird nicht angeboten',
    /** Paket 11 (E): Werkzeuge weiterer Server bietet der Chatbot nur lesend an. */
    'mcp.tool.writing': 'schreibend — von weiteren Servern bietet der Chatbot nur lesende an',
    'mcp.tool.serverMissing':
      'führt der Server derzeit nicht — eingeschaltet scheitert jeder Aufruf, bis der Server es wieder anbietet',
    'mcp.adopt.go': 'Werkzeuge übernehmen',
    'mcp.adopt.hint':
      'Nur lesende Werkzeuge (vom Server als lesend ausgezeichnet) bietet der Chatbot an — '
      + 'dem Modell unter „Kennung__Werkzeug“. Danach speichern.',
    'mcp.adopt.done': 'Übernommen — noch nicht gespeichert.',
    'mcp.tool.hint':
      'Abgehakt bietet der Chatbot das Werkzeug dem Modell an. search_skill ist von Haus aus '
      + 'aus: Skills kommen über die Freigabeliste der Sammlung. Wirksam nach dem Speichern.',
    'mcp.remove': 'Entfernen',
    /** Zugänglicher Name desselben Knopfs: mehrere Zeilen tragen denselben
     *  sichtbaren Text. Beginnt mit ihm (WCAG 2.5.3 „Label in Name"). */
    'mcp.removeFor': 'Entfernen — {name}',
    'mcp.primaryFixed': 'Der Primär-Server lässt sich nicht entfernen.',

    // ── Speichern ───────────────────────────────────────────────────
    'mcp.add': 'Server hinzufügen',
    'mcp.save': 'Registry speichern',
    'mcp.incomplete':
      'Nicht speicherbar: Jeder Server braucht eine Kennung — Einträge ohne '
      + 'Kennung verwirft der Server beim Speichern.',

    // ── Adresse prüfen, ohne sie einzutragen ────────────────────────
    'mcp.discover.title': 'Server prüfen',
    'mcp.discover.hint':
      'Meldet die Werkzeuge einer Adresse, ohne sie einzutragen — zum Prüfen, '
      + 'bevor der Server in die Liste kommt.',
    'mcp.discover.busy': 'Wird geprüft …',
    'mcp.discover.go': 'Prüfen',
    'mcp.discover.none': 'Der Server ist erreichbar, meldet aber kein Werkzeug.',

    // ── Abgleich: Eintragung gegen Wirklichkeit ─────────────────────
    // Bewusst ohne Anzahl im Satz: der Katalog kennt keine Mehrzahlregeln,
    // und eine Überschrift über der Liste braucht auch keine.
    'mcp.compare.missing': 'Eingetragen, aber vom Server nicht angeboten:',
    'mcp.compare.missingWhy':
      'Diese Werkzeuge bekommt das Modell angeboten, der Server kennt sie nicht — '
      + 'jeder Aufruf endet im Fehler. Meist läuft dort eine ältere Fassung.',
    'mcp.compare.match': 'Der Server bietet alles an, was für ihn eingetragen ist.',
    'mcp.compare.extra': 'Zusätzlich angeboten und hier nicht eingetragen:',
    'mcp.compare.unregistered':
      'Diese Adresse steht nicht in der Liste — es gibt nichts zu vergleichen.',
  },

  en: {
    'mcp.loading': 'Loading the registry …',

    'mcp.field.active': 'Active',
    'mcp.field.id': 'Identifier',
    'mcp.field.name': 'Name',
    'mcp.field.url': 'Address',
    'mcp.field.description': 'Description',
    'mcp.urlFromEnv': 'Comes from the environment variable {env} and is not stored here.',
    'mcp.noTools': 'No tools reported — the server was unreachable while loading.',
    'mcp.tool.offer': 'Offer {name}',
    'mcp.tool.unknown': 'not known to the chatbot — not offered',
    'mcp.tool.writing': 'writing — from further servers the chatbot offers read-only tools only',
    'mcp.tool.serverMissing':
      'not provided by the server right now — every call fails until the server offers it again',
    'mcp.adopt.go': 'Adopt tools',
    'mcp.adopt.hint':
      'The chatbot offers only read-only tools (marked as such by the server) — to the model as '
      + '“id__tool”. Save afterwards.',
    'mcp.adopt.done': 'Adopted — not saved yet.',
    'mcp.tool.hint':
      'Ticked: the chatbot offers the tool to the model. search_skill is off by default: '
      + 'skills come through the collection’s release list. Takes effect after saving.',
    'mcp.remove': 'Remove',
    'mcp.removeFor': 'Remove — {name}',
    'mcp.primaryFixed': 'The primary server cannot be removed.',

    'mcp.add': 'Add server',
    'mcp.save': 'Save registry',
    'mcp.incomplete':
      'Cannot save: every server needs an identifier — entries without one are '
      + 'dropped on save.',

    'mcp.discover.title': 'Check a server',
    'mcp.discover.hint':
      'Reports the tools of an address without registering it — to check before '
      + 'the server joins the list.',
    'mcp.discover.busy': 'Checking …',
    'mcp.discover.go': 'Check',
    'mcp.discover.none': 'The server is reachable but reports no tool.',

    'mcp.compare.missing': 'Registered here, but not offered by the server:',
    'mcp.compare.missingWhy':
      'The model is offered these tools, the server does not know them — every '
      + 'call ends in an error. Usually an older build is running there.',
    'mcp.compare.match': 'The server offers everything registered for it.',
    'mcp.compare.extra': 'Offered in addition, not registered here:',
    'mcp.compare.unregistered':
      'This address is not in the list — there is nothing to compare.',
  },
};
