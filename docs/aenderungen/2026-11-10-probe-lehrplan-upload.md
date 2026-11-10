# Probe Lehrplan-PDF → Themenbaum und Behebung der Schleife ohne Anmeldung (2026-11-10)

**Anlass:** Bei einem Nutzertest hat der Chat den Upload nicht erkannt und das Auswahlfeld immer
wieder angeboten. Frage: Geht „PDF hochladen → markitdown → Themenbaum“ jetzt?

## Probe

- **Aufbau:** lokales Backend mit dem aktuellen Staging-Code gegen die Wegwerf-DB
  `boerdi_upload_browser` (danach gelöscht), frisch gebautes Widget, Engine `agent`.
  - Testdatei: Ausbildungsrahmenplan Automobilkaufmann (PDF, 83 kB).
  - Sie wurde per Skript an das Dateifeld des Moduls gereicht, weil der eingebaute Browser keinen
    Dateidialog bedienen kann.
- **Mit erlaubtem Lesen:** Das Studio-Feld `dokument_ohne_anmeldung` stand für die Probe auf
  `true`, als Ersatz für eine Anmeldung.
  - `ui_upload` erscheint und schlägt das einzelne PDF als Strukturdokument vor.
  - Der Knopf „Themenbaum aus dem Strukturdokument erstellen“ startet `POST /api/ui/dokumente`
    (7,5 s). Ergebnis: „Gelesen: …, 23 Abschnitte“.
  - Das Modul antwortet von selbst. Die KI ruft `ui_strukturentwurf` mit `aus_dokument` auf, und es
    entsteht der „Entwurf (aus Dokument)“: „Ausbildung und Prüfung zum Automobilkaufmann und zur
    Automobilkauffrau“, 37 Punkte nach der Gliederung des Plans.
  - **Der Weg funktioniert.**
- **Vorgabe, ohne Anmeldung:** Das Modul sagt richtig „Lesen lassen kann der Chat es hier nicht –
  vielleicht hilft die WLO-Anmeldung“ und zeigt nur „Befund senden“.
  - Nach dem Befund bat die KI, das PDF „im Auswahlfeld erneut auszuwählen und als Strukturdokument
    zu markieren“. Danach könne sie den Themenbaum entwerfen.
  - **Das ist die Schleife aus dem Nutzertest.**

## Ursache

- Der Rahmen `[ORDNER DER PERSON …]` nannte nur den Namen des Strukturdokuments. Dass es nicht
  gelesen wurde und warum, stand nicht darin.
- Den Hinweis auf die fehlende Anmeldung bekam die KI nur in der Quittung des Zugs, der das
  Auswahlfeld zeigte. Diesen Zug beendet die Quittung selbst. Im Folgezug wusste die KI den Grund
  nicht mehr und riet: „noch einmal markieren“.

## Behebung

- `dienst_upload.nicht_gelesen_satz()` rechnet im laufenden Zug aus denselben Schaltern wie das
  Auswahlfeld einen Satz:
  - Studio aus: „abgeschaltet, nicht noch einmal anbieten“;
  - ohne Anmeldung: „erst mit dem WLO-Konto anmelden, bis dahin nicht erneut wählen lassen“;
  - erlaubt: „den Knopf ‚Themenbaum aus dem Strukturdokument erstellen‘ nutzen“.
- `upload_antwort.zeilen()` hängt den Satz an, wenn ein Strukturdokument markiert ist und
  `aktion: erfasst` lautet. Beim Ordner-Entwurf und ohne Strukturdokument kommt kein Satz.
- **Nachprobe im Browser, gleicher Ablauf ohne Anmeldung:** „Der Ausbildungsrahmenplan wurde noch
  nicht gelesen. Dafür musst du dich zuerst mit deinem WLO-Konto anmelden; danach kannst du das PDF
  im Auswahlfeld lesen lassen. Bitte wähle es bis dahin nicht erneut aus.“ Die Schleife ist weg.

## Nutzer-Entscheid: Lesen und Entwurf auch ohne Anmeldung (10.11.)

- **Frage des Nutzers:** Warum braucht das Lesen eine Anmeldung, wenn bis zur Anzeige des Entwurfs
  nichts im Repositorium geschieht? Schreiben erst, wenn er die Umsetzung des Themenbaums anweist.
- **Antwort:** Technisch braucht es keine. Die Vorgabe „aus“ war eine Vorsicht aus U3-2a (Rechenzeit
  und Missbrauch). Laut Plan §16 war anonym schon als „eventuell zulässig“ vorgesehen. Den Schutz
  übernehmen ohnehin:
  - `@public_rate_limit` je IP-Netz und die Fenster je Sitzung;
  - begrenzte Plätze der Umwandlung im Kindprozess mit Frist;
  - `max_mb` und `max_seiten`;
  - die Moderation des Texts;
  - die Löschung nach `aufbewahrung_h`.
