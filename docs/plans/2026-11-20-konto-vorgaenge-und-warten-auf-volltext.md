# Plan: Konto-Knopf, „Meine Vorgänge“, Warten auf den Volltext, Vorgang ohne Anmeldung (2026-11-20)

Auslöser: Rückmeldung des Nutzers am 20.11. nach dem Test von PR #91 auf Staging („OCR mit PDF klappt
und Themenbaum war gut – toll!“) mit vier Punkten.

## 1 Befunde

| # | Rückmeldung | Stand im Code |
|---|---|---|
| R1 | Der Kürzel-Kreis ist kleiner als die anderen Knöpfe; Kreis und Anmelde-Knopf zu einer Funktion zusammenlegen | Zwei Elemente: `span.konto-kuerzel` (28 px, nur Anzeige) und `button.btn-auth` (`shell/chat-shell.component.html` ~351–390) |
| R2 | „Meine Vorgänge“ sieht aus wie „Neues Gespräch“ | Beide sind kreisförmige Pfeile: `ICONS.restore` (Vorgänge) und `ICONS.refresh` (Neustart) |
| R3 | Ohne WLO-Anmeldung folgte der Ablauf in einen neuen Thread — wie wird er zugeordnet? | Laut Code darf das nicht sein: Ohne Anmeldung gehört ein Vorgang `sitzung:{session_id}` (`services/arbeitsstand.aufrufer_fuer`); „Neues Gespräch“ erzeugt eine neue Kennung (`shell/lifecycle.ts`, `generateSessionId`); „Fortsetzen“ und „Meine Vorgänge“ fragen nur angemeldet (403 `nur_angemeldet`, `api/ui_vorgaenge.py`). → **Fehler, nachstellen** (F) |
| R4 | Nach „In WLO ablegen“ muss man immer wieder „nochmal“ schreiben, es dauert lange; Status halten, Eingabe sperren, selbst nachfragen; prüfen, ob Kestra klappt | Auf dem **Dokument-Weg läuft kein Kestra-Flow** (Seed `themenbaum.yaml`: `dokument_laden` → `dokument_gelesen` → … → `entwurf_dokument`; ein Auftrag `metadaten` nur auf dem Datei-Weg). Gewartet wird auf die **Volltext-Erzeugung des Repositorys**; `entwurf_dokument` meldet `volltext_fehlt_datei` und bittet um „nochmal“ (Paket K5, E14). Die Beschriftung „In WLO ablegen und erschließen“ verspricht auf diesem Weg mehr, als geschieht. |

## 2 Entscheide

- **E-D1 (Konto-Knopf):** Ein Knopf in derselben Größe wie die übrigen Knöpfe der Fußzeile.
  - Abgemeldet: Umriss einer Person, ausgegraut, gestrichelter Rand; Klick öffnet die Anmeldung (wie
    heute `btn-auth`). Name „Anmelden – nicht angemeldet“.
  - Angemeldet: Initialen (ohne Namen: gefülltes Personen-Symbol); Klick öffnet ein kleines Menü
    („Angemeldet als …“, „Abmelden“), Tastatur (Enter/Leertaste öffnet, Pfeile, Esc schließt, Fokus
    zurück), `aria-haspopup="menu"`, `aria-expanded`. Abmelden wie heute.
  - Der getrennte Anzeige-Kreis entfällt. Kontrast und Zielgröße wie die Nachbarknöpfe.
- **E-D2 („Meine Vorgänge“):** eigenes Symbol (Prozess/Liste mit Häkchen, z. B. Material „pending_actions“
  bzw. ein selbst gezeichnetes Symbol im Raster der übrigen), dazu eine kleine Zahl (offene Vorgänge in
  anderen Gesprächen, aus `/api/ui/vorgaenge/liste`, beim Öffnen und nach der Anmeldung geholt) und eine
  farbige Markierung, wenn im aktuellen Gespräch ein Auftrag oder eine Wartezeit läuft. Zahl mit
  Text-Alternative („3 offene Vorgänge“).
