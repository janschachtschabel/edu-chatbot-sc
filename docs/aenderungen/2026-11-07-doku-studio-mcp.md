# Doku und Studio-Infotafel zum MCP-Stand 07.11.2026 (2026-11-07)

Auftrag des Nutzers: prüfen, ob README, Doku und die Infotafel im Studio die neuen MCP-Fähigkeiten und Werkzeuge
richtig beschreiben. Ergebnis und Korrekturen:

## Geprüft, bereits aktuell

- **README** (`README.md`): vorausgesetzter MCP-Stand und Verweis auf den Plan (seit M7).
- **`docs/mcp-und-anmeldung.md`**, **`docs/mcp-feedback-werkzeuge.md`**, **`docs/ui-module.md`**,
  **`docs/uebergabe-betrieb.md`**, **`docs/offene-befunde-und-todo.md`** (seit M7 bzw. Review).
- **Studio, Seite „Agent & Maschine“ → „Werkzeuge und Sperren“**: die Liste kommt live aus dem Werkzeugkatalog
  (`services/agent_tool_overview.py`) — die neuen Werkzeuge stehen dort samt Beschreibung und Sperren.
- `docs/browser-plugin-einbindung.md` (Metadaten-Vorschlag nur mit Anmeldung): stimmt weiter.

## Korrigiert

- **Studio-Infotafel „Wissensquellen: RAG und MCP“** (DE/EN): zwei neue Punkte — der strukturierte Antwortteil ist
  verbindlich (Fehlercodes, Bestätigungsschlüssel, Plan-Stand; vorausgesetzt der MCP-Stand vom 07.11.2026) und
  Schreiben (zweistufig, Anlegen und Einsortieren in einer Bestätigung, Pläne mit „Weiter anlegen“). Der Zugang
  sagt jetzt, dass kuratierende Werkzeuge Schreibrecht brauchen und im Muster-Modus ausdrücklich genannt sein müssen.
- **Studio-Infotafel „Zwei Maschinen“, Zeile „Schreiben“** (DE/EN): „nur mit Schreibrecht“ (persönliche Anmeldung
  oder das freigegebene Gastkonto — vorher hieß es nur „persönliche Anmeldung“), dazu Pläne und „Weiter anlegen“;
  über `/api/agent` nur als Vorschlag.
- **`docs/architektur.md`**:
  - §4.4: `client.py` mit `call_mcp_tool_antwort` und dem strukturierten Teil, `tool_cache.py` richtig beschrieben
    (Frist je Werkzeug, nicht „je Zug“).
  - §5.1: falsche Aussage zu `skipCount` entfernt (`_within_collection` kennt jetzt `excludeNodeIds`), unbekannte
    Lizenz; neue Zeilen `get_collection_overview`, `browse_collection_tree`/`get_collection_contents`/
    `get_collection_stats`, `count_wlo_content_matches`, `find_content_by_url`.
  - §5.3: `get_skill_registry` mit `task`.
  - §5.4: Schreibweg nach dem neuen Vertrag (Schlüssel aus `structuredContent.confirm`, Einlösen im Vorlauf,
    Neu-Vorlage, `error.code`), `addToCollectionId`, Pläne, Stapel-Ablage nur über das Upload-Modul.
- `frontend/README.md`: die historische Zahl „zwölf Werkzeuge“ als damaliger Stand gekennzeichnet; ein Kommentar in
  `reference-flow-data.ts` ohne die veraltete Zahl.

## Tests

- Studio: `architecture-reference.component.spec.ts` — Zeile „Schreiben“ jetzt „nur mit Schreibrecht“ und „Weiter
  anlegen“; neuer Test: der MCP-Abschnitt nennt `structuredContent`, den MCP-Stand und „Weiter anlegen“. 1970 grün.
