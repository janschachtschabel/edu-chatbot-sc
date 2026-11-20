# Paket E: Der Volltext aus WLO ehrlich (2026-11-20)

Plan: `docs/plans/2026-11-20-konto-vorgaenge-und-warten-auf-volltext.md` §7 (Messung) und §8 (Ursache R4,
Paket E, ersetzt E-E aus §2). Keine Migration, keine neue Variable. Widget-Bau nötig (E3).

## Befund

Auf dem Dokument-Weg („In WLO ablegen“) bat der Chatbot bei `not_extracted` immer wieder um „nochmal“
(Paket K5, E14). Gemessen (§7) erzeugt das Repositorium den Text synchron beim ersten Lesen und
wiederholt eine gescheiterte Extraktion nie (`ccm:fulltext_status = TRANSFORM_ERROR_INTERNAL` sitzt
fest). „Nochmal“ half deshalb nie. Auf dem Dokument-Weg läuft außerdem kein Flow, die Beschriftung
„In WLO ablegen und erschließen“ versprach mehr, als geschieht.

## Änderung

- **E1 — `not_extracted` ist endgültig.**
  - `services/dokumente/strukturdokument.py`: `not_extracted` fällt aus `SPAETER` (bleibt:
    `text_unreadable`, `abruf_fehler`, `frist`).
  - `ui_module/dienst_fehler.py`: der Satz `volltext_fehlt_datei` („gerade erzeugt … nochmal“) ist
    ersetzt durch `volltext_endgueltig`: WLO konnte keinen Text gewinnen, kein neuer Versuch, die
    Auswege „Hier im Chat lesen lassen“ (dort Texterkennung) und „Ohne Dokument weiter“; im Ablauf
    führt „Weiter im Ablauf“ zu beiden. Der Satz im gemischten Fall (`ohne_volltext`) nennt den
    Ausweg statt „entsteht er gerade“.
  - `ui_module/dienst.py`: eigener Code im Ergebnis, `ToolOutcome.error = "volltext_endgueltig"`
    (die übrigen Fälle bleiben `volltext_fehlt`).
  - Seed `06-ablaeufe/themenbaum.yaml`: `entwurf_dokument.bei_fehler` → neuer Schritt
    `ohne_dokumenttext` (39 von 40 Schritten) mit den Knöpfen „Dokument hier im Chat lesen lassen“
    (→ `dokument_laden`, verwirft `structure`, `document`/`strukturdokument`, `metadaten`), „Ohne
    Dokument weiter“ (→ `grundlage`, verwirft dazu `grundlage`), „Nochmal versuchen“ (→ `zum_entwurf`,
    für andere Fehler wie „ausgelastet“) und „Frei weiter“. Selbsttest „Dokument nicht gelesen,
    nochmal“ geht jetzt beide Auswege (höchstens 20 Selbsttests — darum kein neuer Fall).
- **E2 — vorübergehende Gründe im selben Zug wiederholen.** `strukturdokument._wlo_lesen`: bei
  `text_unreadable`/`abruf_fehler` noch zwei Versuche nach 5 s und 10 s (`WIEDERHOLEN_S`), nur wenn
  die Pause vor der Frist der Lesung endet (30 s bzw. `frist_ende`); in der Pause hält der Knoten
  keinen der drei Plätze. Bricht die Frist einen Versuch ab, bleibt der letzte Grund stehen.
  Endgültige Gründe (`not_extracted`, `access_denied`, `node_not_found`, `ohne_anmeldung`) werden nie
  wiederholt.
- **E3 — Upload-Feld ohne „erschließen“, wo kein Flow folgt.** `ui-upload/upload-orte.ts`: `Orte`
  trägt `nurAblegen`, wenn der Block `einzeldatei_als_struktur` hat (Dokument-Weg).
  `upload-orte-ansicht.ts`: `ortName` — der WLO-Ort heißt dann „In WLO ablegen“ / “Store in WLO”,
  auch gesperrt; Erklärzeile „… nur ablegen; den Text liest der Chat danach aus WLO“, Datenschutz-Satz
  ohne Angaben. Dieselbe Regel gilt mit `hinweis: ohne_erschliessung` (kein Flow-Träger) — dort
  widersprachen sich bisher Name und Erklärzeile. Datei-Weg unverändert. Kein Backend-Vertrag
  geändert.
