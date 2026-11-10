# P1: Grenzen des Chatbot-Wegs der Umwandlung (2026-11-09)

Plan: [`2026-11-09-ablaeufe-im-studio.md`](2026-11-09-ablaeufe-im-studio.md), D9 (P1-a bis P1-c).
Grundlage für AS-T (Schritt `umwandeln` mit `ort: chatbot|kestra`). Fünfte Fassung nach vier
Reviews (Tabellen am Ende).

## Kurz

- **Messung:** Die Umwandlung im Chatbot (markitdown im Kindprozess) schafft bei dichtem Satz rund
  0,28 s je PDF-Seite plus etwa 2 s fest. In die 60 s eines Uploads passen etwa 200 Seiten,
  nicht die erlaubten 300.
  - Es gibt **einen** Platz je Backend-Replik; Chat-Uploads und RAG-Importe teilen ihn.
  - Höchstens 3 Umwandlungen dürfen zugleich laufen oder warten.
  - Daraus folgen etwa 4–5 PDFs zu 40 Seiten je Minute.
  - Scans gehen nur über Kestra (OCR).
- **Nach dem Upload kommt der Chatbot nicht verlässlich an den Inhalt:**
  - Die Bytes einer privaten Datei liefert das MCP mit der Anmeldung der Person nicht (gemessen:
    `eduservlet/download` 403, `GET …/content` 405).
  - Der Text aus dem Repository (`textContent`) kam in derselben Messung leer, wenn auch für eine
    JSON-Datei; für PDF/DOCX/PPTX gibt es keinen Beleg.
- **Darum ist zu entscheiden, wo und wann umgewandelt wird.** Unten stehen sechs Wege mit ihren
  Kosten und Voraussetzungen (§ Optionen). Keiner davon ist heute ohne neuen Code oder ohne Zutun
  des Teams baubar; die Notiz empfiehlt deshalb noch keinen Übergang, sondern nennt, was vorher zu
  klären ist.

## Wie gemessen

- **Skript:** `backend/scripts/umwandlung_messen.py` erzeugt eigene Testdokumente, ohne Download
  und ohne fremde Dateien:
  - PDF mit Textschicht in 10/40/120/300/301 Seiten, je etwa 4 760 Zeichen (dichter Satz);
  - PDF nur aus Bildern (Scan);
  - DOCX mit Überschriften und Tabelle;
  - PPTX mit 30 Folien.
- **Verarbeitung:** die Umwandlung wie beim Upload (`dokumente.umwandlung.wandle`: Kindprozess, ein
  Platz, `PLATZ_FRIST_S` 20 s, `MAX_WARTENDE` 3, Frist 60 s wie `ui_dokumente.FRIST_S`). **Ohne**
  die übrige Aufbereitung eines Uploads (`aufnahme.aufbereiten`: Bereinigung, Gliederung,
  Moderation über das Netz, Befund) — ein Zug dauert entsprechend länger.
- **Güte:** Jede Zeile trägt eine eigene Marke (`Z<seite>x<zeile>`). Gezählt werden die
  gefundenen Marken und ob sie in der Reihenfolge stehen.
- **Maschine:** Windows-Entwicklungsrechner mit 16 Kernen.
  - pdfminer rechnet einfädig; eine Umwandlung nutzt einen Kern.
  - Auf dem vServer (2 Kerne) teilt sie die Kerne mit dem Backend und dem Reranker
    (`RERANK_INTRA_OP_THREADS`): Dort wird sie langsamer, und der Chat aller anderen wird zäher.
  - Dort neben der Dauer auch die Antwortzeit des Chats messen.
- **Grenzen der Testdokumente:**
  - Sie sind synthetisch: einfacher Satz, ohne Bilder, Spalten oder eingebettete Schriften.
  - Die Dauer hängt an Zeichen und Layoutobjekten, nicht an Seiten. Ein dünnes PDF mit 300 Seiten
    kann in die Frist passen, ein echter Lehrplan langsamer sein.
  - P1-a verlangt echte Unterlagen; offen: mindestens ein echtes Lehrplan-PDF auf dem vServer.
- **Rechnung:** (4,8 − 2)/10 ≈ (13 − 2)/40 ≈ (35 − 2)/120 ≈ 0,28 s je Seite. Die etwa 2 s fest
  sind rund 0,6 s Kindprozess (die Vorprüfung bei 301 Seiten) plus das Laden von markitdown.

## P1-a Formate und Qualität

