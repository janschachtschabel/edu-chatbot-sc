# Paket K2d-2 — Dateien eines Auftrags holen (2026-11-08)

Plan: [`plans/2026-11-08-kestra-ablaeufe-komfort.md`](../plans/2026-11-08-kestra-ablaeufe-komfort.md), §K2d,
Teil K2d-2 (Entscheid F3: ja, gedeckelt und nur die im Schritt genannten).

## Was sich ändert

- **Neues Feld am Auftragsschritt:** `dateien_holen`, eine Liste von bis zu drei Kennungen (`outputId`) der
  Dateien, die der Flow liefert. Im Studio heißt das Feld „Dateien holen“ und steht nur bei `typ: auftrag`.
- **Beim Abholen** („Stand prüfen“, Auftrag fertig) holt das Backend genau diese Dateien.
  - **Schlüssel und Adresse:** Es nimmt den Schlüssel der Person. Die Adresse `{Status-Pfad}/files/{outputId}`
    (`/api/v1/jobs/{jobId}/files/{outputId}`) bildet es selbst, nie aus `downloadUrl`. Es folgt keiner
    Weiterleitung, sonst ginge der Schlüssel mit.
  - **Grenze:** höchstens so groß wie ein Upload (Studio „Upload“, `max_mb`). Eine größere Datei wird nicht
    zu Ende gelesen.
  - **Aufbereitung wie ein Upload** (`dokumente.aufnahme`): Art nach Magic Bytes, Umwandlung im Kindprozess,
    Seitengrenze, Moderation (Stufe `auftrag_datei`), kein Bild. Ein Flow ist ein fremder Dienst.
  - **Ablage im Teil:** Der Text (Markdown, höchstens 200 000 Zeichen je Datei) steht im Teil des Ergebnisses unter
    `texte.<outputId>`. Was nicht ging, steht unter `dateien_fehlen.<outputId>` mit einem Code:
    - Holen: `unbekannt`, `nicht_verfuegbar` (nach 7 Tagen gelöscht), `zu_gross`, `zu_langsam`,
      `schluessel_abgewiesen`, `voll` (429), `fehler`;
    - Aufbereitung wie beim Upload: `abgewiesen` (Moderation), `pruefung_fehlt`, `art_unbekannt`, `bild`,
      `kein_text`, `unlesbar`, `zu_viele_seiten`, `entpackt_zu_gross`, `ausgelastet`.
  - **Vorübergehend** (`voll`, `fehler`, `ausgelastet`, `zu_langsam`, `pruefung_fehlt`): Das Ergebnis wird noch nicht
    festgeschrieben. Die Antwort lautet „Der Auftrag ist fertig, aber seine Dateien konnte ich gerade nicht
    holen …“, der Knopf „Stand prüfen“ bleibt. Nach drei Versuchen je Job geht das Ergebnis ohne die Datei weiter.
  - **Frist:** alle Dateien eines Klicks zusammen 60 s, Download und Aufbereitung (mit Warten auf den Platz
    und Moderation) eingeschlossen — unter der Lesefrist des Ingress, 120 s; jeder Download höchstens 30 s. Nach einem abgewiesenen Schlüssel oder `voll` geht keine weitere Anfrage hinaus.
  - **Weiterverwenden** mit K2d-1: `{"$teil": "volltext", "pfad": "texte.report"}`. Fehlt der Text, fehlt der
    Teil, und der Schritt geht zu `bei_fehler`.
- **`dateien` im Ergebnis** tragen jetzt auch `kennung` (`outputId`), damit ein Ablauf sieht, welche Dateien es
  gibt. Die Adresse steht weiter nicht darin.
- **Prüfung:** `dateien_holen` an einem anderen Schritttyp ist ein Befund. Form (Buchstaben, Ziffern, `_`, `-`,
  kein Punkt, weil die Kennung ein Glied eines Pfads ist) und Zahl (höchstens drei) prüft das Modell (422).

## Abweichung vom Plan

- Der Plan sah die Dateien „in der Ablage des Vorgangs (`dokumente`)“. `dokument_uploads` hält aber genau ein
  Dokument je Sitzung für `ui_upload`. Der Text steht deshalb im Teil des Ergebnisses; ein großer Teil liegt
  ohnehin in `vorgang_ablage`. Gelesen wird er wie jeder Teil.
- Gespeichert wird nur der aufbereitete Text, nie die Rohdatei (wie beim Upload).

## Geändert

- `domain/config_models/ablauf.py`: `Schritt.dateien_holen` (`NurBei("typ", "auftrag")`, höchstens drei,
  Muster ohne Punkt).
- `services/auftraege/client.py`: `kennung` in `dateien`; neu `datei()` (Stream mit Deckel, ohne Weiterleitung;
  404 `unbekannt`, 410 `nicht_verfuegbar`, 401/403 `abgewiesen`, 429 `voll`, sonst `fehler`).
- neu `services/auftraege/dateien.py`: `holen()` (Grenzen, Aufbereitung, Codes).
- `services/ablauf/auftrag_zug.py`: holt beim Abholen, noch ohne DB-Verbindung.
- `services/ablauf/pruefung.py`, `pruefung_texte.py`: Befund `dateien_holen` (de/en).
- Studio: Feldtexte `feld.Schritt.dateien_holen.*` (de/en). Schema-Fixture und Vertrag neu erzeugt; keine neue
  Operation.

## Bewusst so

- **Längerer Klick:** Bis zur Gesamtfrist von 60 s; deshalb höchstens drei Dateien. Die Umwandlung nutzt
  denselben einen Platz im Kindprozess wie Uploads und RAG-Importe. Ist er belegt, kommt `ausgelastet`
  (vorübergehend, siehe oben).