- **E-E (Warten auf den Volltext):** Liefert WLO den Volltext eines Strukturdokuments noch nicht
  (`not_extracted`, gerade hochgeladen), hält der Ablauf am Schritt in einem Wartezustand wie beim
  Kestra-Auftrag (`warten: gesperrt`): `ui_fortschritt` zeigt „Der Text aus ‚…‘ wird in WLO erzeugt“,
  fragt selbst in wachsenden Abständen nach (Volltext-Stand des Dokuments über den MCP), Knöpfe „Stand
  prüfen“, „Ohne Dokument weiter“ (anderer Weg) und „Abbrechen“; sobald der Text da ist, geht es ohne
  Zutun der Person weiter zum Entwurf. Obergrenze der Wartezeit nach der Messung (M). Die Beschriftung
  im Upload-Feld nennt auf dem Dokument-Weg nur „In WLO ablegen“ (kein „erschließen“), solange dort kein
  Flow läuft.
- **E-F (Fehler R3):** erst nachstellen (Phase 1 des Debuggens), dann beheben. Erwartung des Nutzers
  und der Spec: ohne Anmeldung folgt kein Vorgang in ein neues Gespräch.
- **M (Messung vor E):** auf Staging mit dem Testkonto (nur gegen die Staging-Hosts, nie am MCP):
  eine Text-PDF im eigenen Bereich ablegen (REST), den Volltext-Endpunkt in Abständen abfragen, bis Text
  da ist (Dauer messen; drei Dateien: Text-PDF klein/groß, Word); Knoten danach löschen. Dazu prüfen, ob
  der Metadaten-Flow `edusharing.chatbot/node-metadata-write` auf Staging derzeit läuft (über den
  Repository-Proxy, eigener Knoten, Metadaten-Schreiben ist erlaubt), und wie lange.

## 3 Pakete

- **D (UI, ein PR mit E oder eigener):** D1 Konto-Knopf (`shell/chat-shell.component.{ts,html}`,
  `_chat-footer.scss`, neues kleines Menü, i18n, Specs, E2E `auth-button.spec.ts`), D2 Vorgänge-Symbol
  und Zähler (`icons.ts`, Shell, `meine-vorgaenge`, i18n, Specs). Schritt 0: `/better-coding-workflow`
  + `/better-coding-frontend`.
- **F (Fehler):** `/better-coding-debug` — Nachstellen gegen Wegwerf-DB: anonym Ablauf starten,
  „Neues Gespräch“, Leiste/Antworten/Kennungen prüfen; Ursache, Test, Behebung.
- **M → E:** Messung, dann Plan-Nachtrag mit Abständen/Obergrenze, dann Umsetzung
  (`services/ablauf/` Wartezustand, Endpunkt für den Volltext-Stand, `ui_fortschritt`, Seeds,
  Upload-Beschriftung).

Je Paket: Review(s) nach der Regel (ab 2 MAJOR oder 1 CRITICAL zweite Runde), volle Suite, E2E,
Durchtest, Notiz unter `docs/aenderungen/`.

## 4 Abnahme

- D1: ein Knopf, gleich groß wie „Vollbild“; abgemeldet → Klick öffnet Anmeldung; angemeldet → Menü
  mit „Abmelden“, Tastatur und Vorleser; kein zweiter Kreis.
- D2: Vorgänge-Symbol klar anders als Neustart; Zahl stimmt mit der Liste; Markierung bei laufendem
  Auftrag.
- F: Test belegt — anonym, „Neues Gespräch“ → kein alter Vorgang, keine Leiste.
- E: Dokument in WLO abgelegt, Text noch nicht da → Eingabe gesperrt, Stand wird selbst geholt,
  Entwurf entsteht ohne „nochmal“, sobald der Text da ist; Obergrenze und Auswege funktionieren.

## 5 Nachtrag (20.11.): Paket G — Werks-Seeds bereinigen, Führung 1:1

Auftrag des Nutzers: „bereinige danach auch die werkseeds – es bleibt nur der neue themenbaum-ablauf drin der
alle usecases umfasst – die anderen alten abläufe für jeden usecase einzeln aus den seeds rausnehmen wenn
diese nicht mehr gebraucht werden. die webseitenführung in den abläufen entspricht text,
schnellantwortbuttons und verzweigung auch noch nicht der ursprünglichen führung – es sollte eine 1 zu 1
kopie sein – aber mit dem ablauf baukasten.“