| Datei | Größe | Dauer | Ergebnis |
|---|---|---|---|
| PDF 10 Seiten | 63 KB | 4,8 s | 47 742 Zeichen, Text vollständig, **keine Überschriften** |
| PDF 40 Seiten | 250 KB | 13,0 s | 191 504 Zeichen, vollständig |
| PDF 120 Seiten | 750 KB | 35,0 s | 574 854 Zeichen, vollständig |
| PDF 300 Seiten | 1,9 MB | 60 s | **Abbruch `umwandlung_zu_langsam`** |
| PDF 301 Seiten | 1,9 MB | 0,6 s | `zu_viele_seiten` (Grenze `max_seiten` 300, Vorprüfung) |
| PDF nur Bilder, 5 Seiten | 1 MB | 2,0 s | 0 Zeichen; laut Code meldet die Aufbereitung dann `kein_text` (`gescannt`) |
| DOCX, 400 Absätze | 3 KB | 2,1 s | 43 028 Zeichen, alle 40 Überschriften (das Skript zählte 39: eine am Textanfang fehlte in der Zählung), Tabelle als Markdown-Tabelle |
| PPTX, 30 Folien | 57 KB | — | **im Chat nicht zugelassen** (`dokument_art.erkenne`: ein ZIP gilt nur mit `word/document.xml`) |
| PPTX über den RAG-Weg | 57 KB | 1,7 s | 20 105 Zeichen, 30 Überschriften (ohne Kindprozess, aber mit dem Laden von markitdown) |

„Vollständig“ heißt: Die Zeichenzahl entspricht dem Erzeugten (bei 10 Seiten erwartet ≈ 47 600).
Die Marken-Güte kam erst mit der Überarbeitung des Skripts. Ein Probelauf (PDF 3 Seiten, DOCX 50
Absätze, PPTX 3 Folien) fand alle Marken in ihrer Reihenfolge; die großen Läufe sind damit noch
nicht wiederholt.

- **PDF:** Der Text kommt, die Gliederung geht verloren (pdfminer liefert keine `#`). Für Metadaten
  und Themenbaum aus einer KI reicht das meist; für Strukturdokumente, deren Überschriften die
  Gliederung tragen, ist ein besseres Werkzeug (Kestra) im Vorteil.
- **DOCX:** gut, mit Überschriften und Tabellen, und schnell.
- **PPTX:** markitdown kann es; nur die Erkennung der Art im Chat lässt es nicht zu (ZIP mit
  `ppt/presentation.xml` wäre zu ergänzen, mit derselben ZIP-Bomben-Prüfung).
- **Scan:** nur Kestra (OCR).

## P1-b Menge (Umwandlung im Chatbot)

| Lauf | Gesamt | Median je Datei | Durchsatz |
|---|---|---|---|
| 10 × PDF 40 Seiten nacheinander | 131 s | 13,1 s | 4,6 Dateien/min |
| 5 × PDF 120 Seiten nacheinander | 191 s | 36,7 s | 1,6 Dateien/min |
| 6 × PDF 40 Seiten zugleich | 31 s | — | 2 fertig, 4 `ausgelastet` |

Deutung von „6 zugleich“ (die Aufteilung laut Code und einer Simulation mit einem Zehntel der Zeit;
der überarbeitete Skriptlauf, der sie misst, steht noch aus):

- **3 Abweisungen kamen sofort:** `MAX_WARTENDE` ist 3. Ein Lauf und zwei Uploads füllen das, der
  nächste wird sofort abgewiesen.
- **1 Abweisung kam durch `PLATZ_FRIST_S`:** Die dritte wartete von Beginn an auf den Platz und
  wurde nach 20 s abgewiesen, während die erste (bis ~13 s) und die zweite (bis ~26 s) liefen.
- **RAG-Importe im Studio** zählen nicht in `MAX_WARTENDE` und warten ohne Frist auf den Platz.
  Belegen sie ihn, scheitert jeder Chat-Upload nach 20 s; belegt ein Stapel ihn, warten die
  Importe.

Weitere Grenzen:

- **Eine Anfrage trägt keinen Stapel:** Zehn Dateien zu 40 Seiten passen in keine Lesefrist.
- **Die Dateien eines Auftrags** haben heute 30 s je Datei (`auftraege/dateien.FRIST_S`, der
  Kommentar sagt fälschlich „wie beim Upload“) und 60 s insgesamt.
