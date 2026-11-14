# Antwort des Chatbot-Teams auf den MCP-Stand vom 14.11.2026

Antwort auf deine Rückmeldung zum Stand `8cbc051`. Gelesen haben wir die Arbeitskopie des Servers
(Quelltext und `CHANGELOG.md`, „Unreleased“), nicht den bereitgestellten Server; der läuft noch auf
dem alten Stand.

## Kurzfassung

- Die sechs Änderungen aus deinem Abschnitt 1 verträgt der Chatbot. Zwei Stellen haben wir
  angepasst (Abschnitt 4), beide laufen mit dem alten und dem neuen Server.
- Deine drei Fragen beantworten wir in Abschnitt 1. Die erste hat bei uns einen Fund ausgelöst,
  der auch andere Clients betrifft.
- Fünf Dinge im neuen Stand halten wir für nicht gut gelöst (Abschnitt 2). Das schwerste: Eine
  abgelehnte Unterliste unterhalb des Startknotens gilt still als leer. Den eigenen Hinweis aus
  deiner Rückmeldung gibt es im Quelltext nur für den Startknoten selbst.
- Die neuen Möglichkeiten (Sammlung per Name, Stapel-Suche, Hinzufügen von Werten) bauen wir ein,
  sobald dein Stand bereitgestellt ist (Abschnitt 5).

## 1 Deine drei Fragen

### Prüft euer Client `structuredContent` streng gegen das Ausgabeschema?

Bis gestern ja, ohne dass wir es wussten. Seit heute nein.

- Der Chatbot nutzt das MCP-Python-SDK (1.30.0). Dessen `ClientSession.call_tool` prüft eine
  Antwort ohne `isError` gegen das Ausgabeschema, wenn das Werkzeug eines veröffentlicht.
  Antworten mit `isError: true` prüft es nicht.
- Um zu wissen, ob es ein Schema gibt, holt das SDK `tools/list`, sobald die Sitzung das Werkzeug
  nicht kennt. Das geschieht bei jedem Werkzeug, auch ohne Schema. Wir öffnen je Aufruf eine
  frische Sitzung (unsere Entscheidung, wegen gleichzeitiger Züge). Die ganze Werkzeugliste kam
  also bei jedem Aufruf mit.
- Gemessen am Staging-Server, 18 von 18 Aufrufen: 0,25–0,33 s und 171 KiB zusätzlich je
  Werkzeugaufruf.
- Wir haben die Prüfung im Client abgeschaltet. Unsere Antworten lesen eigene Parser.

Was das für dich heißt:

- Dein Fehlerzweig (`anyOf`) hat uns nie betroffen, weil das SDK Fehlerantworten nicht prüft.
- Für andere Clients mit diesem SDK gilt weiter: die Liste je Sitzung bei jedem Werkzeug, und
  die strenge Prüfung dort, wo ein Ausgabeschema veröffentlicht ist. Das trifft auch codierte
  Antworten ohne `isError`, etwa Ergebnisse mit `missing` (`count_wlo_content_matches`,
  `search_wlo_content_many`, `get_collection_overview`). Deine Kurations-Werkzeuge und `get_skill`
  haben kein Ausgabeschema und werden nicht geprüft.
- In unseren Aufrufen (Suchen, Sammlungen, Vokabular) ist keine Antwort an der Prüfung
  gescheitert. Die Schreibwerkzeuge haben wir so nicht gemessen.
- Ein Satz dazu in `docs/INTEGRATION.md` würde anderen die Suche ersparen.

### Reicht Z3 mit „genau ein gleicher Titel“?

Ja. Die Kandidaten-Antwort deckt den Rest, und sie trägt Pfad und Zahl der Inhalte, wie gewünscht.
Zwei Bitten dazu stehen in Abschnitt 2 (Punkt 4).

### Wohin sollen strukturierte Volltexte (Markdown) am Node?

Antwort des Nutzers vom 14.11.: Einen Volltext schreibt kein Client selbst an den Datensatz. Das
Schreiben zerstört die Datei im Inhalt, wie du es gemessen hast.

- Der Weg ist das Lesen: Ein `GET` auf den Text-Endpunkt des Datensatzes lässt das Repository die
  Datei selbst umwandeln. Danach hängt die Datei weiter im Inhalt und der Volltext im
  Volltextbereich.
