# ui_fortschritt — Stand eines Ablauf-Auftrags (Paket K1b)

Nachgeladenes Modul (`laden: "bei_bedarf"`): rahmenloses Custom Element `<boerdi-ui-fortschritt>` in
einem eigenen Bündel (siehe `docs/ui-module.md` §2.5). Nur der Ablauf-Treiber baut es
(`agent: false`): startet ein `auftrag`-Schritt einen b-api-Auftrag (Kestra-Flow), hängt der Treiber
den Block an die Antwort — solange das Modul im Studio aktiv ist. Der Knopf „Stand prüfen“ steht
weiter darunter (ohne JavaScript, Modul aus, Bündel nicht ladbar).

- **Daten** `{ablauf, kuerzel, text}`: `kuerzel` = die ersten 12 Hex-Zeichen von sha256(Job-ID) —
  die Job-ID selbst kommt nie in den Browser.
- **Nachfragen** (`fortschritt-ablauf.ts`): `host.auftrag({schritt: 'stand'})` → `POST /api/ui/auftrag/stand`,
  ohne Zug, das Backend schreibt dabei nichts. Erste Frage nach 5 s, dann 10, 20, 30 und alle 60 s; nicht
  während die Seite verborgen ist (sobald sichtbar: sofort); nach 30 Minuten nur noch per „Jetzt prüfen“.
  Nie zwei Fragen zugleich; ein entferntes Element fragt nicht weiter.
- **Abholen**: `fertig` oder `fehler` → einmal `host.auftrag({schritt: 'abholen'})` — die Shell schickt die
  Direktaktion `ablauf_auftrag_pruefen` als Zug ohne Nutzerblase; dort werden die Ausgaben Teil des
  Vorgangs und der Ablauf geht weiter. Läuft gerade ein Zug, wartet das Modul, bis die Shell frei ist;
  ging nichts hin, bietet es „Ergebnis abholen“ an.
- **Abbrechen** (Paket K2b): „Auftrag abbrechen“ steht, solange der Auftrag läuft (nicht im Verlauf, nicht
  während eines Zugs). `host.auftrag({schritt: 'abbrechen'})` schickt die Direktaktion
  `ablauf_auftrag_abbrechen` als Zug ohne Nutzerblase; das Backend fragt erst nach („Ja, abbrechen“). Das
  Nachfragen läuft weiter: nach dem bestätigten Abbruch antwortet der Stand mit 409 → „abgeschlossen“.
- **Fehler nach Status**: 409/404/400/422 → „abgeschlossen“ (etwa ein alter Block im Verlauf);
  401/403 → Hinweis auf die Anmeldung, 403 `abgewiesen` (die B-API weist den Schlüssel ab, R1-e) → eigener Satz; sonst (503, Netz) → Hinweis und weiter mit dem nächsten Abstand.
- **Darstellung** (`fortschritt-stil.ts`, `fortschritt-texte.ts`): Gerüst einmal gebaut, `zeichne()` setzt
  nur Texte und `hidden` — der Fokus bleibt stehen; verschwindet ein fokussierter Knopf, geht er auf den
  Rahmen. „Jetzt prüfen“ ist während einer Frage `aria-disabled` (nicht `disabled`, sonst fiele der Fokus
  auf `body`). Wechsel des Stands werden über eine bleibende `aria-live`-Zeile angesagt, nicht jede Frage.
  Uhrzeit über `Intl`, der Satz aus den Daten nur als `textContent`, nur M3-Tokens.

Tests: `fortschritt-ablauf.spec.ts` (Uhr, Abstände, Fehler, Trennen), `ui-fortschritt.element.spec.ts`
(Darstellung, Fokus, nur lesen, Abbrechen), `e2e/fortschritt.spec.ts` (echtes Bündel, echter Zug-Weg, 320 px).