- **E4 —** `docs/mcp-rueckmeldung-2026-11-20-volltext-status.md`: Befund, Vorschläge 1–3 an den
  MCP-Entwickler, zwei Punkte an den Autor des Metadaten-Flows.

## Entscheid zu E1 (Knöpfe statt KI-Prosa)

Der Baukasten kennt keinen Weg, auf dem ein Werkzeug-Fehler den KI-Schritt von selbst beendet: ein
`agent`-Schritt geht nur über „Weiter im Ablauf“ ohne seine `ausgabe` zu `bei_fehler`
(`treiber.weiter_ki`). Das zu ändern hieße, in `services/ablauf/` einzugreifen, wo Paket F zur selben
Zeit arbeitete. Darum: die KI sagt den ehrlichen Satz und verweist auf „Weiter im Ablauf“; dahinter
stehen die Auswege als feste Knöpfe (`ohne_dokumenttext`). Ein eigener Schritt statt `ohne_entwurf`,
weil die Auswege nur auf dem Dokument-Weg Sinn ergeben. Ohne Freitext: an einem Schritt mit
`freitext.schreibt: grundlage` leert jede Wahl diesen Teil (Querschnitts-Review AS-3, Befund 3) — „hier
im Chat lesen lassen“ verlöre dann die Grundlage „Dokument“ und landete beim Entwurf aus dem Thema (im
Selbsttest so gesehen). „Ohne Dokument weiter“ führt darum zur Frage nach der Grundlage. Dort tippt die
Person ihr Thema, und die vier Fragen kommen erneut.

## Tests

- Neu `tests/test_paket_e_volltext_ehrlich.py` (10 Tests; zuerst 10 rot, dann grün): E1 Satz, Code,
  Vorrang, gemischter Fall, Seed-Knöpfe; E2 Wiederholung nach 5 s, höchstens zwei, nie bei endgültigen
  Gründen, nie über die Frist.
- Auf das neue Verhalten nachgezogen (sie hielten das alte „nochmal“ fest):
  `test_paket_k5_strukturdokumente.py`, `test_paket_k_review.py` (B5), `test_review_tg3def.py` (M3),
  `test_tg7_durchtest.py` (m3), `test_nachpruefung_tg3def.py` (MINOR 4),
  `test_ablauf_feste_argumente.py` (Abnahme S2).
- Frontend: zwei neue Fälle in `ui-upload.element.spec.ts` (zuerst 2 rot, dann grün).

## Doku

`docs/ablaeufe.md` (Absatz „Kein Text aus WLO“), `docs/ui-module.md` und `ui-upload/README.md`
(Name des WLO-Orts).

## Offen

- Kommt `extractionStatus` vom MCP (Rückmeldung, Vorschlag 2), nach Status unterscheiden (eigenes
  Paket).
- Später, falls gewünscht: ein Werkzeug-Fehler, der den KI-Schritt von selbst zu `bei_fehler` führt
  (Treiber, nach Paket F).

## Review behoben (20.11.: 1 MAJOR, 8 MINOR, 4 NIT)

- **MAJOR 1:** „Dokument hier im Chat lesen lassen“ führt zum eigenen Feld `dokument_chat` (`ui_upload`,
  `orte: [chat]`, danach `dokument_gelesen`). Im alten Feld war angemeldet mit Flow-Träger „In WLO
  ablegen“ vorgewählt, das führte zurück in denselben Fehler. Der Schritt steht bei den Auswegen:
  `dokument_laden` hat kein `weiter` und geht zum folgenden Schritt. 40 Schritte, die Obergrenze. Der
  Selbsttest „Dokument nicht gelesen, nochmal“ läuft jetzt angemeldet.
- **MINOR 2:** `strukturdokument.im_vorgang` liest `ablage` nur noch, wenn der Teil `strukturdokument`
  fehlt (Vorgang vor TG-3d). Neue Ablagen trägt `vorgang_teil._mit_strukturdokument` ohnehin in den Teil
  ein. Damit kehrt ein verworfener WLO-Knoten nicht zurück. Der Test TG-3e
  (`test_dokument_stand.py`) ist auf diese Regel umgestellt.