- **Grenze für die KI:** Ein Text kann bis 200 000 Zeichen lang sein. Ein Werkzeug der KI bekommt einen Teil aber
  nur bis 64 kB (`teil_verweise.MAX_BYTES`), größer gilt er als fehlend. Modul- und Auftragsschritte eines Ablaufs
  bekommen ihn ganz.
- **Kein Sicherheitsereignis bei einem Moderationstreffer** (anders als beim Upload,
  `log_safety_event("upload:moderation")`). Das Holen läuft ohne DB-Verbindung, und der Treffer steht als Code im
  Teil und als Zähler `boerdi_safety_stage_total{stage="auftrag_datei"}`.
- Der Studio-Schalter `dokument_im_chat` gilt für Uploads im Chat, nicht für Dateien eines Auftrags. Diese holt
  nur ein Schritt, den die Redaktion angelegt hat, und nur mit Anmeldung.
- **Moderation:** Ohne erreichbare Moderation entscheidet `MODERATION_FAILURE_MODE` wie beim Upload (`closed`:
  `pruefung_fehlt`).

## Review (2026-11-08)

Ein frischer Reviewer: 0 kritisch, 0 hoch, 3 mittel, 6 Kleinigkeiten. Behoben:

| Befund | Behebung |
|---|---|
| Ein vorübergehender Fehler (429, Netz, Umwandlung ausgelastet) verbrauchte das Ergebnis endgültig, obwohl die Datei noch 7 Tage liegt. | Kein Festschreiben, Hinweis und „Stand prüfen“; höchstens drei Versuche je Job (`entities`). |
| 200 000 Zeichen Text, aber 64 kB an ein Werkzeug der KI. | Unter „Bewusst so“ benannt (Ablaufschritte bekommen den ganzen Text). |
| Ein Klick mit drei Dateien konnte über die 120 s des Ingress laufen. | Gesamtfrist 60 s, Download höchstens 30 s, danach `zu_langsam`. |
| Nach einem abgewiesenen Schlüssel ging es mit demselben weiter. | Nach `schluessel_abgewiesen`/`voll` keine weitere Anfrage. |
| `abgewiesen` für Schlüssel und Moderation. | `schluessel_abgewiesen` für den Schlüssel. |
| Gepackte Antworten wuchsen vor dem Deckel; kein Blick auf `Content-Length`. | `Accept-Encoding: identity`, gepackt wird abgewiesen, eine zu große angekündigte Länge nicht gelesen. |
| Abweichungen vom Upload (Sicherheitsereignis, Schalter) undokumentiert. | Unter „Bewusst so“. |
| Metrik-Stufe fehlte in `uebergabe-betrieb.md`; Codeliste unvollständig. | Ergänzt. |
| Testlücken | Tests für 429, Länge, gepackt, Deckel bei vielen Stücken, Abbruch nach Schlüssel, Gesamtfrist, echte Aufbereitung (Stufe, Treffer, Bild, `closed`), vorübergehender Fehler im Zug. |

## Zweites Review (2026-11-08)

Ein frischer Reviewer: 0 kritisch, 1 mittel, 4 klein, 1 Kleinigkeit. Behoben:

| Befund | Behebung |
|---|---|
| Fiel die Moderation aus (`MODERATION_FAILURE_MODE=closed`), wurde das Ergebnis mit `pruefung_fehlt` endgültig festgeschrieben. | `pruefung_fehlt` gilt als vorübergehend: „Stand prüfen“ versucht es erneut. |
| Die 60 s deckten nur den Download; Warten auf den Platz der Umwandlung, Puffer und Moderation lagen außerhalb (bis ~90 s). | Die Aufbereitung läuft in der Restfrist (`asyncio.timeout`), danach `zu_langsam`; der Kindprozess hält seinen Platz wie bisher. |
| Der Zähler der Versuche lag unter der rohen Job-ID in der Sitzung (Studio-Sitzungsansicht) und blieb nach Abbruch liegen. | Ein Eintrag `{auftrag: <Kürzel>, n}`; ein anderer Auftrag fängt neu an. |
| 410 (Datei gelöscht) hieß `unbekannt`. | `nicht_verfuegbar`. |
| Modulkopf des Clients ohne `zu_gross`; Plantext sprach noch von der Ablage `dokumente`. | Nachgezogen. |
| Testlücken | Tests für Frist in der Aufbereitung, Abbruch nach `voll`, Zähler mit Kürzel und Rücksetzen nach Erfolg. |

## Tests

- neu `backend/tests/test_auftrag_dateien_k2d2.py` (24, davon 6 aus dem Review):
  - Kennung im Stand, die Adresse bildet der Client, mit Schlüssel;
  - Deckel, Fehlercodes, keine Weiterleitung, fremde Zeichen werden nicht geholt;
  - nur die genannten Dateien, höchstens drei, Codes, Kürzung;
  - Modell und Prüfung;
  - Goldfassung;
  - im Zug: „Stand prüfen“ legt `texte` und `dateien_fehlen` in den Teil; ohne `dateien_holen` bleibt das
    Ergebnis wie bisher.
- angepasst `test_auftraege_vertrag.py` (Dateien mit `kennung`), `test_ablauf_studio_k2c1.py` (Wächter kennt das
  Feld).
- Studio-Suite 2040 grün.
- Volle Backend-Suite nach K2d-1…3: 8978 grün, 1 rot (Log-Wächter `test_log_ohne_inhalt`: eine Logzeile
  nannte die Variable `antwort`) — behoben, Wächter und Paket-Tests danach grün.

## Betrieb

Keine Migration, keine neue Variable. Backend und Studio neu bauen. Ein Flow, dessen Dateien geholt werden
sollen, muss sie als Ausgabe-Dateien mit `outputId` liefern (Job-Vertrag).