- **Je Backend-Replik ein Platz** (Vorgabe: eine Replik).

## P1-c Weg zum Inhalt nach dem Upload

Nach dem Upload liegen die Dateien privat im persönlichen Bereich der Person. Der Chatbot erreicht
WLO nur über das MCP; einen eigenen REST-Zugang hat er nicht.

- **Bytes über die nodeId:** heute nicht möglich.
  - Das MCP hat kein Werkzeug für Binärdaten.
  - `eduservlet/download` (403) und `GET …/content` (405) liefern die Bytes mit Basic-Anmeldung
    nicht (Messung des MCP, `services/write/batch-manifest.ts`).
  - `get_skill` lädt die Datei einer nodeId als UTF-8-Text herunter, ohne Größengrenze. Das ist ein
    dokumentierter Entscheid für kuratierte Skills (`skills.ts`); `getSkill` prüft aber die
    Inhaltsart nicht — ein Hinweis an das MCP-Team, weil dann eine beliebig große Datei ganz in den
    Speicher geht.
- **Text aus dem Repository** (`get_wlo_content_text` → `/node/v1/nodes/{id}/textContent`):
  - **Anmeldung:** Der Chatbot schickt den Block des Zuges, sonst den der Anlage
    (`services/mcp/auth.py`, `_effective_token`); ohne Block liest das MCP mit seinem Dienstkonto.
    Für Abläufe heißt das: nur mit `has_personal_auth()` und dem Block des Zuges, wie die
    Stapel-Ablage (`mcp_ablage`) — mit einem Test „ohne Anmeldung → kein Aufruf“.
  - **Ungemessen und zweifelhaft:** siehe Kurz.
  - **Grenzen:** 25 s je Aufruf (`WLO_TEXT_TIMEOUT_MS`; gemessen im Median 4,6 s, höchstens
    9,2 s); höchstens 200 000 Zeichen (`maxChars`). Das ist dieselbe Grenze, die ein Teil im Vorgang
    nach dem Vorbild `auftraege/dateien` hätte; Werkzeuge sehen davon höchstens 64 000 Bytes.
  - **Zustände:** `text_unreadable` und eine abgelaufene Anmeldung sind vorübergehend;
    `access_denied` heißt „keine Rechte“; `not_extracted` heißt „Datei da, noch kein gespeicherter
    Text“ — bei Markdown, JSON und Bildern regelmäßig endgültig, **direkt nach einem Upload
    vielleicht nur „noch nicht“** (bis die Messung aus Punkt 5 es klärt, als vorläufig werten);
    `truncated` heißt gekürzt.
  - Dazu `node_not_found` (etwa nach `erneut` oder einem gelöschten Knoten) und `no_text_no_url`
    (Datei ohne Größe, etwa ein unfertiger oder `unverified` Upload).
  - **Zwischenspeicher:** `use_cache=False` liest den Werkzeug-Cache nicht, **schreibt das Ergebnis
    aber hinein** (`services/mcp/client.py`). Der Schlüssel trägt das Kennzeichen der Person (kein
    Leck an andere). Die Größengrenze (`MCP_TOOL_CACHE_MAX_ENTRY_CHARS`, Vorgabe 1 Mio. Zeichen)
    liegt über den höchstens 200 000 Zeichen — **jeder Text wird also gespeichert**, 5 min lang. Auch
    die Fehlanzeigen (`text_unreadable`, ein vorläufiges `not_extracted`) sind kein Werkzeugfehler
    und landen im Cache: Eine Wiederholung mit der Vorgabe spielte 5 min das alte „noch nicht“ ab.
    **Pflicht für E/F:** `get_wlo_content_text` auf die Sperrliste (`tool_cache._TOOL_CACHE_BLOCKLIST`).
  - `get_wlo_content_text` steht noch nicht in `ablauf/werkzeuge.LESENDE_MCP`.

## Was für jeden Weg gilt, auf dem der Chatbot Texte hält (B–F)

Bei A bleiben große Ausgaben nach D8 in Kestra; der Teil hält einen Verweis, moderiert wird beim
Lesen (wie `dateien_holen`). Für B–F gilt:

- **Aufbewahrung:** Ein Dokument im Chat gilt heute 24 h nach der letzten Nutzung (höchstens 72 h,
  `aufbewahrung_h`);
  seine Teile im Vorgang gehen mit ihm (`vorgaenge.dokument_teile_entfernen`). Texte in
  `wlo.texte@1` lägen dagegen unter der **Frist des Vorgangs**: 3 Tage, bei einem wartenden
  Auftrag 8 bis 30 Tage. Das wäre länger als heute — **ein eigener Entscheid**, etwa die Frist der
  Texte an `aufbewahrung_h` zu binden.