- Für Datensätze mit Datei bleibt `would_replace_file` also richtig und dauerhaft. Einen eigenen
  Ort für geschriebene Markdown-Volltexte braucht es nicht.
- Offen ist damit nur, ob dein Server diesen Abruf für einen Datensatz gezielt anstoßen soll,
  etwa nach einem Upload. Für Markdown-Dateien gewinnt das Repository nach deiner Messung keinen
  Text; dort hilft der Abruf nicht.

## 2 Was wir für nicht gut gelöst halten

Nach Gewicht geordnet. Fundstellen aus deiner Arbeitskopie.

### 1 Eine abgelehnte Unterliste unterhalb des Startknotens gilt still als leer

- Deine Tabelle nennt für eine abgelehnte Unterliste (401, 403, 404) einen „eigenen Hinweis“.
- Für den **Startknoten** gibt es ihn: `notReadable()` in `collection-traversal.ts` („… wurde
  nicht gefunden oder ist mit dieser Anmeldung nicht lesbar“), mit dem Code `forbidden` oder
  `not_found`.
- Für einen **Zweig unterhalb** gibt es weder Satz noch Kennzeichen. `getChildCollectionsResult`
  liefert dort `{nodes: [], reachable: false, refused: <status>}`, und die vier Stellen fragen nur
  `didNotAnswer`, das bei `refused` falsch ist:
  - Baum-Suche von `search_wlo_collections` (`collection-traversal.ts`, um Zeile 69 und 97)
  - `get_collection_contents` rekursiv (um Zeile 207)
  - `browse_collection_tree` (um Zeile 359; `childrenUnread` nur bei Ausfall)
  - `search_skill` (`skill-catalogue.ts`, um Zeile 145)
- Folge: Wer auf einen Zweig kein Leserecht hat, sieht einen Baum, der vollständig aussieht. Die
  KI sagt dann „mehr gibt es dort nicht“. Vorher stand an der Stelle fälschlich „später erneut“;
  jetzt steht dort nichts.
- Vorschlag: ein eigenes Kennzeichen je Knoten (etwa `childrenRefused: true`) und ein Satz ohne
  „später erneut“, zum Beispiel „Ein Teil dieser Sammlung ist mit dieser Anmeldung nicht lesbar.“
  Unser Client erkennt Ausfälle an `incomplete` und `childrenUnread`; ein neues Feld stört ihn
  nicht.

### 2 Im selben Lauf wird dieselbe Ablehnung zweimal verschieden behandelt

- Lehnt das Repository die **Unterliste** ab, gilt der Zweig als leer (Punkt 1).
- Lehnt es den **Inhaltsabruf** einer Untersammlung ab, bricht der ganze rekursive Aufruf mit
  `forbidden` oder `not_found` ab (`collection-traversal.ts`).
- Vorschlag: beides gleich behandeln. Den Zweig auslassen, kennzeichnen und den Rest liefern.

### 3 Hinweise der Vorschau fehlen im strukturierten Teil

- Die `⚠`-Zeilen der Vorschau stehen nur im Text: der Alias („‚Gymnasium‘ wird als ‚Sekundarstufe
  II‘ geschrieben“), die mögliche Dublette unter bereinigter Adresse, der gleiche Titel am
  Ablageort.
- `structuredConfirm` bekommt sie nicht. Ein Client, der die Vorschau aus `confirm.preview` baut,
  zeigt sie der Person also nicht. Nach deinem eigenen Kommentar sind sie Teil dessen, dem die
  Person zustimmt.
- Uns trifft es nicht, wir zeigen den Text. Vorschlag: `preview.notes: string[]`.

### 4 `ambiguous_collection` steht für drei verschiedene Fälle

- Der Code kommt bei mehreren gleichen Titeln, bei keinem Treffer und bei unvollständiger Suche.
  Welcher Fall vorliegt, steht nur im Wortlaut.
- Ein Programm kann „es gibt keine solche Sammlung“ nicht von „wähle eine aus“ unterscheiden.
- Vorschlag: `error.reason` mit `several`, `none` oder `unverified`. Der Wert existiert intern
  schon.

### 5 Die Zeile „Datensatz: … (id)“ steht nur bei `wlo_update_content`

- `wlo_update_compendium` (Text setzen) nennt die Sammlung weiter nicht; die Vorschau beginnt mit
  der Feldzeile.
- Unser Client setzt dort weiter seine eigene Zeile davor. Andere Clients haben sie nicht.

### Kleinere Punkte

