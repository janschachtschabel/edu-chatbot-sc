# Paket U3-2a: ein Dokument im Chat lesen — Backend und Studio-Bereich (2026-11-05)

Plan: [`../plans/2026-11-04-pakete-sammlungsstrukturen-upload-mcp.md`](../plans/2026-11-04-pakete-sammlungsstrukturen-upload-mcp.md)
(Fassung 3, §16.6). Teil 1 von 3: U3-2b (Entwurf aus dem Dokument) und U3-2c (Knopf, Fortschritt
und Befund im Modul) folgen; bis dahin ruft niemand den neuen Endpunkt.

## Was entsteht

Ein Dokument (PDF, Word, Text, Markdown), das die Person im Auswahlfeld `ui_upload` markiert hat,
kann das Widget an `POST /api/ui/dokumente` schicken. Das Backend wandelt es um, gliedert es,
lässt Übersicht und Anfang moderieren und legt **Markdown und Gliederung** an der Sitzung ab —
die Datei selbst nicht. Zurück kommt nur der Befund (Seiten, Wörter, Sprache, Abschnitte, Art der
Gliederung, Warnungen) und eine Vorschau der ersten Überschriften, kein Text.

## Was sich ändert

| Bereich | Änderung |
|---|---|
| Datenbank | Migration `0017_dokument_uploads`: ein Dokument je Sitzung (`session_id` UNIQUE, CASCADE), `verfaellt_am` mit Index |
| Domäne | `dokument_art` (Magic Bytes, Bilder eigens), `dokument_gliederung` (bereinigen, ATX / nummeriert mit Inhaltsverzeichnis-Abgleich / Teile à 3000, Übersicht, Abschnittstext), `dokument_befund` |
| Dienste | `services/dokumente/ablage.py` (speichern ersetzt, lesen nur gleiche Sitzung und gleicher Aufrufer, abgelaufen sofort unlesbar), `umwandlung.py` (Seitenprüfung vor der Umwandlung, ZIP-Grenzen wie RAG, Temp-Verzeichnis 0700 mit Endung aus der Art, Frist 60 s, Wartedeckel 3, NUL entfernt, ≤ 2 Mio. Zeichen), `aufnahme.py` (Ablauf und Fehlercodes) |
| Aufbewahrung | `aufbewahrung.lauf()` löscht abgelaufene Dokumente mit; nicht im Bericht (kein Protokoll) |
| API | `POST /api/ui/dokumente` (multipart: `session_id`, `block_id`, `datei`) und `POST /api/ui/dokumente/loeschen` (204, auch für fremde Kennungen); Rumpf-Grenzen 26 MiB bzw. 16 KiB; OpenAPI neu erzeugt |
| Config | neuer Bereich `01-base/upload-config` (`dokument_im_chat` an, `dokument_ohne_anmeldung` aus, `ablage_in_wlo` aus, `max_mb` 10 ≤ 25, `max_seiten` 300 ≤ 1000, `aufbewahrung_h` 24 ≤ 72); Seed, Wirkung „voll/voll“ |
| Auswahlfeld | `upload_angebot` setzt `schalter.dokument_im_chat` aus Studio **und** Anmeldung; `ablage_in_wlo` bleibt bis U3-3 aus |
| Studio | Seite „UI-Module“ bekommt den Abschnitt „Hochladen“ (Feldtexte de/en in `fields-upload.ts`); Schema-Fixture neu erzeugt |

**Reihenfolge der Bremsen am Endpunkt:** reservierte/kurze Sitzungskennung (422) → Drosselung
außen je IP und innen je Sitzung (429, Ereignis) → Sitzung (404 `sitzung_unbekannt`) → offene
Frage von `ui_upload` mit dieser `block_id` (409 `keine_anfrage`) → Verbindung zurück in den Pool →
Anmeldung bestätigen → Studio-Schalter (403 `aus` / `nur_angemeldet`) → Größe (413 `zu_gross`) →
Art (415 `bild`, 400 `art_unbekannt`) → Seiten/ZIP (400) → Umwandlung (504 `zu_langsam`,
503 `ausgelastet`, 400 `unlesbar`) → kein Text (400 `kein_text`) → Moderation (400 `abgewiesen`,
Sicherheitsereignis ohne Inhalt) → Ablage (409 `laeuft_schon` bei zwei Uploads zugleich).

**Abweichung vom Plan:** keine Umgebungsvariablen `CHAT_UPLOAD_*`. Die Grenzen stehen nur im
Studio-Bereich, mit festen Obergrenzen im Modell; die Rumpf-Grenze des Pfads folgt der Obergrenze.
Zwei Quellen für dieselbe Zahl hätten nur die Frage aufgeworfen, welche gilt.

**Datenschutz:** Rohdatei nie gespeichert, Dateiname nie geloggt (nur Art und Fehlerart), Text
nur gerahmt an die KI (kommt mit U3-2b). Ohne Anmeldung wird das Dokument ohne Aufrufer abgelegt;
nach einer späteren Anmeldung in derselben Sitzung ist es dann nicht mehr lesbar (gewollt).

**Offen:** markitdown steht auf 0.1.6; ob ein Sprung auf ≥ 0.1.9 nötig ist, klärt ein
`pip-audit`-Lauf (nicht Teil dieses Pakets).

## Tests

Neu: `test_dokument_art`, `test_dokument_gliederung`, `test_dokument_umwandlung`,
`test_dokument_aufnahme`, `test_dokument_ablage` (Postgres), `test_upload_config`,
`test_ui_dokumente_api`; ergänzt: `test_aufbewahrung`, `test_ui_upload`, `test_config_models`,
`test_openapi_contract`, `test_i18n_messages`.