- **Moderation und Fremdtext:** Jeder Text ist Fremdtext.
  - Je Text eine Moderation wie `auftraege/dateien`; `pruefung_fehlt` ist vorübergehend.
  - Den Schlüssel für die Moderation liefert der Zug; ein Hintergrund-Job hat keinen. Bei
    `B_API_KEY_MODE=forward` gäbe es dort keine Moderation, sonst rechnete sie über die Anlage ab.
  - Ein Rahmen als Fremdtext; die KI bekommt nur Kurztexte (Plan D8).
- **Zurückschreiben ins Repository:** Das MCP verweigert einen Volltext auf einem Knoten mit Datei
  (`fulltext.ts`, `FULLTEXT_KEEPS_BINARY = false` → `would_replace_file`). Texte aus dem Chatbot
  kommen also nicht ans Repo; Kestra schreibt sie dort selbst. Folgeschritte, die nur den Teil
  `wlo.texte@1` lesen, bleiben gleich (D9); `wlo_attach_fulltexts` verhält sich je `ort` verschieden.
- **Größe des Teils:** 200 Dateien mit je 2 Mio. Zeichen passen nicht in einen Teil
  (`teil_setzen` schreibt eine JSONB-Zeile). Je Datei eine Zeile in `vorgang_ablage`, gekürzt auf
  200 000 Zeichen; der Teil trägt nur Verweise und Stände.
- **Wiederaufnahme:** Das automatische Abholen ist kein Hintergrund-Zug, sondern `ui_fortschritt`
  mit `automatisch: true` (`hintergrund_zug.AUTOMATISCH_AKTIONEN` kennt nur
  `ablauf_auftrag_pruefen`). Ein Schritt, der Datei für Datei arbeitet, braucht eine eigene Aktion
  dort und läuft nur, solange das Widget offen und die Anmeldung gültig ist.

## Optionen

**Was vor der Wahl zu klären ist:**

- **Für A, B, C:** Wann gibt es den Extraktions-Flow (Team)? Wie sieht die Übergabe aus (T2)? Und
  wer baut den Themenbaum — der Chatbot (`ui_strukturentwurf` aus einem Dokument) oder Flow-2 in
  Kestra (Team-Skizze §4b)? Bekommt Flow-1 die `structure_node_ids` oder nur die Inhalte?
- **`ort: kestra` hängt an AS-6** (R2: Ausgaben eines Auftrags als typisierte Teile, große per
  Verweis) — nicht nur am Flow.
- **T1 (Upload-Weg) entscheidet nur über D** und darüber, ob B/C überhaupt greifen: Lädt die Person
  in der Inbox über ein edu-sharing-Frontend hoch, sieht der Chatbot die Datei nie.
- **Für E:** die Staging-Messung (Punkt 5).
- **Für F:** ein Byte-Werkzeug des MCP (Punkt 6).