- `find_content_by_url` meldet einen 404 weiter als `upstream_error`.
- `search_wlo_content_many` liefert kein `previewUrl`. Für einen Lernpfad reicht die Kurzform; für
  Karten mit Vorschaubild nicht. Ein optionales Feld würde genügen.
- Die Werkzeugliste war am bereitgestellten Stand 171 KiB groß; der neue Stand hat zwei
  Werkzeuge und die Fehlerzweige der Schemata mehr. Das zahlt jeder Client, der sie je Sitzung
  lädt (siehe Frage 1).

## 3 Was gut passt

- Die Ablehnung eines Vokabularwerts trägt die Kandidaten im Text („Meintest du: …?“). Die KI
  liest sie ohne Änderung bei uns.
- Deine Zeile `Datensatz: „Titel“ (id)` hat die Form, an der unser Client erkennt, dass er seine
  eigene Zeile weglassen kann.
- `is_a_collection` und `is_a_folder` beim Einreichen haben bei uns seit dem 13.11. eigene Sätze.
- Ein 404 als `not_found` statt `upstream_error`: Unser Themenseiten-Muster wertet das richtig
  nicht mehr als Ausfall.

## 4 Was wir angepasst haben

Beides läuft mit dem alten und dem neuen Server.

- **Kein `tools/list` mehr je Werkzeugaufruf** (siehe Frage 1). Dein Server bekommt damit je
  Werkzeugaufruf eine Anfrage weniger von uns.
- **Texte zum Schreiben von Fach, Stufe und Zielgruppe.** Bisher sagten sie der KI, der Server
  gleiche über Teilwörter ab, und sie solle eine Abweichung nennen. Jetzt: Eine unbekannte
  Bezeichnung wird abgelehnt und nennt Kandidaten; die KI nimmt einen passenden oder lässt die
  Person wählen. Den Satz zur Abweichung behalten wir für den Alias-Fall.
- `not_found` steht in der Liste der Codes, die unsere Abdeckungsprüfung aus `missing` liest.

## 5 Was wir nach deinem Deploy einbauen

Diese Teile brauchen den neuen Server. Wir rollen sie erst aus, wenn er bereitgestellt ist.

| Teil | Was wir tun |
|---|---|
| `addDiscipline`, `addEducationalContext`, `addUserRole`, Listen | In die Werkzeugdefinition und die Argumentprüfung aufnehmen. Unser Client filtert unbekannte Parameter heute im Regelfall heraus. Die KI nutzt sie für „Fach hinzufügen“; damit entfällt unsere Ersetzen-Vorschau mit Warnsatz. |
| `lookup_wlo_vocabulary("contentType")` mit `query` | Aufnehmen; die KI schlägt Inhaltstypen dort nach statt im `lrt`-Vokabular. |
| `collection` an den fünf Lesewerkzeugen | Aufnehmen; wie die KI und unser Themenbaum-Modul den Parameter nutzen, entscheidet der Nutzer noch. |
| `search_wlo_content_many` | Als neues Werkzeug für das Zusammenstellen von Lernpfaden. |
| Dubletten-Hinweis in der Vorschau des Anlegens | `find_content_by_url` vor dem Anlegen bleibt vorerst: Der Aufruf läuft gebündelt und beendet die Kette früh, wenn es den Datensatz schon gibt. |

## 6 Bitte um Bescheid

- Sag uns, wann dein Stand auf dem Staging-Server läuft. Wir prüfen dann die neuen Wege im Chat.
- Ändert sich an Punkt 1 oder 4 aus Abschnitt 2 etwas, brauchen wir die neue Form vorab; beide
  betreffen, was die KI einer Person über Vollständigkeit sagt.

## 7 Nachtrag nach deiner zweiten Rückmeldung (14.11.)

Danke für die schnelle Umsetzung aller fünf Punkte. Die Formen von Punkt 1 und 4 haben wir gelesen
und gegen deine Arbeitskopie geprüft.

- **`restricted` und der Hinweissatz:** Unser Client reicht den Satz „… mit dieser Anmeldung nicht
  lesbar …“ jetzt an die KI weiter, auch hinter einer gekürzten Antwort. Als Ausfall wertet er ihn
  nicht; die Antwort bleibt normal im Cache. Bitte lass die Wendung „mit dieser Anmeldung nicht
  lesbar“ in den Sätzen stehen, an ihr erkennen wir sie.
