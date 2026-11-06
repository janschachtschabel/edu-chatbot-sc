# Paket U3-2b/c: Themenbaum aus einem Strukturdokument (2026-11-05)

Plan: [`../plans/2026-11-04-pakete-sammlungsstrukturen-upload-mcp.md`](../plans/2026-11-04-pakete-sammlungsstrukturen-upload-mcp.md)
(§16.6). Baut auf U3-2a auf ([`2026-11-05-paket-u3-2a-dokument-lesen.md`](2026-11-05-paket-u3-2a-dokument-lesen.md)).
Nutzertest: „Das Themenbaum-Generieren müsste auch kommen, wenn ich nur ein Dokument reinwerfe und
sage, es ist ein Strukturdokument.“

## Was die Person jetzt kann

Sie markiert in „Ordner und Dateien“ ein Strukturdokument (auch eine einzelne Datei ohne Ordner) und
klickt „Themenbaum aus dem Strukturdokument erstellen“. Nur diese Datei wird hochgeladen (Fortschritt
in Prozent, dann „wird gelesen …“). Danach antwortet das Modul von selbst; die KI ruft den
Strukturentwurf mit `aus_dokument`, und unter der Antwort steht ein bearbeitbarer Entwurf
„Entwurf (aus Dokument)“, dessen Punkte der Ordnung des Dokuments folgen.

Ohne WLO-Anmeldung (Vorgabe) oder wenn das Studio es abschaltet, steht statt des Knopfs ein Hinweis.

## Was sich ändert

| Bereich | Änderung |
|---|---|
| ui-module | `ui-upload`: Ziele als Liste (`upload-dokument.ts`, Plan O-26 — heute nur `themenbaum`), Darstellung `upload-dokument-ansicht.ts` (Hinweis, Fortschritt, Befund, Fehler je Code, „Noch einmal versuchen“ nur wo es hilft), Antwort `aktion: "dokument"`; Datenschutz-Satz je nach Schalter |
| ui-module | Vertrag: Fähigkeit `hochladen` (`ModulHost.hochladen`, Element-Brücke, Manifest-Schema); `ui_upload` hat `antworten, hochladen` |
| ui-module | `ui-strukturentwurf`: Parameter `aus_dokument`, `quelle: dokument`, Punkte mit `fundstelle` und `abschnitte`; Marke „Entwurf (aus Dokument)“ |
| ui | `dokument-transport.ts` (XHR mit Fortschritt, Zugangsblock, Code aus `detail`), `ChatApiClient.dokumentHochladen`, `BlockModulHost`/`WidgetModulHost.hochladen`, Shell → `dokumentLesen` (Sitzungswache) |
| Studio | Vorschau-Host lädt nichts hoch (Ansage + Beispiel-Befund) |
| Backend | Antwortform `ui_upload`: Rahmen `[DOKUMENT DER PERSON …]` / `[ENDE DOKUMENT]` (Befund, Ziel-Satz, erste Überschriften), Endmarke `DOKUMENT`; `Form.ende_fuer` für Module mit zwei Rahmen |
| Backend | `services/dokumente/stand.py`: Lader für das Dokument der Sitzung (einmal je Zug, erst bei Bedarf, Frist neu, Verbindung frei); in beiden Maschinen über `Umgebung.dokument` (Agent: `run_agent_loop(modul_dokument=…)`, Muster: oberste Ebene des `session_state`) |
| Backend | `strukturentwurf_dienst`: Ebene 1 aus Gliederung (≤ 8000) + Anfang (≤ 1500) mit `abschnitte` je Punkt, Ebene 2 aus dem Text der Abschnitte samt Unterabschnitten (≤ 6000); erfundene Kennungen fallen weg; Fehler `kein_dokument`, `aus_dokument` + `vorlage` schließen sich aus |
| Domäne | `dokument_gliederung.mit_unterabschnitten`; `uebersicht` hält den Deckel samt Kürzungsmarke ein (vorher bis zu 10 Zeichen darüber) |

**Abweichungen vom Plan:** Das Modul antwortet nach dem Lesen sofort (der Klick war die
Entscheidung) — nur während eines laufenden Zugs wartet der Befund auf „Themenbaum jetzt erstellen“.
Die Grenze je Dokument kennt das Modul nicht vorab; das Backend antwortet mit `zu_gross`.

## Offen (für die Nutzer-Rückmeldung)

- O-25: ob „Rolle je Datei“ die richtige Bedienung ist — bleibt bis zum Abgleich mit den Usecases.
- O-26: weitere Ziele („Inhalte erschließen“, „als Gesprächsgrundlage“) — die Liste ist vorbereitet,
  Backend-Satz je Ziel in `upload_antwort._ZIEL`, Text je Ziel im Modul.
- Das Modul ruft `POST /api/ui/dokumente/loeschen` noch nicht auf („Andere Auswahl“ lässt das gelesene
  Dokument bis zur Frist liegen).

## Review U3-2 (2026-11-05, unabhängiger Prüfer) — Befunde und Behebung

Zählung: 1 CRITICAL, 3 MAJOR, 8 MINOR, 5 NIT; alle gegen den Code geprüft.