| | Option | Wie | Trägt bei T1 | Kosten und Risiken |
|---|---|---|---|---|
| A | **Kestra für alles** | AS-T nur mit `ort: kestra`. | beide | Wartet auf den Extraktions-Flow (Team), T2 und AS-6; bis dahin keine Umwandlung in Abläufen. Kein Chatbot-Platz, kein Datenschutz-Zusatz. |
| B | **Strukturdokument im Chat, Inhalte über Kestra** | Das eine Strukturdokument (der Upload-Validator erlaubt höchstens eins) wird im Chat umgewandelt (`/api/ui/dokumente`), die Inhalte über Kestra. Zwei Fälle: **B1** — der Chatbot baut den Themenbaum in derselben Sitzung: `modul ui_upload` (Dokument lesen) → `agent`-Schritt mit `ui_strukturentwurf` und `aus_dokument` → Teil `draft`. **B2** — der Text soll als `wlo.texte@1` über das Warten hinaus bleiben. | nur bei Upload im Widget (`ui_upload`) | **B1 geht heute ohne neuen Code:** Ein `agent`-Schritt darf `ui_strukturentwurf` nutzen (Manifest `agent: true`, `pruefung.agent_werkzeug`), und der Dienst liest das Dokument der Sitzung serverseitig (`ui_module/dienst.py`). Es bleiben die Einschränkungen (3) Modul-Reihenfolge und ein Dokument je Sitzung; der Entwurf muss vor dem Kestra-Warten entstehen. **B2 braucht neuen Code:** (1) Kein Ablaufschritt liest heute den Text — der Teil `document` trägt nur einen Verweis, der Text liegt in `dokument_uploads` und ist nur für dieselbe Sitzung und Person lesbar (`dokumente/ablage.aktuelles`); nötig sind ein Auflöser Verweis → Text, der Typ `wlo.texte@1`, eine Kürzung (gespeichert bis 2 Mio. Zeichen) und die Verknüpfung `upload_id` ↔ nodeId (Rolle `struktur`). (2) **Aufbewahrung:** Der Text verfällt 24 h nach der letzten Nutzung — vor dem Ende eines Kestra-Wartens (bis 24 h Job, Vorgang 8–30 Tage); ein zweites Hochladen in der Sitzung ersetzt ihn. Punkt 3 gilt also auch hier. (3) **Modul:** `ui_upload` liest ein Dokument heute nur über den Knopf „Themenbaum aus dem Strukturdokument“, und das schließt die Frage; Lesen und Übertragen gehen in einem Schritt nur in der Reihenfolge „erst übertragen, dann lesen“. Nötig: beides unabhängig von der Reihenfolge mit einem neutralen Ziel (oder zwei Schritte); das Dokument geht zweimal hinaus (Chat und Ablage); Schalter `dokument_im_chat` an. (4) **Verhältnis zu §4b** offen (siehe oben): Baut der Chatbot den Themenbaum, wird Flow-2 umgangen; extrahiert Kestra das Strukturdokument ohnehin, ist die Umwandlung doppelt. Inhalte warten auf A. |
| C | **Kestra, außer Einzeldateien** | Wie B, dazu wenige Einzeldateien im Chat. | nur bei Upload im Widget | Alle Kosten von B, dazu: Der Chat-Weg trägt **ein** Dokument je Sitzung (ein neues löscht das vorige samt Teil, `dokumente/ablage`), und das Modul lädt nur die Datei mit der Rolle `struktur` hoch. Nötig wären mehrere Dokumente je Sitzung (Tabelle, Löschregel, Teil je Dokument) und eine Mehrfachauswahl im Modul; P1-b-Grenzen gelten. |
| D | **Umwandlung beim Stapel-Upload** | Beim Hochladen (`api/ui_ablage.py`) liegt die Datei schon vor (Starlette spoolt Multipart ab 1 MiB auf die Platte, darunter im Speicher, `api/body_limit.py`); eine eigene Kopie in einem 0700-Verzeichnis, umgewandelt mit einer pfadbasierten Variante von `wandle`. | nur MCP-Stapel | **Datenschutz:** eine Rohkopie privater Dateien bliebe liegen, bis der Platz frei ist (heute gilt „die Rohdatei wird nicht gespeichert“, `ui_dokumente`); nach einem Neustart greift kein `finally` → Aufräumen beim Start, Höchstalter, Obergrenze in MB. **Kapazität:** ein Stapel darf 200 Dateien haben (~43 min Platz bei 40 Seiten) — Chat-Uploads scheitern solange nach 20 s, RAG-Importe warten; nötig wären eine niedrigere Stufe nur bei freiem Platz und eine Obergrenze je Stapel. **Architektur:** Ein früherer Schritt (`ui_upload`) zöge Arbeit für einen späteren (`umwandeln`) vor — D9 („umgestellt am Schritt“) wäre zu ändern; offen sind Verzweigungen, Ablaufänderungen dazwischen, die Simulation und der Rückweg ohne Bytes. **Lücken zu `wlo.texte@1`:** Wiederholung eines Index (kein zweiter Versuch), `erneut`/`passt_nicht` (nichts angelegt, Text verwaist), `unverified` (keine nodeId), gleichzeitiges Schreiben am Teil `ablage` (`VorgangKonflikt`), nur 4 von 15 Arten umwandelbar, Verdrängung (`MAX_JE_PERSON` 3). |
| E | **Text aus dem Repository** | `get_wlo_content_text` mit der Anmeldung der Person. | beide | Ungemessen, Gegenmessung (leer); 25 s je Datei, 200 000 Zeichen; der Cache schreibt mit; keine Gliederung. Erst nach einer Staging-Messung tragfähig. |
| F | **Bytes über die nodeId** (D9, wie ursprünglich geplant) | Mit der Lese-Anmeldung der Person die Datei holen, im Chatbot umwandeln, die Bytes verwerfen. | beide | Braucht ein Byte-Werkzeug des MCP (Punkt 6; heute 403/405). Dann: P1-b-Grenzen (ein Platz, Datei für Datei), Aufbewahrung und Moderation wie oben; keine Rohkopie wie bei D, keine Abhängigkeit von der Extraktion des Repositorys wie bei E. Grundlage für Inhalte, solange Kestra fehlt. |

