# Paket M7: Doku, README, Master-Skill zum MCP-Stand 07.11.2026 (2026-11-07)

Plan [`../plans/2026-11-07-mcp-vertrag.md`](../plans/2026-11-07-mcp-vertrag.md) (M7). Abschluss der Pakete M1–M6.

## Was sich ändert

- **Master-Skill** (`docs/skills/vorgehen.md`, `-kompakt`, `-knapp`) und Seeds `m08`, `m19`, `m20`:
  - M08: erster Überblick über eine Sammlung mit `get_collection_overview` (ein Aufruf), gezielt weiter wie bisher.
  - M19: `count_wlo_content_matches` für die Abdeckung vieler Themen — zählt über ganz WLO, nicht in der Sammlung.
  - M18: Pläne (`wlo_create_collection_tree`, `wlo_add_to_collections`) — eine Vorschau, ein Ja für alles; „Weiter
    anlegen“ bietet der Chat selbst an, das Modell setzt nicht fort.
  - (Schon in M3/M4: Dublette per Adresse, Anlegen mit Sammlung, Metadaten mit Vokabularen belegen.)
- **README:** der vorausgesetzte MCP-Stand und ein Verweis auf den Plan.
- **`docs/mcp-und-anmeldung.md` §5:** Fehlercodes `login_*`, Verzweigen über `structuredContent`, Pläne nur im
  Vorlauf und nur für dieselbe Person.
- **`docs/mcp-feedback-werkzeuge.md` §6:** welche Wünsche der Server umgesetzt hat und was der Chatbot davon nutzt.
- **`docs/ui-module.md`, Modul-README `ui-upload`:** die letzten Ablagen.
- **`docs/offene-befunde-und-todo.md`:** Plan-Eintrag, Deploy-Schritte (§4), Zurückgestelltes (§6), T1b erledigt.
- **Studio:** keine Änderung nötig — Werkzeuglisten (Agent), Server-Register und Muster kommen aus Katalog bzw. Seeds;
  die neuen Werkzeuge erscheinen dort von selbst.

## Review

Doku-Review: 0 MAJOR, 6 MINOR, 7 NIT, alle behoben:
- Master-Skill: M08 auch in `-knapp`; M18 Schritt 4 sagt, dass der Chat das Ja zu einem Plan selbst einlöst (nicht
  erneut aufrufen); M20 nennt `addToCollectionId` und das Einsortieren eines vorhandenen Datensatzes; der Chip bei
  einer geeigneten Seite heißt „Metadaten belegen“ statt „vorschlagen“.
- Seeds: m20 schränkt `wlo_suggest_metadata` auf vorhandene Datensätze ein; m08 nennt `get_collection_overview` in
  der Pipeline; m19 sagt in der Kernregel, dass die Zählung über ganz WLO geht.
- `offene-befunde-und-todo.md`: Verweise (§3/§4/§6, M1–M7), Voraussetzung der Stapel-Ablage (nur noch
  `WLO_BATCH_UPLOAD_ENABLED`), Bündelgröße, „Image neu bauen“ statt `npm run build:widget`.
- `uebergabe-betrieb.md` nennt den vorausgesetzten MCP-Stand; T1b im U3-Plan als erledigt markiert; Musternamen im
  Feedback-Dokument eindeutig.

## Beim Deploy

- **Master-Skill neu in den WLO-Knoten übertragen** (alle Änderungen aus M3, M4 und M7).
- Übrige Schritte gesammelt in `offene-befunde-und-todo.md` §4 („MCP-Vertrag“).

## Tests

- Master-Skill-Wächter (`tests/test_master_skill*.py`, `tests/test_check_master_skill.py`) grün; volle Suite am Ende.
