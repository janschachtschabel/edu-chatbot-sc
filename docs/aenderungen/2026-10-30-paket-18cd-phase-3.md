# Änderungsnotiz — Paket 18C/D, Phase 3: `ui` neben `debug`, Fehlernummer

Stand 2026-10-30 · Basis `main` `9ee94ed` (Phase 1 und 2) · Plan
[`docs/plans/2026-10-29-paket-18cd-volle-umsetzung.md`](../plans/2026-10-29-paket-18cd-volle-umsetzung.md)

**Warum:** Der Debug-Block geht heute an jeden Client, auch an anonyme — Persona, Signale,
Entitäten, Spur. Phase 4 gibt ihn nur noch dem Studio. Damit das Widget danach weiterläuft,
bekommt jede Antwort hier **zusätzlich** einen öffentlichen Teil `ui` mit genau dem, was das
Widget braucht. Fehlerblasen nannten die Klasse der Ausnahme; jetzt nennen sie eine
Fehlernummer, die im Studio zum Zug führt. Für Widget und Chat ändert sich nichts Sichtbares
außer dem Satzende der Fehlerblasen.

| Was | Wie |
|---|---|
| `ui` (neu, öffentlich) | `UiInfo`: `pattern`, `intent`, `state`, `tools_called`, `modulations` (nur `tone`, `length`, `formality`, `card_text_mode`, `rag_areas`, `sources`, `_tone_modifier_override` — Begründungen, Kernregel und Zustandsübergang bleiben Diagnose); im Verlauf dazu `query_metas`, `web_links`, `type_focus`, `dokumente`, `topic_page_view`, `prepared_write`. Abgeleitet aus dem Debug-Block an der API-Grenze (`api/publikum`) — an `POST /api/chat`, am Strom-`result` und an jeder Nachricht des Verlaufs. `debug` bleibt in dieser Phase unverändert |
| `ist_interner_zug`, `darf_diagnose` | `ist_interner_zug` (Studio-Proxy nach Anmeldung, gültiger Studio-Schlüssel) entscheidet weiter über die Buchung auf `B_API_KEY`; `darf_diagnose` gibt Diagnose frei und zählt zusätzlich den reinen Entwicklungsmodus (`BOERDI_ALLOW_OPEN_ADMIN` ohne Schlüssel) |
| Fehlernummer | `error.internal`, `material.genFailed`, `material.createFailed` und neu `error.answerFailed` enden mit „(Fehlernummer: …)“ bzw. „(Error number: …)“ = die ersten 12 Zeichen der Trace-ID — auch ein Agent-Lauf, der an einem Modellfehler scheitert, und der `error`-Rahmen des Stroms (`nummer`); keine Fehlerklasse, kein Anbietertext im Canvas-Material; die Rückfallmeldung der Antwort ist jetzt zweisprachig |
| Suche nach Fehlernummer | Nummern unter 8 Zeichen werden genau gesucht (eine kurze Client-Trace-ID ist ganz die Nummer), ab 8 Zeichen weiter per Präfix |
| Auswertung | der Eval-Runner warnt einmal je Adresse, wenn eine Antwort ohne Debug-Block kommt; `run_golden` schickt `STUDIO_API_KEY` an die eigene Anlage und warnt sonst; Fehlerblasen von vor der Fehlernummer zählen weiter als solche |
| Vertrag | `ChatResponse.ui` und Schema `UiInfo` in `openapi-v1.json` und `openapi-public.json`; Muster der Suchroute `{1,128}` — eingetragen in `docs/api/bewusste-vertragszusaetze.md` |

## Was sich im Betrieb ändert

| Was | Muss | Kann |
|---|---|---|
| Image | Backend neu bauen und ausrollen (keine Migration, Widget unverändert) | |
| Fehlermeldungen von Nutzerinnen und Nutzern | | die Fehlernummer aus der Blase im Studio suchen (`GET /api/sessions/zug/{nummer}`, die Oberfläche folgt in Phase 4) |
| Golden-Läufe | | `STUDIO_API_KEY` in der Umgebung des Laufs setzen — ab Phase 4 Pflicht für Muster, Werkzeuge und Spur im Bericht |
| Host-Seiten und eigene Clients | | auf `ui` umstellen, wo sie bisher `debug` lesen (`pattern`, `intent`, `state`, `tools_called`; `persona`/`signals` gibt es öffentlich nicht) — ab Phase 4 fehlt `debug` ohne Freigabe |

## Prüfung

- Backend: neu `test_publikum.py`, `test_interner_zug.py`, `test_eval_ohne_diagnose.py`;
  Ergänzungen in `/api/chat`, Strom, Verlauf, Trace-ID (Fehlernummer, Wächter gegen `{kind}`),
  Suche (kurze Nummern), Auswertung; bisherige Erwartungen auf die Fehlerklasse bewusst auf die
  Fehlernummer umgestellt.
- OpenAPI-Gates grün nach Neuerzeugen.
- Unabhängiges Review (nur lesend): Befunde behoben bzw. begründet gelassen — im Plan-Log.
