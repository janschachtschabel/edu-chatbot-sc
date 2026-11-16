# Rückmeldung zu den Abläufen (2026-11-15)

Anlass: Rückmeldung des Nutzers vom 15.11. nach einem Durchgang auf Staging.

## Was sich ändert

- **Dokument im Ablauf lesen (Fehler):** Im Ablauf „Themenbaum · aus einem Dokument“ zeigte das
  Auswahlfeld „Lesen lassen kann der Chat es hier nicht“, und danach hieß es „Es ist kein
  Dokument gelesen worden“ — mit und ohne Anmeldung, gleich wie das Studio steht.
  - **Ursache:** Der Modul-Schritt baute den Block aus den Daten des Ablaufs, sobald sie den
    Vertrag des Moduls erfüllten; `zweck` genügte dafür. Den Dienst `upload_angebot`, der
    `schalter` und `grenzen` einsetzt, erreichte er nie, und ohne Schalter erlaubt das Widget
    kein Lesen.
  - **Behebung:** Module mit eigenem Dienst ohne Sprachmodell (`ui_upload`) laufen im Ablauf
    immer über den Dienst. Er bekommt nur seine Parameter (`zweck`, `hinweis`,
    `einzeldatei_als_struktur`); Systemfelder aus einem Ablauf fallen weg, ein Ablauf kann
    Lesen also nicht selbst erlauben.
  - **Prüfung:** Ein Upload-Schritt mit einem unbekannten Feld oder ohne `zweck` ist jetzt ein
    Befund. Ohne `zweck` entstand auch vorher nie ein Block.
  - **Folge für alle Abläufe mit Upload-Schritt** (Sammlungsstruktur, Sammlung prüfen,
    Themenbaum aus Inhalten): „Dokument lesen“ und „Ablage in WLO“ folgen dort jetzt erstmals den
    Einstellungen im Studio und der Anmeldung. Vorher fehlten die Schalter, also ging beides
    nie.
- **Entscheidungsfrage, eigene Antwort:** Enter schickt die eigene Antwort ab, Umschalt+Enter
  beginnt eine neue Zeile. Während einer Eingabe mit IME schickt Enter nicht ab. Der
  Vorlesetext nennt beides.
- **Ablauf, den die KI direkt startet:** Unter der Nachricht, nach der er startet, stehen keine
  Chips mehr. Vorher standen dort der Startknopf und Schnellantworten der KI, etwa „Für
  Grundschulkinder“.
  - Das Backend lässt nur den Startknopf stehen, auch gegen Chips, die später dazukommen
    (Facetten, Anmeldung). Das Kürzen nimmt ihn nicht mehr weg; vorher konnte der Start dadurch
    still ausfallen.
  - Das Widget zeigt den Knopf nicht, weil es ihn selbst drückt. Ansicht und Druck nutzen
    dieselbe Prüfung.
- **„Ohne Ablauf“ heißt jetzt „Ohne Führung, frei im Chat“** (en: „Without guidance, free
  chat“), in allen vier Abläufen mit diesem Ausstieg. Die Abschiedstexte sagen „ohne
  Führung“. Die Kennungen (`ohne`) bleiben.

## Was noch kommt

Erledigt am 2026-11-16: die Webseitenführung als Ablauf und der Zähler „Schritt x von y“ ohne
Verzweigungen und Rückwege — `aenderungen/2026-11-16-webseitenfuehrung-als-ablauf.md`.

## Geprüft

- Backend: neue Tests in `test_ablauf_upload_schalter.py`, `test_ablauf_direkt.py` und
  `test_turn_persist.py`; die Tests zu Abläufen, Seeds, Upload und Zusammenstellung sind grün.
- Frontend: `ui-entscheidung` (29) und `send-message` mit dem Direktstart (46) grün, ESLint
  sauber.
- Ein Review: 0 CRITICAL, 0 MAJOR, 3 MINOR und 6 NIT, alle behoben.

## Deploy

- Image neu bauen. Keine Migration.
- Die neuen Texte der Abläufe wirken erst nach dem Werksabgleich:
  `import-config --werksabgleich`. Ein Ablauf mit eigener Fassung im Studio behält den alten
  Chip-Text, bis die Redaktion ihn übernimmt.
