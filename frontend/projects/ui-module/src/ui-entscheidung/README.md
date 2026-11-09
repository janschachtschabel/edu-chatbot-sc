# ui_entscheidung

Eine Frage mit festen Möglichkeiten zum Anklicken (Paket U1-d1) — das erste **abfragende** Modul.
Die KI ruft es im Agent-Modus als Werkzeug (`agent: true`); der Zug endet, die Person wählt.

- **Eingabe:** `frage` (≤ 300 Zeichen), `optionen` (2–8, je `id` `^[a-z0-9_-]{1,40}$`, `label`,
  optional `hinweis`), `mehrfach` (Checkboxen statt Radio), `freitext` (zusätzlich der Punkt
  „Eigene Antwort“ mit Textfeld, ≤ 1000 Zeichen). Das Backend prüft den Aufruf gegen `eingabe` und auf eindeutige Kennungen
  (`backend/src/boerdi/ui_module/werkzeuge.py`); ein Fehler geht an die KI zurück.
- **Eigene Antwort** (seit 2026-11-09): ein Punkt der Gruppe, kein Zusatzfeld mehr. Bei Einzelwahl
  ein Radio wie die anderen: wer ins Textfeld schreibt, wählt ihn, und die Wahl oben springt
  heraus; wer danach wieder oben wählt, schickt den Text nicht mit (er bleibt im Feld stehen). Bei
  Mehrfachwahl eine Checkbox: abgehakt geht der Text nicht mit; wer danach weiterschreibt, hakt
  sie wieder an. Ins Feld springt der Fokus nur nach einem Klick mit Maus oder Finger — mit den
  Pfeiltasten bleibt er in der Gruppe (WCAG 3.2.2). Ein Hinweis nur für Screenreader am Feld sagt,
  dass Schreiben „Eigene Antwort“ wählt. Nur lesend steht der Punkt angehakt da, wenn die Antwort
  einen Text trug. Vorher schickte, wer erst oben wählte und dann schrieb, beides — und bekam die
  Wahl nicht mehr weg.
- **Antwort:** `gewaehlt[]` (Kennungen in der Reihenfolge der Möglichkeiten; leer, wenn nur die
  eigene Antwort gewählt ist), optional `freitext`. Das Backend nimmt eine leere Wahl nur mit Text an.
  „Antworten“ ruft `host.antworten(daten, text)`; `text` ist die lesbare Fassung (Beschriftungen,
  darunter die Ergänzung) und wird die Nutzerblase. Die Shell sendet beides als nächsten Zug mit
  `ui_antwort`; das Backend prüft die Antwort gegen die offene Frage der Sitzung
  (`services/ui_antwort`, `ui_module/antwort`) und gibt sie der KI gerahmt vor der Nachricht.
- **Fähigkeit:** nur `antworten` — der eigene Host des Blocks lässt nichts anderes zu.
- **Gesperrt:** ohne Wahl (oder „Eigene Antwort“ ohne Text) und während eines Zugs (`host.beschaeftigt()`).
- **Nur lesend** (`kontext().nurLesen`): beantwortet mit der gegebenen Antwort („Deine Antwort: …“),
  veraltet mit „Diese Frage ist nicht mehr offen.“ Jeder Zug der Person schließt die offene Frage;
  das Widget setzt den Zustand sofort, der Verlauf leitet ihn beim Neuladen ab.
- **Barrierefrei:** `fieldset`/`legend` benennt die Gruppe, native Radio/Checkbox (Pfeiltasten,
  Leertaste), Enter sendet, Hinweise über `aria-describedby`, Zielflächen ≥ 24 px, bedienbar ab
  320 px. Texte de/en über `kontext().sprache`.
- **Textfassung** (ältere Widgets, `/api/agent`): die Frage und die nummerierten Möglichkeiten —
  dort antwortet die Person mit Text.

Nicht für Schreib-Bestätigungen (dafür die Vorschau mit Bestätigung). Im Muster-Modus nur, wenn
das Muster das Modul in `tools:` nennt und das Widget es meldet (U-F4, seit U1-d2). Ohne `mcp` in
den Quellen verbietet der Prompt Werkzeugaufrufe; fehlt eine Pflichtangabe, wird es nicht
angeboten (die Rückfrage kommt dann als Text).
