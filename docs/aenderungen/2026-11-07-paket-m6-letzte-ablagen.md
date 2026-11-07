# Paket M6: Die eigenen letzten Ablagen (2026-11-07)

Plan [`../plans/2026-11-07-mcp-vertrag.md`](../plans/2026-11-07-mcp-vertrag.md) (M6). Offener Punkt T1b aus U3-3
(„letzte Ablagen nach der Anmeldung“), jetzt über `wlo_list_my_batches` des MCP (Stand 07.11.).

## Was sich ändert

- **Backend:** `services/ablage/mcp_ablage.letzte_ablagen()` ruft `wlo_list_my_batches` mit dem Zugang der Person
  (nur mit bestätigter Anmeldung, nie mit dem Block der Anlage) und gibt je Ablage Titel, Datum und Zahlen zurück
  (abgelegt, ohne Inhalt, unklar, gescheitert, offen) — **keine Kennungen**. Eine Ablage, deren Stand WLO nicht lesen
  konnte, steht ohne Zahlen da. Das Werkzeug steht wie die drei Stapel-Werkzeuge in keinem Angebot an die KI.
- **`POST /api/ui/ablage/vorbereiten`** bringt die Liste als `letzte` mit (bis 5). Sie wird parallel zur Freigabe
  geholt und bekommt danach höchstens 3 s; scheitert oder dauert sie (auch ein Server ohne das Werkzeug), ist sie
  leer — die Vorbereitung hängt nicht daran. Scheitert die Freigabe, wird die Liste abgebrochen.
- **Modul `ui_upload`:** Neben der Vorschau steht eingeklappt „Deine letzten Ablagen in WLO (n)“ mit je einer Zeile
  „Titel (Datum) – 30 abgelegt, 2 unklar, 1 gescheitert“ (wie die eigene Ergebniszählung: „ohne Inhalt“ zählt als
  abgelegt, „unklar“ steht für sich, Nullen fallen weg) und dem Hinweis, dass dieselbe Auswahl nicht noch einmal
  übertragen werden muss; ist die Liste gekappt, sagt es ein Satz. Datum in der Sprache der Seite. Aufgeklappt
  bleibt sie auch beim Neuzeichnen. Kein zusätzlicher Aufruf aus dem Modul.

## Bewusst nicht

- Kein Fortsetzen einer früheren Ablage aus der Liste (der Server bietet es über `nodeId`; ein eigener Schritt, wenn
  gebraucht) und keine Anzeige im Chat-Text „nach der Anmeldung“ — die Liste steht dort, wo eine doppelte Ablage
  entstünde.

## Review

Unabhängiges Review: 1 MAJOR, 3 MINOR, 3 NIT (dazu Befunde zum M5-Nachtrag, siehe dort). Behoben:
- Die Liste bremst `vorbereiten` nicht mehr (MAJOR): eigene Aufgabe, nach der Freigabe höchstens 3 s, bei einem
  Fehler der Freigabe abgebrochen.
- Zahlen wie die eigene Zählung (`unklar` heißt „kann abgelegt sein“ — als „offen“ hätte es zu einer doppelten
  Ablage verleitet).
- Kappung (`scanTruncated`) wird genannt.
- Aufgeklappt bleibt aufgeklappt, der Fokus kehrt zur Überschrift zurück.
Gelassen (NIT): die Studio-Vorschau des Moduls zeigt keine Liste (sie hat keine Antwort mit `letzte`).

## Wirkt erst, wenn

- im MCP die Stapel-Ablage eingeschaltet ist (`WLO_BATCH_UPLOAD_ENABLED`; live derzeit aus),
- MA-0 (Messung mit dem Testkonto) gelaufen ist (wie für das Übertragen selbst, U3-3) und
- im Studio „Inhalte in WLO ablegen“ eingeschaltet ist (Vorgabe aus).

## Beim Deploy

- Image neu bauen (baut Widget und Module selbst), danach Hard-Reload: `ui-upload` hat einen neuen Hash.
  Bündel 17,7 kB gzip (Grenze 20 kB).

## Tests

- `backend/tests/test_mcp_vertrag_m6.py` (neu, 6; aus dem Review: eine hängende Liste): Liste ohne Kennungen, unlesbarer Stand, ohne Anmeldung kein Aufruf,
  Werkzeug nicht im KI-Angebot, `vorbereiten` bringt die Liste mit, ein Fehler hält die Vorbereitung nicht auf.
- `frontend/…/upload-uebertragen.spec.ts` (+1): `letzteAus` liest die Antwort; Unbrauchbares fällt weg.
- `frontend/…/ui-upload-uebertragen.element.spec.ts` (+2): die Liste steht neben der Vorschau, ohne zusätzlichen
  Aufruf; aufgeklappt bleibt sie beim Neuzeichnen, Kappung genannt.