- **G1 (Seeds):** aus `backend/seeds/06-ablaeufe/` entfallen `themenbaum_aus_dokument.yaml`,
  `themenbaum_aus_inhalten.yaml`, `themenbaum_aus_thema.yaml`, `sammlungsstruktur.yaml` (alle ab Werk
  aus, vom generischen `themenbaum.yaml` abgedeckt). Es bleiben `themenbaum.yaml`, `fuehrung.yaml`,
  `sammlung_pruefen.yaml` (kein Themenbaum-Fall). Vorher prüfen: Verweise (andere Seeds, Ziele,
  Auslöser, Master-Skill-Texte, Studio, Doku, Tests), Verhalten des Werksabgleichs bei einem Bereich,
  dessen Seed fehlt (Werksfassung bleibt? verwaist? eigene Fassung einer Anlage bleibt erhalten) —
  Entscheid: eigene Fassungen in Anlagen nie still löschen; Werksfassung eines entfernten Seeds
  verschwindet bzw. wird als „entfernt“ angezeigt (je nach vorhandenem Mechanismus).
- **G2 (Führung 1:1):** die alte Webseiten-Tour (Quelle: Tour-Konfiguration/State-Machine der Begrüßung,
  vgl. `scripts/fuehrung_aus_tour.py`) Schritt für Schritt gegen `06-ablaeufe/fuehrung.yaml` vergleichen
  — Texte wörtlich, Schnellantwort-Knöpfe (Beschriftung, Reihenfolge, Ziel), Verzweigungen, Seiten-
  wechsel. Abweichungen in einer Tabelle; danach den Generator bzw. Seed so korrigieren, dass der Ablauf
  eine 1:1-Kopie im Ablauf-Baukasten ist (fehlt dem Baukasten eine Fähigkeit, im Plan nachtragen und
  bauen). Test: Abgleich Tour ↔ Ablauf als automatischer Test.

  **Befund G2 (Durchtest Tour ↔ Ablauf, Wegwerf-DB, 16 Wege, 53 Züge):** Texte, Chips und Ziele
  der Hauptwege sind gleich (47 Züge); abweichend sind vier Fälle, die der Baukasten nicht kann:
  - **G2a — Antwort-Chip als Text** (`text_antworten` am Schritt mit `optionen`): ein Chip, der wie
    getippt zählt. Die Tour zählt „Bin mir nicht sicher“ als Fehlversuch (erst Hilfetext, beim
    zweiten Mal Ende → gewöhnlicher Chat); der Ablauf hatte dafür eine Option mit eigenem Schritt
    `unsicher`, der den Hilfetext endlos wiederholte. Der Chip ist ein Wahl-Chip mit der
    reservierten Wahl `_text` (übersteht jeden Deckel); der Vorlauf macht daraus getippten Text,
    nie an der Frage eines anderen Laufs (Review G2).
  - **G2b — Wendung an der Frage einer Führung** (`endet_bei_text`): eine Wendung desselben Ablaufs
    an einer Frage ohne Freitext ist getippter Text (Hinweis `kein_treffer`, dann Ende) — wie die
    Tour im Gruppen-Schritt; sonst bleibt „Du bist schon mitten in …“ (Paket K).
  - **G2c — Tour-Chip der Begrüßung = Knopf**: ist die eingebaute Tour aus, startet ein Druck auf
    den Tour-Chip (`tour_action: start`) den Ablauf mit dem Merkmal `tour_chip` wie sein Knopf (wartet
    ein anderer, erst die Rückfrage; Review G2) — ein
    wartender Lauf desselben Ablaufs beginnt neu an der aktuellen Seite (die Tour startet neu; der
    Ablauf zeigte den alten Schritt erneut).
  - **G2d — Frage nach Seitenwechsel**: wartet eine Führung (Ablauf mit `seite`-Schritt) an einer
    Frage, pingt das Widget nach einem Seitenwechsel auch dort und öffnet sich; der Ping zeigt die
    Frage samt Chips erneut, ungespeichert — wie der Tour-Tick im Gruppen-Schritt.
  - **Review G2 (Nachtrag):** `text_erneut` am `seite`-Schritt — eine Wendung zeigt den wartenden
    Schritt wie die Tour neu gerendert (Einstieg bei den Lösungen → Lösungen-Text).
  Gewollte Unterschiede bleiben: relative Pfade statt `base_host`, Ablauf-Leiste, kein Etikett
  „KI-generiert“. Notiz: `docs/aenderungen/2026-11-20-paket-g2-fuehrung-1zu1.md`.

