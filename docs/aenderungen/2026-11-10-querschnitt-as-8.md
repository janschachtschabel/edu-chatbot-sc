# Querschnitts-Review AS-8 (Probe, Trockenlauf, Handbuch) — Behebungen (2026-11-10)

Plan: `docs/plans/2026-11-09-ablaeufe-im-studio.md` §5n. Das Review folgte den Wegen Ende zu Ende:
- Knopf am Ablauf → Vorschau → Widget → Backend → Treiber → Leiste;
- Schreiben, Auftrag, Ablage und Vorgänge in der Probe;
- Ausfälle (Cookie, Klassifikator);
- Handbuch gegen Code.

**Was trägt:** Recht einmal entschieden, Merker getrennt (`aktiv`/`recht`), eine Schranke für
MCP-Schreiben, Trocken-Aufträge, Besitz `probe:<Sitzung>`, synchroner Start im Widget, gleiche
Grenzen der Startdaten in Studio, Widget und Backend.

**Gefunden:** 0 kritisch, 2 schwer, 4 mittel, 3 klein. Beide schweren Befunde lagen im
ausgeschalteten Beispiel und im Handbuch, nicht im Probe-Mechanismus. Alle sind am Code bestätigt
und behoben.

| # | Schwere | Befund | Behebung |
|---|---|---|---|
| 1 | schwer | „Sammlung prüfen“: Der Dienst `abdeckung_zaehlen` liefert bei einem Ausfall `{gezaehlt: 0, …}`, nie `None`. `bei_fehler: ohne_zahlen` griff also nicht, und die Person las „Bei 0 von 0 Punkten …“. Der Testfall mit `null` stellte einen Fall nach, den es im Betrieb nicht gibt. | Verzweigung `gezaehlt` (`wenn_wert` größer 0 → `zeigen`, sonst `ohne_zahlen`). Testfälle „Zählung ohne Ergebnis“ (`gezaehlt: 0`) und „Zählung gesperrt“ (`null`). Im Handbuch die Regel „Werkzeug so nachstellen, wie es im Betrieb antwortet“. Test `test_ablauf_beispiele`. |
| 2 | schwer | Der KI-Schritt hatte nur `ui_strukturabgleich`; der Dienst verlangt eine Kennung, der Text lädt zu einem Namen ein — die KI hätte raten müssen. | `search_wlo_all` dazu (die Liste erlaubter lesender Werkzeuge kennt `search_wlo_collections` nicht; `search_wlo_all` findet Sammlungen). Hinweis an die KI: Namen per Suche auflösen. Seed, Handbuch, Notiz AS-8c, Test. |
| 3 | mittel | In der Probe startete ein Auftrag ohne WLO-Anmeldung, im Betrieb nicht — Widerspruch zwischen P-5 und P-8. | **Entscheid: P-8 geht vor.** Der Trocken-Starter braucht die Anmeldung wie im Betrieb; übersprungen werden nur b-api und Schlüssel. Test zuerst (rot, dann grün). Plan P-5, Notiz AS-8a, Vertragsliste und Handbuch angeglichen. |
| 4 | mittel | Die Vertragszeile sagte „ohne Cookie wirkungslos“, weiter hinten „403“. | „sonst 403 `probe_ohne_recht` — nie ein echter Zug“. |
| 5 | mittel | Das Handbuch verschwieg, dass ein freigegebener Schreibschritt in der Probe nur `{trockenlauf, werkzeug}` als Teil hinterlässt. | Satz im Kapitel „Im Widget ausprobieren“: Folgeschritte auf Kennungen des Angelegten prüft ein Testfall mit `eingaben.ergebnis`. |
| 6 | mittel | Die Tabelle der Testfall-Felder war unvollständig. | `quelle`, `angemeldet`, `gewaehlt`, `seite`, `eingaben.bei`/`teile`/`freigabe: ja` ergänzt. |
| 7 | klein | Bausteine: Verzweigung ohne `wenn_teil`/`wenn_gewaehlt`; `optionen`/`freitext` nur bei `nachricht`. | Nachgetragen. |
| 8 | klein | `probe` fehlte in der Tabelle „was zur Laufzeit noch wirkt“. | Eingetragen, mit dem Hinweis, dass die Sitzung im Backend Probe bleibt. |
| 9 | klein | Plan P-3 nannte einen alten Text; der Stand sagte „Review folgt“. | Nachgezogen. |

**Hinweis (vorbestehend, nicht behoben):** Sitzungen der Vorschau, auch Probe-Sitzungen, zählen in
`services/session_origin` als `production` (Kosten, Nutzung, Qualität). Das galt schon für die
gewöhnliche Vorschau; eingetragen in `offene-befunde-und-todo.md`.

**Prüfung:**
- `test_ablauf_beispiele`: 6 grün.
- `test_probe`, `test_ablauf_auftrag` und `test_ui_auftrag_api`: 112 grün.
- Seed: Prüfen ohne Befund, 5 Testfälle grün.