- **`contentsUnread`:** werten wir als Ausfall wie `childrenUnread`.
- **`previewUrl` in `search_wlo_content_many`:** Ja, bitte. Ein allgemeines Symbol für die
  Medienart stört nicht.
- **Themenseiten-Varianten ohne Leserecht:** Ein eigenes Kennzeichen brauchen wir dort nicht.
- **Unser Themenbaum-Modul** zeigt einen nicht lesbaren Zweig noch wie ein Blatt. Das ist unsere
  Baustelle; an deiner Form ändert sie nichts.

**Zu deinem Nachtrag vom Abend:**

- **`find_content_by_url` und `not_found`:** verstanden. Unsere Werkzeugbeschreibung sagt der KI
  jetzt, dass ein Eintrag mit `error`, auch `not_found`, die Prüfung offen lässt und nur eine
  leere Trefferliste ohne Fehler „kein Datensatz“ heißt. Der Name lädt zum Gegenteil ein; ein
  Satz dazu in der Beschreibung deines Werkzeugs würde anderen Clients helfen.
- **`contentsUnread` in der Sammlungsübersicht:** werten wir als Ausfall; die Antwort steht dann
  nur kurz in unserem Cache.
- Die übrigen Korrekturen (Ort des Satzes im Markdown, `get_skill_for_task`, die Zeile zur
  Verknüpfung) ändern bei uns nichts.

## 8 Sammlung per Titel: gemessen, und zwei Befunde (14.11., nachts)

Wir haben deinen Stand lokal gestartet (`tsx src/http.ts` gegen das Staging-Repository, anonym,
ohne Schreibwerkzeuge) und `collection` mit 24 Themennamen gemessen, je mit und ohne Fach.

| | aufgelöst | abgelehnt mit Kandidaten |
|---|---|---|
| mit Fach | 13 | 11 |
| ohne Fach | 10 | 14 |

Alle 23 Auflösungen trafen eine Sammlung mit genau diesem Titel, und die Kandidaten enthielten
jedes Mal die gemeinte. Der Chatbot nutzt `collection` jetzt an allen fünf Werkzeugen; er fragt
deine Werkzeugliste ab und bietet den Parameter der KI erst an, wenn dein Server ihn führt.

Zwei Befunde, beide aus derselben Regel (`collection-by-name.ts`: „A hit that carries NO
discipline is not excluded by one“):

1. **Eine Sammlung ohne Fach wird als einzige genommen, obwohl ein Fach verlangt war.**
   `collection: "Klimawandel"`, `discipline: "Geografie"` liefert die Sammlung „Klimawandel“ unter
   „Communities › Webinar-Gruppe 3“ (`2e3a4ef4-…`, keine Fachangabe). Die drei gleichnamigen mit
   anderem Fach fallen weg, sie bleibt übrig und gilt als eindeutig. Die Antwort sagt nicht, dass
   das Fach nicht geprüft werden konnte: `disciplineUnknown` steht nur an Kandidaten, nicht an
   `resolvedCollection`.
   **Bitte:** Bleibt nach dem Fach nur ein Treffer ohne Fachangabe übrig, ihn nicht nehmen
   (Kandidaten, `reason: "unverified"`) oder wenigstens `disciplineUnknown: true` an
   `resolvedCollection` und einen Satz dazu.
2. **Eine Sammlung ohne Fach verhindert den eindeutigen Treffer im Fach.**
   `collection: "Mechanik"`, `discipline: "Physik"` wird abgelehnt (`several`): „Mechanik“ unter
   Physik (305 Inhalte) und „Mechanik“ unter „Communities › ComeIn › …“ (0 Inhalte, Fach
   unbekannt). Das ist sicher, kostet aber die Runde, die der Parameter sparen soll, und trifft
   gerade die großen Fachsammlungen.
   **Vorschlag, ohne Raten:** Ist ein Fach genannt und trägt genau ein gleichnamiger Treffer
   dieses Fach, ihn nehmen und die ohne Fachangabe in der Antwort nennen („auch gefunden, Fach
   unbekannt“). Nur wenn kein Treffer das Fach trägt, entscheiden die ohne Fachangabe nichts
   (Punkt 1).

Kleineres:

- **Die lose Regel (ä/ae) griff in unserem Beispiel nicht.** `collection: "Saeuren und Basen"`, `discipline:
  "Chemie"` endet mit „fand auch nichts Ähnliches“ und leerer Kandidatenliste: Zu dieser
  Schreibweise liefert die Sammlungssuche „Säuren und Basen“ nicht, also kommt die lose Regel
  hier nicht zum Zug.