## 6 Nachtrag (20.11.): Ergebnis F und Entscheid

Phase 1 (Notiz folgt mit der Behebung): **Ohne Anmeldung folgt kein Lauf** (nachgestellt per API und
Browser gegen Wegwerf-DB). Der Nutzer war angemeldet („In WLO ablegen“ verlangt die Anmeldung, 403
sonst). „Neuer Chat“ (`restart()`) lässt den Zugangsblock liegen; im ersten Zug holt
`arbeitsstand.auffrischen()` per `vorgaenge.juengster()` den jüngsten offenen Vorgang der Person in die
neue Sitzung (Review V1, Befund 1), und ein anonym begonnener Lauf gehört nach der Anmeldung der Person
(`anonymen_uebernehmen`). **Nebenbefund (schwer):** Die erste Nachricht des neuen Gesprächs wird still
als Freitext-Antwort auf die offene Frage des alten Laufs gespeichert.

**Entscheid E-F (ersetzt V1, Befund 1):** Ein neues Gespräch übernimmt einen Vorgang nie still. Den
Zweig `juengster` in `auffrischen` entfernen; die Wiederaufnahme läuft nur über „Fortsetzen“ (Hinweis
erscheint schon) und „Meine Vorgänge“. Zusätzlich als Sicherung: Eine Nachricht zählt nie als Antwort
auf eine Frage, die in einer anderen Sitzung gestellt wurde. Tests: neue Sitzung mit Anmeldung → kein
Lauf, „Fortsetzen“ angeboten; Wechsel über „Fortsetzen“ → Lauf da; Durchtest K (`tests/
test_preflight_node.py:1074`) entsprechend anpassen.

**Umgesetzt (20.11., Änderungsnotiz `docs/aenderungen/2026-11-20-paket-f-kein-stilles-uebernehmen.md`):**
`juengster` fällt in `arbeitsstand.auffrischen` **und** in `arbeitsstand._speichern` weg (ein Teil aus
einem neuen Gespräch landete sonst still im jüngsten Vorgang und holte ihn samt Lauf herein); der
Rückgriff R1-d in `ui_auftrag._wartender_auftrag` ebenso; `/api/ui/vorgaenge/offen` schließt den
Vorgang eines Verweises nicht mehr aus. Sicherung in `wahl_zug._fortsetzen`: die Frage gilt nur dem
Gespräch, in dem der Lauf zu warten begann (`vorgaenge.session_id`, gesetzt von
`zug_basis.festhalten`). Durchtest K: nur Docstring (das Verhalten an der Frage bleibt).

## 7 Nachtrag (20.11.): Ergebnis der Messung M

Staging, Testkonto, direkt REST (nicht am MCP), eigene Knoten danach endgültig gelöscht:
- Das Repository erzeugt den Volltext **synchron beim ersten** `GET …/textContent` (Automobilkaufleute
  223 KB: 0,4 s nach dem Upload, 58 410 Zeichen; Augenoptiker 0,4 s; 8-MB-PDF 10,5 s); vorher
  `200 {"text": null}`; danach setzt es `ccm:fulltext_status` (`CONTENT_AVAILABLE`, `NO_CONTENT` bei PDF
  ohne Textebene, `TRANSFORM_ERROR_UNSUPPORTED` bei .md). Im Hintergrund nach dem Upload passiert nichts.
- `not_extracted` ist damit **endgültig** (Scan, Markdown), kein Zwischenstand. Vorübergehend ist nur
  `text_unreadable` (erstes Lesen länger als `WLO_TEXT_TIMEOUT_MS` oder 5xx).