## Empfehlung (vorbehaltlich der Entscheide)

- **Ziel A** (Kestra): Es ist der einzige Weg ohne Chatbot-Platz und ohne Datenschutz-Zusatz;
  er braucht den Flow des Teams, T2 und AS-6.
- **Einen Übergang erst wählen, wenn die Fragen oben beantwortet sind:**
  - **B1** geht heute schon, wenn das Team sagt, dass der Chatbot den Themenbaum baut: Strukturdokument
    im Chat lesen, Entwurf im `agent`-Schritt mit `ui_strukturentwurf` (`aus_dokument`), alles in
    derselben Sitzung vor dem Kestra-Warten. Kein `wlo.texte@1`, keine längere Aufbewahrung.
  - **B2** nur, wenn der Strukturtext über das Warten hinaus gebraucht wird: dann die Arbeiten (1)
    und (3), der Aufbewahrungs-Entscheid (2) und die Antwort auf (4).
  - **F** ist der sauberste Übergang für Inhalte, wenn das MCP-Team ein Byte-Werkzeug liefert.
  - **E** nur nach der Staging-Messung.
- **D nicht:** Rohkopie privater Dateien, Kapazität, Kopplung der Schritte gegen D9 und die Lücken
  zu `wlo.texte@1` wiegen mehr als der Gewinn.
- **Bis dahin** kann AS-T mit `ort: kestra` vorbereitet werden, sobald AS-6 steht und T2
  beantwortet ist; abnehmen lässt es sich erst mit dem Extraktions-Flow. Der Teil `wlo.texte@1` und
  die Prüfung sind für beide Orte gleich.

## Offene Punkte (Entscheide)

1. **Team:** Termin des Extraktions-Flows, T2 (Übergabe), wer den Themenbaum baut (Chatbot oder
   Flow-2), ob Flow-1 die `structure_node_ids` bekommt; T1 (entscheidet über D und darüber, ob
   B/C greifen).
2. **Option für AS-T:** A als Ziel; als Übergang B, C, E oder F (oder keiner) — nach Punkt 1.
3. **Aufbewahrung** der Texte in `wlo.texte@1`: an `aufbewahrung_h` (24 h) gebunden oder die Frist
   des Vorgangs.
4. **PPTX** im Chat-Weg zulassen?
5. **Staging-Messung von E**, mit Testkonto und selbst angelegten, danach entfernten Knoten: Ist
   ein privater Upload (PDF, DOCX, PPTX) über `textContent` mit der Anmeldung der Person lesbar, ab
   wann, in welcher Güte?
6. **An das MCP-Team:** ein Werkzeug für die Bytes einer privaten Datei (welcher Endpunkt mit Basic
   oder Ticket?) — Voraussetzung für F; der Hinweis zu `getSkill`.
7. **Messung auf dem vServer**, außerhalb der Betriebszeit: Das Image enthält `backend/scripts`
   nicht — ein eigener Container aus demselben Image mit eingebundenem Skript, nicht im laufenden
   Backend; dazu ein echtes Lehrplan-PDF.
8. **Frist der Auftragsdateien** (`auftraege/dateien.FRIST_S` 30 s gegen 60 s beim Upload).

## Review 1 (Befundhebung)

Erstes Review gegen D9 und am Quelltext von Chatbot und MCP. Ergebnis: 0 kritisch, 5 schwer,
9 kleiner, 2 Kleinigkeiten.