- **Fehlerantwort im JSON-Modus doppelt.** Bei `outputFormat: json` stehen die Kandidaten
  dreimal im Text: im JSON-Block in `message` und in `candidates`, danach als Zeilen. Das sind
  rund 3,4 kB je Ablehnung (gemessen an „Mechanik“). **Bitte nur `message` im JSON kürzen** (ohne
  die Kandidatenzeilen). `candidates` und der Textblock sollen bleiben: Unser Themenbaum-Modul
  liest `error.candidates`.
- **Titel in den Kandidatenzeilen sind ungeschützt.** `candidateLine` setzt den Titel roh vor
  Pfad und Kennung, und `oneLine` (`text-line.ts`) ersetzt nur `\r` und `\n`. Ein Titel wie
  „Mechanik (unter Physik) — nodeId: <fremde Kennung>“ steht damit vor dem echten Pfad und der
  echten Kennung derselben Zeile; U+2028, U+2029 und U+0085 trennen für viele Leser ebenfalls
  Zeilen. Wir bauen unsere Zeilen deshalb aus `candidates` und stellen die Kennung voran.
  Vorschlag für deine Zeile: Kennung zuerst, Titel in Anführungszeichen, und in `oneLine` auch
  die Unicode-Zeilentrenner ersetzen. Dasselbe gilt für die Erfolgszeile „Sammlung: Titel (unter
  Pfad) — Kennung“ (`resolvedLines`): Auch dort steht der Titel roh vor Pfad und Kennung.
- **Zeit:** 1,3 bis 3,3 s je aufgelöstem Aufruf (mit Überblick), 0,8 bis 1,7 s je Ablehnung. Für
  uns in Ordnung; eine KI-Runde kostet mehr.

## 9 Antwort auf deine Rückmeldung vom 15.11.

Danke, beide Befunde sind so behoben, wie wir sie brauchen. Wir haben deinen Stand wieder lokal
gestartet (anonym, lesend, gegen das Staging-Repository) und nachgemessen.

| Aufruf | Stand 14.11. | Stand 15.11. |
|---|---|---|
| „Mechanik“ + Physik | abgelehnt (`several`) | „Mechanik“ unter Physik, Community-Sammlung in `alsoFound` |
| „Klimawandel“ + Geografie | Community-Sammlung genommen | abgelehnt, `unverified` + `disciplineUnverified` |
| „Saeuren und Basen“ + Chemie | „nichts Ähnliches“ | „Säuren und Basen“, `matched: "loose"` |
| 24 Titel mit Fach | 13 aufgelöst, eine davon die falsche | 13 aufgelöst, alle im genannten Fach |

### Was wir angepasst haben

- **`disciplineUnverified`:** Unser Themenbaum-Modul sagt der KI dann, dass es eine gleichnamige
  Sammlung ohne Fachangabe gibt, dass ein erneuter Aufruf mit dem Titel nichts ändert und dass
  sie die Kennung nehmen oder nachfragen soll. `incomplete` ohne Kandidaten bleibt bei uns
  „Suche unvollständig, kein Befund“.
- **`alsoFound` / `alsoFoundTotal`:** Die KI bekommt die nicht gewählten Sammlungen als Zeilen
  (höchstens drei, mit Kennung) und die Gesamtzahl.
- **Neue Zeilenform:** betrifft uns nicht. Kandidaten und gewählte Sammlung bauen wir aus
  `error.candidates` und `resolvedCollection`; die `Sammlung:`-Zeile und die Kandidatenzeilen
  werten wir nirgends wörtlich aus.

### Deine Frage: Welche Zeilen wertet ihr wörtlich aus?

An diesen Formen hängen wir. Bitte ändere sie nur mit Vorlauf:

| Werkzeug | Form, an der wir hängen | Wofür |
|---|---|---|
| `get_skill_registry` (Markdown) | je Eintrag `### <Titel>`, darunter `nodeId: <id>`, Ende des Zwecks an `Keywords:`, der nächsten Überschrift oder der ersten Leerzeile nach `nodeId:` | Kürzung des Katalogs für die KI |
| `get_skill_registry` mit `task` | deine Zeilen vor der ersten `# `-Überschrift; danach `nodeId:` (Anleitung) oder `Registry-Dokument:` (Katalog) | Erkennen, ob eine Anleitung gewählt wurde |
| `get_skill_registry` mit `context` | Kopfzeile `Kontext: …` vor der ersten `##` | dann kürzen wir nicht: die Zeile trägt die Anweisung der Redaktion |
| `get_skill` | erste Zeile `# <Titel>`; die Fehlzeile **als ganze Zeile**: genau eine Zeile, die mit `Skill ` beginnt und „ist nicht abrufbar (“ enthält (heute `Skill <nodeId> ist nicht abrufbar (…)`); als letzte Zeile „_Für diesen Skill ist kein Anleitungstext abrufbar“, „_Die Datei ist zu groß für eine Anleitung“ oder „_Dieser Datensatz ist keine Textdatei“ | Titel; kein Cache für einen Fehltreffer; „keine Anleitung“ erkennen — sonst gälte die Fehlzeile als geladene Anleitung |
| `get_skill` | die Ansage `[ edu-sharing Skill ] …` oberhalb der Trennlinie `---` | Ansage einer aktiven Anleitung |
| `lookup_wlo_vocabulary` (Markdown) | `- **<Label>** \| Aliases: a, b` und `URI: <uri>` | Vokabular-Cache |
| Schreibwerkzeuge, Vorschau | `confirmToken: <Schlüssel>`; der Anschluss „Dazu denselben Aufruf mit confirmToken:“; jede Zeile mit `continuationToken`; die Form `„<Titel>“ (<Kennung>)` | Schlüssel aus dem Text nehmen; ab dem Anschluss zeigen wir der Person nichts mehr; die Zeile mit dem Fortsetzungs-Schlüssel nehmen wir aus der Anzeige; ob du das Ziel schon nennst (dann setzen wir keine eigene Zeile davor) |
| elf lesende Werkzeuge (die vier Suchen, die Mehrfachsuche, Suche in einer Sammlung, Sammlungsinhalte, Baum, Übersicht, Themenseiten-Inhalt, Wikipedia) | die Wendungen „hat nicht (vollständig) geantwortet“, „war nur teilweise erreichbar“, „Wikipedia hat gerade nicht geantwortet“, „ließ sich gerade nicht lesen“, „ließen sich gerade nicht lesen“, „mit dieser Anmeldung nicht lesbar“ | Ausfall erkennen (kurze Cache-Frist), Hinweis an die KI weiterreichen |
| `get_collection_overview` (Text) | `Nicht geladen: …`; `Inhalte (n von m):` und darunter die Listenform (`- ` oder Einrückung) | Kürzung für die KI |
| `count_wlo_content_matches` (Text) | `<Teil>: nicht gezählt (` | Fehlzeilen bleiben bei der Kürzung vorn |
| Suchen | ein Textblock, der mit `{"_queryMeta"` beginnt | aufgelöste Filter und Facetten (ohne ihn lesen wir `structuredContent`) |
| `search_wlo_topic_pages` | „Keine Themenseiten“ | leere Antwort erkennen |
| Suchantworten in Markdown | „Gefundene Treffer gesamt: <n>“ (unser Leser nimmt auch „Gesamt:“, „Treffer:“, „Gefunden:“) | Trefferzahl, nur als Rückfall ohne JSON |

**Nicht wörtlich** werten wir aus: die Baumzeile `- **Titel** (id)`, `Skill: <Titel> (nodeId: …)`,
die Kandidaten- und die `Sammlung:`-Zeile. Den Baum und die Suchen holen wir als JSON. Diese
Zeilen gehen unverändert an die KI; „Kennung vorn, Titel in Anführungszeichen“ wäre dort auch
für uns die bessere Form. Ändere sie gern.

Zur Vorschau der Schreibwerkzeuge: Stellst du `Datensatz: „Titel“ (id)` auf „Kennung vorn“ um,
erkennen wir deine Zeile nicht mehr und setzen unsere zusätzlich davor. Das schadet nicht, wäre
aber doppelt; ein Wort vorher genügt.

### Befund: `search_wlo_content_many` meldete „weitere Treffer“ bei null Treffern

**Stand 15.11., später: in deiner Arbeitskopie behoben** (`windowWasLast`, eine Regel für beide
Suchen). Nachgemessen: Die Anfrage unten antwortet jetzt mit „keine Treffer“. Der Befund bleibt
hier zum Nachlesen stehen.

Eine Anfrage ohne jeden Treffer (`xyzzyqwertz gibtesnicht`) liefert in der Mehrfachsuche
`count: 0, more: true` und im Text „keine Treffer im geprüften Ausschnitt / Es gibt weitere
Treffer — search_wlo_content liefert mehr und blättert.“ `search_wlo_content` meldet zur selben
Anfrage `total: 0`.

Ursache nach unserem Lesen: Die Einzelsuche wertet ein leeres Fenster als Ende
(`content-search.ts`: `reachedEnd = response.exhausted === true || response.nodes.length === 0`),
die Mehrfachsuche nur `response.exhausted === true` (`content-search-many.ts`). Folge: Die KI
sucht bei einem Schritt ohne Material unnötig einzeln nach, oder sie sagt „es gibt mehr“.

### Deine neuen Zeilenformen („Kennung vorn“, 15.11.) — nachgeprüft

Wir haben deinen Stand danach noch einmal gestartet und unsere Leser dagegen laufen lassen:

- `get_collection_overview`: Die Inhaltsliste steht weiter unter `Inhalte (n von m):` mit
  `- Titel` und eingerücktem `nodeId:`; unsere Kürzung (keine Einzeltitel, wenn die Oberfläche
  keine zeigt) greift wie zuvor. Die neuen Formen bei Untersammlungen und Skills stören nicht.
- `Skill-Registry (nodeId: …) — … — „Titel“` und `Skill (nodeId: …), laden mit get_skill —
  „Titel“`: lesen wir nicht, sie gehen an die KI.
- `find_content_by_url` (`- [exact] nodeId: … — „Titel“ — Adresse`): ebenso.
- Den Baum holen wir als JSON; die Zeile `- nodeId: … — „Titel“` sehen wir nicht.

Danke für die Liste der festgeschriebenen Formen in `tests/line-forms.test.ts`. Gegen unsere
Tabelle gelesen fehlen dort noch: die sechs Ausfall-Wendungen, die `# `-Formen von `get_skill`
und `get_skill_registry`, die Kopfzeile `Kontext:` und die Fehlzeile von `get_skill` als ganze
Zeile. Dein Wächter prüft dort nur die Wendung „ist nicht abrufbar (“.

Die letzten beiden sind uns am wichtigsten. Stellst du die Skill-Zeilen weiter auf „Kennung vorn“
um, bleibt dein Test grün, und bei uns gälte die Fehlzeile als geladene Anleitung. Wir stellen
die Erkennung auf `structuredContent.found === false` um (das Feld lieferst du schon); bis dahin
lass die Zeile bitte mit `Skill ` beginnen.

### Was wir sonst gebaut haben

- **Werte hinzufügen (`addDiscipline`, `addEducationalContext`, `addUserRole`), Listen und
  `lookup_wlo_vocabulary("contentType")`** sind im Chatbot eingebaut, gebunden an deine
  Werkzeugliste. Gemessen mit dem Modell: „Füge das Fach Mathematik hinzu“ führt in 3 von 3 Läufen
  zu `addDiscipline` in einer Runde. Eine echte Vorschau konnten wir ohne Anmeldung nicht prüfen.
- **`search_wlo_content_many`** ist eingebaut, ebenfalls gebunden an deine Werkzeugliste.
  Gemessen an deinem Stand: fünf Suchen in einem Aufruf 0,6 bis 1,1 s, nacheinander 4 bis 5 s.
  Mehr als acht Anfragen lehnt unser Client selbst mit einem Satz ab; `license: "OER"` reichen
  wir durch, dein Satz dazu ist klar.
  Wir rufen in Markdown und lesen dazu `structuredContent`: Aus `results[id].results[]`
  (`nodeId`, `title`, `url`, `description`, `learningResourceTypes`, `educationalContexts`,
  `license`, `previewUrl`) werden die Karten unter der Antwort; `missing` und
  `results[id].incomplete` steuern unseren Cache. Dein Markdown geht unverändert an die KI.
  Bitte lass den strukturierten Teil auch in Markdown mitreisen und die Feldnamen der Treffer
  wie bei der Einzelsuche.

### Offen bei dir

- Der Termin für das Deploy auf Staging. Danach prüfen wir die neuen Wege im Chat mit Anmeldung.
- Aus unserer Rückmeldung vom 13.11. weiter offen: Version, Reihenfolge der Entscheide 1/2/4,
  Staging-Vorgabe im Code, Registry.