- Kestra `edusharing.chatbot/node-metadata-write` läuft auf Staging (202 → SUCCEEDED in 13,2 s, acht Felder).
  Für den Flow-Autor: die jobId steht im Klartext in `ccm:version_comment` am Knoten (lesbar für alle mit
  Leserecht), und der Flow überschreibt den Titel der Person.

**Folge für E-E:** Ein langer Wartezustand mit Abfrage ist die falsche Antwort. Die Meldung „Text wird gerade
erzeugt“ beim Nutzer (Text-PDF) passt nicht zur Messung → Ursache in der Kette Chatbot → MCP → Repository
suchen (Phase 1 läuft, R4). E-E wird nach dem Befund neu gefasst: `not_extracted` sofort ehrlich („kein
lesbarer Text“ + „Ohne Dokument weiter“/„Hier im Chat lesen lassen (OCR)“), nur `text_unreadable` kurz
selbst nachfragen (5/10/20 s, dann 30 s, Obergrenze 3 min) mit gesperrter Eingabe.

## 8 Nachtrag (20.11.): Ursache R4 und neues Paket E

**Ursache (Phase 1, Staging, belegt):** Am Knoten des Nutzers (`automobilkaufleute-2016-09-16.pdf`, über den
MCP abgelegt) steht `ccm:fulltext_status = TRANSFORM_ERROR_INTERNAL` — die Extraktion des Repositorys ist
beim ersten Lesen intern gescheitert und wird nie wiederholt (`GET …/textContent` antwortet sofort
`{"text": null}`; `forceUpdate=true` nur für Admins). Der MCP liest den Status nicht
(`src/services/content-text.ts:164, 244-248`) und meldet `not_extracted`; der Chatbot zählt `not_extracted`
zu `SPAETER` (`services/dokumente/strukturdokument.py:61`) und rät zu „nochmal“ (`ui_module/dienst_fehler.py`
`volltext_fehlt_datei`) — das hilft nie. Sieben Nachspiele des MCP-Wegs lieferten sofort Text; der Auslöser
liegt im Repository (Transformer-Logs nötig). Auf dem Dokument-Weg läuft kein Kestra-Flow.

**Paket E (ersetzt E-E aus §2):**
- **E1:** `not_extracted` bei WLO-Strukturdokumenten ist endgültig: nicht mehr in `SPAETER`; neuer Satz
  „WLO konnte aus ‚…‘ keinen Text gewinnen“ mit den Auswegen „Hier im Chat lesen lassen“ (Upload-Feld mit
  Ort Chat — dort greift auch die Texterkennung) und „Ohne Dokument weiter“; der Ablauf bleibt nicht in einer
  „nochmal“-Schleife.
- **E2:** nur `text_unreadable`/`abruf_fehler`/`frist` sind vorübergehend: der Server versucht im selben Zug
  selbst noch ein-, zweimal (nach ~5 s und ~10 s, innerhalb der Frist), bevor er „gleich nochmal“ sagt — kein
  langer Wartezustand nötig (Messung §7: erstes Lesen ≤ 10,5 s bei 8 MB).
- **E3:** Beschriftung im Upload-Feld auf dem Dokument-Weg „In WLO ablegen“ (ohne „erschließen“), solange dort
  kein Flow läuft.
- **E4:** Rückmeldung an den MCP-Entwickler `docs/mcp-rueckmeldung-2026-11-20-volltext-status.md`:
  `ccm:fulltext_status` in `NODE_PROPS`, neues optionales Feld `extractionStatus` (bzw. eigener Grund
  `extraction_error`), zu klären: bestätigtes Werkzeug „Extraktion neu anstoßen“ für eigene Knoten (Status-
  Eigenschaft löschen, dann `textContent` lesen — gemessen: stellt den Text wieder her). Dazu an den
  Flow-Autor: jobId im Klartext in `ccm:version_comment`; Titel wird überschrieben.
- Sobald der MCP `extractionStatus` liefert: nach Status unterscheiden (später, eigenes Paket).
