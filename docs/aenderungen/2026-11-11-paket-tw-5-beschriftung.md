# Paket TW-5: „Senden“ statt „Befund senden“ (2026-11-11)

Plan `plans/2026-11-11-themenbaum-ausloesen-und-wissen.md`, Entscheid E7. Auf Rückmeldung des
Nutzers heißt der Knopf im Auswahlfeld (`ui_upload`) jetzt „Senden“, englisch „Send“, statt
„Befund senden“ („Send summary“). Was gesendet wird, sagt der Satz darunter: „Nur Ordnernamen
und Zahlen gehen an den Chat …“.

- Geändert: `frontend/projects/ui-module/src/ui-upload/upload-texte.ts` (de/en).
- Die beiden Specs, die den Knopf am Label finden, sind angepasst.
- Der Knopf trägt zusätzlich den Namen „Auswahl an den Chat senden“ (en „Send selection to the
  chat“, `aria-label`). Der Chat hat selbst einen Knopf „Senden“, so sind beide unterscheidbar.
  Der sichtbare Text steckt im Namen (Label in Name).
- Die README des Moduls ist nachgezogen. Ältere Änderungsnotizen bleiben, wie sie sind.
- Prüfung: ui-module 348 grün, eslint sauber.