| # | Befund | Schwere | Stand nach Fassung 3 |
|---|---|---|---|
| 1 | Ohne Anmeldung liest das MCP mit dem Block der Anlage oder dem Dienstkonto. | schwer | Behoben (P1-c, Pflicht und Test). |
| 2 | Der Text aus dem Repository stand als Tatsache da. | schwer | Behoben (ungemessen, Option E erst nach Messung). |
| 3 | Der Weg zu den Bytes war falsch begründet. | schwer | Behoben (P1-c). |
| 4 | Fristen und Grenzen des Repository-Texts fehlten. | schwer | Behoben (P1-c). |
| 5 | Moderation und Fremdtext fehlten. | schwer | Behoben („Was für jeden Weg gilt, auf dem der Chatbot Texte hält“). |
| 6 | Deutung „6 zugleich“ unvollständig. | kleiner | Behoben (Fassung 3 auch die Erzählung, siehe Review 2, Befund 7). |
| 7 | „300 Seiten“ zu allgemein. | kleiner | Behoben (dichter Satz). |
| 8 | Kerne auf dem vServer. | kleiner | Behoben. |
| 9 | „Derselbe Code wie ein Upload“. | kleiner | Behoben. |
| 10 | Wiederaufnahme falsch benannt. | kleiner | Behoben. |
| 11 | Grenzen der Optionen vermischt. | kleiner | Behoben (Optionen getrennt). |
| 12 | Datenschutz und Aufbewahrung fehlten. | kleiner | In Fassung 2 falsch behoben, in Fassung 3 berichtigt (Review 2, Befund 1). |
| 13 | Die Güte prüfte nur den Wortschatz. | kleiner | Werkzeug behoben; die großen Läufe sind noch nicht wiederholt. |
| 14 | Docstring und Weg auf den vServer. | kleiner | Behoben. |
| 15 | `direkt()` ohne `finally`. | Kleinigkeit | Behoben; die Erklärung der 2 s in Fassung 3 berichtigt. |
| 16 | „Ein Platz“ je Replik. | Kleinigkeit | Behoben. |

## Review 2 (zweites, unabhängiges Review)

Nach den 5 schweren Befunden von Review 1. Ergebnis: 0 kritisch, 6 schwer, 6 kleiner,
3 Kleinigkeiten, dazu 1 vorbestehender Befund. Der Messteil trug; die Empfehlung (damals Weg C =
heute Option D) nicht.

| # | Befund | Schwere | Behebung in Fassung 3 |
|---|---|---|---|
| 1 | Zwei falsche Datenschutz-Aussagen: `use_cache=False` schreibt doch in den Cache; die Texte lägen länger als heute (Vorgangsfrist statt 24 h). | schwer | Berichtigt; Aufbewahrung als eigener Entscheid (Punkt 3). |
| 2 | Weg C falsch beschrieben: Die Datei liegt schon gespoolt auf der Platte, kein Strom; eine Warteschlange von Rohkopien widerspricht „die Rohdatei wird nicht gespeichert“. | schwer | Option D richtig beschrieben, mit Rohkopie als Datenschutz-Kosten. |
| 3 | Keine Grenze über Läufe hinweg; ein Stapel blockiert Uploads und RAG-Importe. | schwer | In Option D und P1-b. |
| 4 | Weg C koppelt einen früheren an einen späteren Schritt — gegen D9. | schwer | In Option D; D wird nicht empfohlen. |
| 5 | Lücken zwischen Weg C und `wlo.texte@1`. | schwer | In Option D und „Was für jede Option gilt“. |
| 6 | Entscheide nicht vollständig und nicht neutral; es fehlte die einfachere Option „Strukturdokument im Chat“; T1 gehört zuerst; das Zurückschreiben unterscheidet sich je Ort. | schwer | Vergleich A–E, T1 zuerst, Empfehlung erst danach (B). |
| 7 | Erzählung „die dritte wartete ab 20 s“ falsch. | kleiner | Berichtigt. |
| 8 | DOCX zeigte 39 statt 40 Überschriften (Zählfehler im Skript). | kleiner | Notiz und Skript berichtigt (`_ueberschriften` zählt jede Zeile mit `#`). |
| 9 | Erklärung der ~2 s falsch. | kleiner | Berichtigt (Kindprozess ~0,6 s + markitdown). |
| 10 | `assert` im Skript bricht die vServer-Messung ab. | kleiner | Behoben: Fehler je Datei werden gezählt, die Messung läuft weiter. |
| 11 | Vergleich „200 000 gegen 2 Mio.“ trug nicht. | kleiner | Gegen die Grenze des Teils gestellt. |
| 12 | Hinweis zu `get_skill` ohne den dokumentierten Entscheid. | kleiner | Mit Verweis auf den Entscheid formuliert. |
| 13–15 | Markenformat, Pfad, „vorläufig, nach den Entscheiden“. | Kleinigkeit | Berichtigt. |
| vorbestehend | `umwandlung._wartende` sinkt bei Abbruch sofort, der Kindprozess hält den Platz weiter. | kleiner | In den offenen Befunden. |

