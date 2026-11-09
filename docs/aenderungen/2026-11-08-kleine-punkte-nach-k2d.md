# Kleine offene Punkte nach K2c/K2d (2026-11-08)

Auftrag des Nutzers: „behebe die kleinen Punkte und Befunde“. Behoben sind die kleinen Punkte aus
`offene-befunde-und-todo.md`, die nach K2c-1, K2c-4 und K2d-3 offen waren.

## Was sich ändert

- **Knopf „Plan fortsetzen“** statt „Weiter anlegen“. W2/W3 (Volltexte, Metadaten) legen nichts an; der Knopf
  passt jetzt zu jedem Plan. Englisch bleibt „Continue“.
  - Mitgezogen: Bot-Texte (`write.planOpen`, `planStillOpen`, `planBusy`, `planUnclear*`), die
    Werkzeugbeschreibungen, M18 (Seed und `docs/dimensionen/muster/M18-kuration.md`), die Studio-Referenz,
    `architektur.md`, `mcp-und-anmeldung.md`, `docs/skills/vorgehen*.md`.
- **„WLO ist ausgelastet“ nennt die Wartezeit**, die der Server angibt (`retryAfter` bei `upstream_busy`
  oder `Retry-After` eines 429/503): „WLO bittet, etwa 60 Sekunden zu warten.“
  - Bei der Abnahme (`write.busy`) und bei „Plan fortsetzen“ (`write.planBusy`); `McpAntwort.warte_s`.
  - Auch das Modell liest sie im Fehlertext (Werkzeug- und Agent-Schleife).
  - Ohne Angabe, bei 0 oder über einer Stunde bleibt der Satz wie bisher (`wiederholung.genannte_wartezeit`).
- **`bei_fehler` nur, wo er wirkt.** Der Treiber nimmt ihn bei `modul`, `werkzeug`, `agent` und `auftrag`
  (`pruefung.MIT_BEI_FEHLER`).
  - Bei `nachricht` und `verzweigung` meldet die Prüfung jetzt „bei_fehler wirkt bei der Art … nicht“.
  - Sein Ziel gilt dort nicht mehr als erreichbar.
  - Das Studio zeigt dort keinen Pfeil „bei Fehler →“.
- **`weiter` als Liste außerhalb einer Verzweigung** (die Prüfung meldet sie schon als falsch) nimmt der
  Treiber jetzt wie kein `weiter`, also den folgenden Schritt. Bisher ging ein Schritt mit `weiter: []` und
  `bei_fehler` auch im Erfolgsfall zu `bei_fehler`. Die Schrittfolge im Studio folgt dem.
- **W2:** Die Beschreibung nennt die Grenzen je Eintrag (`sourceUrl` bis 2000, `language` bis 10 Zeichen).

## Bewusst nicht

- **`would_replace_file` merkt den Text nicht vor.** Ein echtes Vormerken (Text im Vorgang halten, nach der
  Messung des MCP-Teams nachtragen) ist ein eigenes Paket und hängt am MCP-Team.
- **`MODERATION_FAILURE_MODE=closed` sperrt auch „Stand prüfen“ und „Abbrechen“**, und die Seitenwege
  `/api/ui/*` kennen die Sperre nicht. Beides ist eine Entscheidung des Nutzers, kein Fehler.

## Review (2026-11-08)

Ein frischer Reviewer: 0 kritisch, 0 hoch, 4 klein, 3 Kleinigkeiten. Behoben:

| Befund | Behebung |
|---|---|
| `write.planBusy` sagte noch „weiter angelegt“ (en „created“); der Test prüfte nur „anlegen“. | „weiter geändert“ / „changed“; der Test prüft den Wortstamm in allen Plan-Texten. |
| Die Wartezeit eines 429/503 (`Retry-After`) kam nicht an, nur `upstream_busy`. | `McpAntwort.warte_s` aus beiden Quellen. |
| Das Modell erfuhr die Wartezeit nicht. | Sie steht im Fehlertext. |
| „WLO nennt dafür etwa … Sekunden“ war unklar. | „WLO bittet, etwa … Sekunden zu warten.“ |
| Ein Tippfehler im `bei_fehler`-Ziel an `nachricht` wurde nicht mehr gemeldet. | Das Ziel wird weiter geprüft. |
| `offene-befunde` nannte noch „Weiter anlegen“. | Nachgezogen. |

Nachgezogen (2026-11-08, zweite Runde): `WriteGate.prepare` verbrauchte im Agent-Modus `execute` den Merkposten
auch, wenn der Aufruf nie hinausging. Jetzt kommt er bei „ausgelastet“ ohne Code zurück
(`client.ausgelastet_ohne_aufruf`: eigener Wächter, Ausfall-Schalter, 429/503). Bei `upstream_busy` bleibt er
verbraucht, denn ob der Server den Schlüssel eingelöst hat, steht nicht im Text. Test in
`test_kleine_punkte_k2d.py`.

## Tests

- neu `backend/tests/test_kleine_punkte_k2d.py` (11, davon 3 aus dem Review: Wartezeit aus 429 und `upstream_busy`, ohne Angabe):
  - Knopf;
  - Wartezeit, auch Unsinn;
  - Abnahme und Fortsetzen bei „ausgelastet“;
  - **Durchlauf W2/W3** durch Einlösen und „Plan fortsetzen“ (bisher nur generisch über M5);
  - `bei_fehler` bei `nachricht`;
  - `weiter: []` im Treiber.
- Studio: `ablauf-folge.spec.ts` (neuer Fall, ein angepasster), `architecture-reference.component.spec.ts`.
- grün: M5-Verträge, Abnahme, Prüfung, Treiber, K2c-Studio-Tests, Seeds, i18n.

## Betrieb

- Seed `03-patterns/m18-kuration.md` geändert: `boerdi import-config --werksabgleich`.
- Ein gespeicherter Ablauf mit `bei_fehler` an `nachricht` oder `verzweigung` bekommt beim nächsten Speichern
  den neuen Befund. Im Werksbestand gibt es keinen.