- **MINOR 3:** `dienst_fehler.volltext_fehler` baut Text und Code. Im gemischten Fall nennt
  `volltext_endgueltig` nur die Dokumente ohne Text, die übrigen bekommen je einen Satz aus
  `ohne_volltext`.
- **MINOR 4:** `ohne_dokumenttext` sagt nicht mehr „diesmal“. „Nochmal, falls es eben ausgelastet war“
  steht zuletzt. Die Knöpfe hängen weiter nicht am Fehlercode: das ginge erst mit einer Regel auf den
  Code im Treiber, langfristig.
- **MINOR 5:** `strukturdokument.volltext` fragt über `call_mcp_tool_antwort`. `timeout`, `transport` und
  `busy` werden `abruf_fehler` (wird wiederholt), `auth` wird `ohne_anmeldung`, eine Ablehnung (`tool`)
  wird ihr Code, falls bekannt, sonst `ohne_text`. Vorher wurde der Fehlertext des Clients zu
  `ohne_text`, und die KI sagte „kein Zugriff“. Die Attrappe `_mcp` in `test_dokument_stand.py`
  bedient den neuen Aufruf.
- **MINOR 6:** Die Frist der Lesung ist jetzt 50 statt 30 s. Der MCP wartet beim ersten Lesen bis zu
  25 s (`WLO_TEXT_TIMEOUT_MS`), danach passt noch eine Wiederholung. Zur Frist des Musterwegs: Der
  Dienst rechnet ohne Zugfrist 90 s, und zwar vor dem Lesen. Ein langes Lesen kürzt also die Zeit des
  Entwurfs. Der Agent hat 900 s, dort ist das unkritisch.
- **MINOR 7:** „dort wird auch Text in Scans erkannt“ steht im Satz an die KI nur, wenn „Hier im Chat“
  und die Texterkennung an sind (`_chat_mit_texterkennung`). Der Seed formuliert vorsichtig („dort lässt
  sich der Text oft auch aus Scans lesen“).
- **MINOR 8:** Auf dem Dokument-Weg verspricht kein Satz Metadaten: weder der Satz an die KI
  (`dienst_upload._ablage_satz(…, dokument=True)`) noch der Hinweis vor der Anmeldung
  (`ablageNachAnmeldungDokument`).
- **MINOR 9:** eigener Datenschutz-Satz `datenschutzWloDokument` (de/en).
- **NIT 10:** „Ohne Dokument weiter“ verwirft auch `ordnerweg` und `soll_ist`.
- **NIT 11:** `docs/ablaeufe.md` (40 Schritte, Ort auf dem Dokument-Weg, Fristen, `ablage`), Seed-Kopf
  (`orte` nur an `dokument_chat`), Docstring `OhneVolltext`.
- **NIT 12:** Tests: die Pause hält keinen Platz (Semaphor gemessen), eine Frist im zweiten Versuch
  lässt den letzten Grund stehen, `ablage` mit Teil gegenüber `ablage` ohne Teil. Beide Tests zum
  Verhalten waren schon grün und halten es jetzt fest.
- **NIT 13:** Die MCP-Rückmeldung nennt Scan, nicht umwandelbares Format und gescheiterte Umwandlung.
- Erledigt damit aus „Offen“: die tote WLO-Rückkehr über `im_vorgang`.

Neue Tests in `tests/test_paket_e_volltext_ehrlich.py` (zuerst 11 rot, dann grün; dazu die zwei NIT-12
Wächter), dazu ein Fall in `ui-upload.element.spec.ts` (zuerst rot). `ui-upload` jetzt 23 826 B gzip.

## Beim Deploy

Backend-Image und Widget-Bundle (E3). Den Seed `themenbaum` in bestehende Installationen übernehmen
(`import-config --werksabgleich`), sonst fehlt `ohne_dokumenttext`, und `entwurf_dokument` führt weiter
zu `ohne_entwurf`.