| # | Schwere | Befund | Behebung | Test |
|---|---|---|---|---|
| 1 | CRITICAL | ATX- und `data:`-Bild-Regex quadratisch (16 000 Zeichen → 1,7 s; eine `.md` hielt die Ereignisschleife minutenlang an) | ATX linear (`\S[^\n]*`, Schluss-`#` in Python), `data:`-Bilder ohne Regex in einem Durchgang; Erkennen, Bereinigen, Gliedern, Befund in `asyncio.to_thread` | `test_lange_leerzeichenzeile_und_offene_data_bilder_in_linearer_zeit` (1 MB < 2 s, vorher rot) |
| 2 | MAJOR | `pdf_seiten`/`vorpruefung` im Elternprozess (kaputtes 8-MB-PDF: 2 × 16 s Stillstand), PDF doppelt geparst | Prüfung und Umwandlung gemeinsam im Kindprozess (`pruefe_und_wandle`), `wandle_datei(vorgeprueft=True)` | `test_zip_bombe_im_kind…`, `test_pdf_geht_durch_den_kindprozess…` (kein zweites Parsen) |
| 3 | MAJOR | Rollen/„ignorieren“ während des Hochladens bedienbar → Modul blieb dauerhaft gesperrt | Baum während des Lesens gesperrt (`gesperrt` in `baueBaum`, Ereignisse abgewiesen); verwaiste Antwort setzt den Ablauf zurück | Spec „Review 3“ |
| 4 | MAJOR | Frist zählte das Warten auf den Platz mit; nach Zeitüberschreitung hielt das Kind den Platz bis 120 s | `im_kindprozess(frist_s=…, platz_frist_s=…)`: Kind wird zur Upload-Frist beendet, Platz-Wartezeit 20 s → `ausgelastet`; Zähler sinkt erst nach dem Lauf | `test_der_platz_hat_eine_eigene_wartegrenze` |
| 5 | MINOR | `mkdtemp` vor dem `try` → Zähler hing bei vollem Datenträger | in den `try`, `OSError` → `server` | `test_kein_temp_verzeichnis_haelt_den_zaehler_nicht_fest` |
| 6 | MINOR | Moderation las 3000 Zeichen, der Entwurf 8000; ungeprüft galt als sauber | Moderation ≥ Generator (8000/4000, Wächtertest); ungeprüft folgt `MODERATION_FAILURE_MODE` (closed → 503 `pruefung_fehlt`) | `test_die_moderation_sieht_mindestens…`, `test_ungepruefte_moderation_folgt_dem_failure_mode` |
| 7 | MINOR | Lader prüfte die aktuellen Schalter nicht; DB-Fehler flog in den Werkzeugaufruf | `dokument_erlaubt()` zuerst; `SQLAlchemyError` → Rollback, `None` (→ `kein_dokument`) | zwei Tests in `test_dokument_stand` |
| 8 | MINOR | 413 der Rumpf-Grenze (Text) wurde „ließ sich nicht lesen“ mit neuem Versuch | `codeVon`: 413 → `zu_gross` | Spec „Review 8“ |
| 9 | MINOR | jeder Fortschrittsschritt zeichnete die ganze Fläche neu | Balken und Satz an Ort und Stelle, neu gezeichnet nur beim Phasenwechsel | Spec „Review 9“ |
| 10 | MINOR | Rahmen trägt 8 Überschriften vom Client statt Übersicht ≤ 3000 aus der DB | **als Abweichung angenommen:** die Überschriften sind gerahmt, einzeilig und laufen durch die Sicherheitsprüfung; den Text liest der Dienst ohnehin serverseitig. Bindung an `upload_id` → offen | — |
| 11 | MINOR | markitdown 0.1.6, Plan verlangt ≥ 0.1.9 mit grünem `pip-audit` | **offen** — Bedingung vor der Freischaltung im Betrieb | — |
| 12 | MINOR | Testlücken | 1, 2, 3, 4 abgedeckt; Muster-Weg über `tool_loop_module` getestet, die eine Zeile in `respond.py` nicht | siehe oben |
| 13 | NIT | schon abgebrochenes Signal → Promise blieb offen | Prüfung vor `open()` | Transport-Spec „Review 13“ |
| 14 | NIT | Docstrings nannten `CHAT_UPLOAD_*` | korrigiert | — |
| 15 | NIT | `ui-upload.element.ts` 372 Zeilen | Ablauf in `upload-dokument-ablauf.ts` (Element 329) | bestehende Specs |
| 16 | NIT | Vertiefen eines Dokument-Entwurfs liest das Dokument nicht | **offen**, Folgepunkt | — |
| 17 | NIT | jede `IntegrityError` → 409 | gelöschte Sitzung → 404 `sitzung_unbekannt` | `test_inzwischen_geloeschte_sitzung_ergibt_404` |

Außerhalb des Umfangs (schon vorher): 429 trägt den Satz des Servers als `detail` (auch beim
Themenbaum-Zweig); `rag/umwandeln` loggt den Text einer markitdown-Ausnahme; Starlette legt
Multipart-Dateien über 1 MB kurz im System-Temp ab.
