# ui_themenbaum

Die Unterthemen eines WLO-Fachportals oder einer Sammlung als aufklappbarer Baum (Paket U1-e) —
das erste Modul mit **Datenquelle**. Die Logik stammt aus dem MCP-Widget `browse`
(`wlo-mcp-server-sc/src/apps/widgets/browse/`): statischer Baum aus den mitgelieferten Kindern,
Auf-/Zuklappen lokal, gekürzte Zweige markiert. Seit U1-h geht es **im selben Baum** tiefer:
fehlende Unterthemen lädt das Aufklappen nach (siehe „Nachladen“).

**Bestand, nicht Entwurf (Paket U2, Plan `docs/plans/2026-11-04-paket-u2-themenbaum-entwurf.md`):**
Dieses Modul zeigt nur, was es in WLO gibt (Marke „Aus WLO“ im Kopf). Eine **neue** Gliederung
entwirft `ui_strukturentwurf` (eigener Ordner `../ui-strukturentwurf/`). Baum, Tasten, Ansage und
Aussehen teilen beide über den gemeinsamen Kern `../_baum/` (kein Modul; das Register übergeht
ihn). Unter dem Baum steht für die Wurzel **„Als Entwurf bearbeiten“** — nur, wenn die Daten
`entwurf_moeglich` tragen (das Backend setzt es, solange der Entwurf im Studio aktiv ist): Host-Aktion `alsEntwurf`
(Fähigkeit `oeffnen`) → Direktaktion `edit_collection_as_draft` → ein neuer Zug ohne KI mit einem
`ui_strukturentwurf`-Block (Quelle `wlo`). Bestandsknoten erreichen die KI auch dann erst, wenn die
Person den Entwurf übernimmt oder dazu schreibt.

- **Aufruf:** Die KI ruft `ui_themenbaum` mit `subject` (Name eines Fachportals) **oder** `nodeId`
  (Kennung einer Sammlung). Mehr sieht sie nicht: die Parameter kommen aus der Beschreibung von
  `browse_collection_tree`, `depth: 2` und `maxResults: 31` setzt das Backend fest
  (`datenquelle.vorgaben`; ein Knoten mehr, als der Baum zeigt — kommt er, gibt es oben mehr).
  Das Nachladen (U1-h) prüft dasselbe Angebot. Das Backend ruft das Werkzeug selbst
  (`backend/src/boerdi/ui_module/datenquelle.py`), formt schlanke Knoten (`themenbaum.py`) und gibt
  der KI nur eine Quittung (Zahl der Themen, gekürzt ja/nein) — **die Knoten laufen nicht durchs
  Modell**.
- **Angeboten** nur, wenn das Widget das Modul meldet und `browse_collection_tree` im Zug verfügbar
  ist (Studio-Schalter, Sperren der Sicherheit, Modus der Einbettung). Im Muster-Modus zusätzlich
  nur, wenn das Muster das Modul in `tools:` nennt (U-F4).
- **Eingabe (Block-Daten):** `titel?` (≤ 160), `wurzel_id?`, `wurzel_url?` (die Sammlung in WLO),
  `gekuerzt?` (ein Zweig gekürzt), `wurzel_mehr?` (oben gekürzt), `knoten[]` (≤ 30) mit
  `id`, `titel` (≤ 200), `url?` (nur http/https; Themenseite vor Sammlung), `anzahl?`, `mehr?`,
  `kinder[]` (≤ 10, eine Ebene). Beschreibungen und übrige Felder des Servers bleiben draußen.
- **Bedienung (WAI-ARIA Tree View):** `tree`/`treeitem`/`group`, Ebene, Position, `aria-expanded`,
  wandernder `tabindex`, die Auswahl folgt dem Fokus (`aria-selected` = der Knoten, für den die
  Aktionsleiste gilt — eine Antwort ist das nicht); ↑ ↓ wechseln, → öffnet bzw. springt ins erste Kind, ← schließt bzw.
  springt zum Elternknoten, Pos1/Ende, Enter/Leertaste klappen (auch Einträge, deren Unterthemen
  erst geladen werden); Enter auf einem Blatt zeigt dessen Inhalte (Standardaktion). Anzahl,
  „weitere“ und der Ladezustand über `aria-describedby`; Ebene, Position und Größe je Gruppe.
  Start zugeklappt.