## Review 3 (drittes, unabhängiges Review)

Nach den 6 schweren Befunden von Review 2. Ergebnis: 0 kritisch, 6 schwer, 4 kleiner,
2 Kleinigkeiten. Die Befunde aus Review 2 waren behoben (Nr. 6 nur teilweise); neu fielen die
Kosten von B und C und eine fehlende Option auf.

| # | Befund | Schwere | Behebung in Fassung 4 |
|---|---|---|---|
| 1 | B „kaum neuer Code, vorhandener Weg“: Kein Schritt liest heute den Text; Verweis statt Text, sitzungsgebunden, keine nodeId. | schwer | Die vier Arbeiten in der Tabelle. |
| 2 | B „24 h“ als Vorteil: Der Text verfällt vor dem Ende eines Kestra-Wartens. | schwer | Als Kosten genannt; Punkt 3 gilt auch für B. |
| 3 | B: Das Modul schließt Lesen und Übertragen fast gegenseitig aus. | schwer | Als Kosten genannt (Modul, doppelte Übertragung, Schalter). |
| 4 | B: Verhältnis zu Flow-1/Flow-2 (§4b) offen. | schwer | Als Frage vor der Wahl (Punkt 1). |
| 5 | C: Der Chat-Weg trägt ein Dokument je Sitzung. | schwer | Als Kosten genannt. |
| 6 | Option F (Bytes über die nodeId, D9 wie geplant) fehlte. | schwer | Zeile F; Punkt 6 als Voraussetzung. |
| 7 | „T1 zuerst“ falsch gewichtet. | kleiner | T1 nur für D und B/C-Greifen; die eigentlichen Vorfragen zuerst. |
| 8 | `ort: kestra` hängt an AS-6 (R2) und T2. | kleiner | In A und den Vorfragen; Plantabelle AS-T angepasst. |
| 9 | Der allgemeine Teil belastete A ungleich. | kleiner | Auf B–F begrenzt; ein Satz zu A. |
| 10 | `not_extracted` direkt nach dem Upload vielleicht nur vorläufig; `access_denied` fehlte. | kleiner | Ergänzt. |
| 11 | Spooling erst ab 1 MiB. | Kleinigkeit | Berichtigt. |
| 12 | Cache-Schlüssel je Person, Größengrenze. | Kleinigkeit | Ergänzt. |

Die Empfehlung ist jetzt bewusst schmal: A als Ziel; einen Übergang erst nach den Vorfragen.


## Review 4 (viertes, unabhängiges Review)

Nach den 6 schweren Befunden von Review 3. Ergebnis: 0 kritisch, 2 schwer, 3 kleiner,
2 Kleinigkeiten; die zwölf Befunde von Review 3 waren bearbeitet (Nr. 1 überkorrigiert, Nr. 7/8
nur in der Notiz). Laut Review trägt die Notiz nach diesen Korrekturen als Entscheidungsgrundlage.

| # | Befund | Schwere | Behebung in Fassung 5 |
|---|---|---|---|
| 1 | „Kein Ablaufschritt liest heute den Text“ stimmt nicht: Ein `agent`-Schritt mit `ui_strukturentwurf` (`aus_dokument`) liest das Dokument der Sitzung. | schwer | B geteilt in B1 (heute vorhanden, sitzungsgebunden) und B2 (neuer Code); Empfehlung darauf bezogen. |
| 2 | Der Plan beschrieb D9, Z. 14 und AS-T noch nach der Annahme von vor P1. | schwer | Plan nachgezogen (Z. 14, D9, P1-c-Satz, AS-T, T1). |
| 3 | Voraussetzungen von `ort: kestra` an drei Stellen verschieden. | kleiner | Überall AS-6, T2 und der Flow. |
| 4 | Plan T1 „dem Ablauf egal“ — für `umwandeln` nicht. | kleiner | Plan T1 ergänzt. |
| 5 | Zustände `node_not_found`, `no_text_no_url`; Fehlanzeigen liegen 5 min im Cache. | kleiner | Ergänzt; Sperrliste als Pflicht für E/F. |
| 6 | Verweise auf den umbenannten Abschnitt. | Kleinigkeit | Angepasst. |
| 7 | „Die vier Arbeiten“ ungenau. | Kleinigkeit | Mit B1/B2 neu gefasst. |