- **Umgesetzt:** `UploadSettings.dokument_ohne_anmeldung` hat jetzt die Vorgabe `true`.
  - Seed-Kommentar, Studio-Hinweis (de/en) und Schema-Abzug (`area-schemas.fixture.ts`) sind
    angepasst.
  - Im Studio (Betrieb → Hochladen, „Auch ohne WLO-Anmeldung“) bleibt es abschaltbar.
  - Die Ablage in WLO (`ablage_in_wlo`) bleibt an die bestätigte Anmeldung gebunden, ebenso jedes
    Schreiben.
- **Wirkung auf bestehende Anlagen:** Der Bereich steht dort als `upload: {}`. Damit gilt nach dem
  Deploy die neue Vorgabe ohne weiteren Schritt. Wer im Studio ausdrücklich „aus“ gespeichert hat,
  behält „aus“.
- **Tests:**
  - neu `test_die_vorgabe_erlaubt_lesen_ohne_anmeldung`;
  - angepasst: Vorgabe in `test_upload_config.py` und `test_ui_upload.py`; die Abweisung
    `nur_angemeldet` in `test_ui_dokumente_api.py` stellt „aus“ jetzt ausdrücklich ein;
  - Backend (Upload/Dokument/Schema/Seed/i18n) 984 bestanden, Studio 171 Testdateien grün.
- Die Zeile „[ edu-sharing Skill ] Chatbot Masterskill - aktiv“ ist laut Nutzer gewollt.

## Tests

- `tests/test_ui_upload.py`: vier neue Fälle (ohne Anmeldung, Studio aus, erlaubt; kein Satz beim
  Ordner-Entwurf und ohne Strukturdokument). Vorher rot, danach grün.
- Teilmenge Upload/Antwort/Dokument/Golden-UI/Master-Skill: 619 bestanden, 1 übersprungen; ruff
  sauber.

## Offen

Siehe `offene-befunde-und-todo.md` §1, „Lehrplan-PDF → Themenbaum“:

- Die KI zeigt das Auswahlfeld nicht immer. Dafür muss der Master-Skill in den WLO-Knoten.
- Steht das Lesen im Studio auf „nur Angemeldete“, verspricht der Hinweis schon vor der Prüfung der
  Schalter, dass der Plan gelesen wird.

## Review (10.11., unabhängig, zusammen mit der Browser-Abnahme AS-U)

0 kritisch, 0 schwer, 2 mittel, 3 klein. Alle wurden am Code geprüft und behoben.

| # | Befund | Behebung |
|---|---|---|
| 1 | Die Quittung des Auswahlfelds hängte anonym jeder Absage „ohne WLO-Anmeldung“ an, auch wenn das Studio das Lesen bzw. Übertragen ganz abgeschaltet hat. Die KI schickte dann zur Anmeldung, die nichts ändert. | Der Grund kommt aus der Config (`_ohne_grund`): „im Chat abgeschaltet“, oder die Anmeldung nur dort, wo sie hilft. Der Modultext sagt nur noch „Lesen lassen kann der Chat es hier nicht.“, den Grund nennt die KI im nächsten Zug. Test `test_upload_quittung_nennt_die_anmeldung_nicht_wo_sie_nicht_hilft`. |
| 2 | Der Satz „hat den Knopf nicht genutzt“ wurde mit dem Stand des Folgezugs gerechnet. Der Knopf kann beim Zeigen gefehlt haben (alte Vorgabe, Anmeldung dazwischen). | Vorsichtiger formuliert: „wurde nicht gelesen … dort kann sie jetzt … wählen“. Zweig 2 sagt „nicht (bestätigt) angemeldet“. |
| 3 | Der Kommentar am späten Import nannte einen Zyklus, den es nicht gibt. | Richtiger Grund: Das Rahmen-Modul bleibt frei von Config- und MCP-Importen. |
| 4 | Das Modul-README klang, als sei die Anmeldung immer Pflicht. | Angepasst. |
| 5 | „eine der anderen Antworten“ stimmte nicht, wenn es nur einen Knopf zurück gibt. | „eine andere Antwort“ / „another answer“. |

Schon vorher vorhanden: Ein anonym gelesenes Dokument gehört `aufrufer=None`. Meldet sich die Person vor
dem Entwurf an, findet der Entwurf es nicht mehr (`kein_dokument`). Eingetragen in `offene-befunde` §1.

## Deploy

Backend, Studio und Widget-Bündel (Modul `ui-upload`, Text) neu bauen. Keine Migration, keine neue Variable.