- **Aktionen** stehen nicht im Baumeintrag, sondern in einer Leiste für den aktiven Knoten:
  „Inhalte anzeigen“ (`host.aktion('sammlung')` → Direktaktion `browse_collection`; gesperrt
  während eines Zugs), „In WLO öffnen“ (`host.link`, Sitzungs-Kennung und Hinweis wie überall),
  nach einem Ladefehler „Erneut laden“. Den Knopf „Unterthemen öffnen“ (neuer Baum als Antwort,
  U1-e) gibt es seit U1-h nicht mehr.
- **Nachladen (U1-h):** Kinder eines Knotens sind *bekannt*, wenn er als Knoten einer Antwort kam
  (erste Ebene des Blocks oder eines Zweigs; der Server holt zwei Ebenen), sonst *unbekannt*.
  Aufklappen eines unbekannten oder gekürzten („weitere“) Knotens ruft `host.zweig(nodeId)` →
  Shell → `POST /api/ui/themenbaum/zweig` (kein Zug, keine KI, nichts gespeichert; Tiefe und
  Menge setzt das Manifest) und hängt die Antwort (Form der Block-Daten) ein. Sichtbar und
  nachgeladen wird bis Ebene 8 (auch mitgebrachte tiefere Kinder bleiben verborgen), tiefer
  bleibt „In WLO öffnen“; die Einrückung je Ebene schrumpft mit der Breite (20 px breit, rund
  13 px bei 320 px). Ein Vorfahr, der in einem nachgeladenen Zweig wieder auftaucht (Kreis im
  Repositorium), steht dort als Blatt. Zustände am Eintrag: „lädt …“ (`aria-busy`, Kreisel ohne
  Animation bei `prefers-reduced-motion`), „nicht geladen“ (Knopf „Erneut laden“; ein Eintrag
  ohne mitgelieferte Kinder ist danach wieder zu, →/Enter/Klick versuchen es direkt neu; bei 403
  kein neuer Versuch), bei 429 „zu viele Anfragen – bitte kurz warten“ (neuer Versuch nur auf
  Wunsch), „keine Unterthemen“ (dann ein Blatt). Eine höfliche Statuszeile sagt das Ergebnis an
  (dieselbe Meldung zweimal wird zweimal angesagt). Stand der Fokus im Baum, bleibt er am Knoten
  und folgt beim Ersetzen einer gekürzten Liste dem Thema; wer in die Aktionsleiste gewechselt
  ist, bleibt dort. Nachgeladenes gilt **bis zum Neuladen**; der Verlauf zeigt den ursprünglichen
  Baum. Das Backend nimmt als Knoten nur edu-sharing-Kennungen (UUID). Regeln in
  `themenbaum-zweige.ts`, Texte in `themenbaum-texte.ts`.
- **Fähigkeiten:** `oeffnen`, `nachladen`.
- **Zustände:** leer („Hier gibt es keine Unterthemen.“, Aktionen dann für die Sammlung selbst),
  gekürzt (Hinweis unter dem Baum, „weitere“ am Zweig — Aufklappen lädt mehr, vollständig ist es
  in WLO), oben gekürzt (Hinweis „mehr, als hier stehen“ mit Link „Alle in WLO ansehen“, wenn
  `wurzel_url` da ist). Ohne brauchbares Ergebnis des ersten Abrufs entsteht kein Block (die KI
  bekommt eine Fehlermeldung); Fehler beim Nachladen stehen am Eintrag (siehe „Nachladen“).
- **Textfassung** (ältere Widgets, `/api/agent`): eingerückte Markdown-Liste mit Links.
- **Barrierefrei:** Fokus sichtbar an der Zeile, aktiver Eintrag zusätzlich fett, Zielflächen
  ≥ 28 px, Knöpfe 32 px, bedienbar ab 320 px. Texte de/en über `kontext().sprache`.
- Nach jeder Manifest-Änderung: `npm run module:register`.

Noch nicht: Auswahl eines Knotens („später wählen“) — dafür kommt das abfragende
`ui_themenbaum_auswahl` (Plan §13). Muster, die heute `browse_collection_tree` selbst nennen,
zeigen weiter Karten.
