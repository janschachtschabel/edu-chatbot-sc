# Plan: Chatbot an den neuen MCP-Vertrag anpassen (2026-11-07)

Auftrag des Nutzers (07.11.): Der WLO-MCP läuft mit dem neuesten Stand. Den Chatbot selbstständig anpassen —
Änderungen, Ergänzungen, Studio, README, Doku — Paket für Paket, nach jedem Paket Review mit Befundbehebung.

Grundlage: Bericht des MCP-Entwicklers „WLO-MCP: Neues für BOERDi“ (Stand 07.11., inkl. unserer 11 Punkte) und
`wlo-mcp-server-sc/docs/MCP-REFERENZ.md` §2. Live geprüft am 07.11.: 47 Werkzeuge (Stapel-Ablage aus), neue
Werkzeuge da; Fehler tragen `structuredContent.error.code`; `missing`; unbekannte Lizenz → 0 Treffer mit
`unresolvedFilters` in `structuredContent`.

Ausgangslage (Bestandsaufnahme 06./07.11.): Der Chatbot liest fast alles als Text; `call_mcp_tool` macht aus
jedem Fehler `"MCP error: <Text>"`; die Schreib-Abnahme hängt am deutschen Vorschautext (Regex auf
`confirmToken:`); Stapel-Gründe heißen bei uns noch `unknown/expired/mismatch`; `excludeNodeIds` wird in
`skipCount` umgerechnet; eine Lizenz, die wir nicht abbilden, lassen wir still weg; kein `login_required`.

Leitregeln: `structuredContent` ist verbindlich, Text nur Rückfall; Verzweigen über `error.code`, nie über
deutschen Text; Schreiben bleibt hinter Abnahme und Anmeldung (`has_personal_auth`); keine neuen Abhängigkeiten.

## Pakete

### M1 — Antwortvertrag im Client
1. Fehler mit Code: der Transport behält `structured.error` (`code`, `message`, Zusatzfelder); ein
   `McpAntwort`-Ergebnis (Text, Art, Code, strukturierter Teil) für die Aufrufer, die verzweigen müssen;
   das Modell sieht den Code mit (`MCP error [code]: …`).
2. `login_required` / `login_rejected` → wie eine abgelehnte Anmeldung (Knopf „Anmelden“).
3. Stapel-Ablage: Gründe `batch_unknown/expired/mismatch` (alte Namen bleiben als Rückfall).
4. `search_wlo_within_collection`: `excludeNodeIds` durchreichen (keine Umrechnung in `skipCount`).
5. Lizenz: nicht abbildbare Lizenz unverändert an den Server (der antwortet ehrlich mit 0 und Vorschlägen);
   `unresolvedFilters`/`facets` aus `structuredContent` lesen (Text-`_queryMeta` als Rückfall).

### M2 — Schreib-Abnahme aus `structuredContent.confirm`
Schlüssel und Vorschau aus `confirm` (Text als Rückfall); Vorschau-Kasten aus `preview.fields`/`items`;
`unchanged: true` → „nichts zu ändern“, keine Abnahme; `confirm_expired/mismatch/unknown` → eigene Texte mit
neuer Vorschau; `timeout` mit `outcomeOpen: false` → gefahrlos wiederholbar, `true` → „erst nachsehen“;
`exists` (`error.existing`) → vorhandenen Datensatz anbieten.

### M3 — Anlegen mit Sammlung in einer Bestätigung
`wlo_create_content` mit `addToCollectionId`, `find_content_by_url` als Lese-Werkzeug; Muster m18/m20 und
Master-Skill-Vorgehen anpassen (Dublette zuerst prüfen, eine Abnahme statt zwei).

### M4 — Neue und erweiterte Lese-Werkzeuge
`resolve_wlo_filters`, `get_collection_overview`, `count_wlo_content_matches`, `get_node_details` mit
`nodeIds`, `browse_collection_tree` Tiefe 3, `get_skill_registry` mit `task`; Argument-Modelle,
Werkzeugkatalog, Studio (Freigabe/Beschreibungen), Seed `05-knowledge/mcp-servers.yaml`.

### M5 — Pläne: Sammlungsbaum und Massen-Aufnahme
`wlo_create_collection_tree`, `wlo_add_to_collections` hinter derselben Abnahme; nach der Bestätigung führt
das Backend den Plan mit `continuationToken` fort (im Zug bis zur Frist, sonst Knopf „Weiter anlegen“),
zeigt `progress`; `plan_*`, `too_many_plans`, `inProgress`. Eingang aus dem Strukturentwurf („In WLO anlegen“)
als eigener Schritt, wenn M5 steht.

### M6 — Letzte Ablagen
`wlo_list_my_batches` (nur mit eingeschalteter Stapel-Ablage) für „letzte Ablagen“ (T1b).

### M7 — Doku, README, Studio
`docs/ui-module.md`, `offene-befunde-und-todo.md`, `uebergabe-betrieb.md`, Backend-README, Studio-Texte; je
Paket eine Änderungsnotiz `docs/aenderungen/2026-11-07-paket-m<n>-*.md`.

## Stand

- **M1** fertig, reviewt (3 MAJOR, 6 MINOR, 3 NIT behoben) — `aenderungen/2026-11-07-paket-m1-antwortvertrag.md`.
- **M2** fertig, reviewt (1 MAJOR, 8 MINOR, 2 NIT behoben) — `aenderungen/2026-11-07-paket-m2-abnahme.md`.
  Abweichung: Vorschau-Kasten bleibt Textfassung des Servers (zeigt eher zu viel als zu wenig).
- **M3** fertig, reviewt (2 MAJOR, 8 MINOR, 1 NIT behoben) — `aenderungen/2026-11-07-paket-m3-anlegen-mit-sammlung.md`.
- **M4** fertig, reviewt (2 MAJOR, 11 MINOR, 3 NIT behoben) — `aenderungen/2026-11-07-paket-m4-lese-werkzeuge.md`.
  Abweichung: `resolve_wlo_filters` und `get_node_details` mit `nodeIds` bewusst nicht gebaut (Begründung in der
  Notiz; offen in `offene-befunde-und-todo.md`).
- **M5** fertig — `aenderungen/2026-11-07-paket-m5-plaene.md`. Abweichung: kein selbsttätiges Fortsetzen im Zug;
  fortgesetzt wird über den Knopf „Weiter anlegen“ (ein Abschnitt dauert bis ~40 s, zwei hintereinander sprengten
  die Zugfrist). Der Eingang aus dem Strukturentwurf bleibt eigener Schritt. Reviewt (3 MAJOR, 6 MINOR, 3 NIT),
  Nachprüfung (1 MAJOR: Pläne löst nur der Vorlauf ein) und Nachtrag aus dem M6-Review behoben.
- **M6** fertig, reviewt (1 MAJOR, 3 MINOR, 3 NIT behoben) — `aenderungen/2026-11-07-paket-m6-letzte-ablagen.md`.
  Die letzten Ablagen kommen mit `vorbereiten` (kein eigener Aufruf, keine Anzeige im Chat-Text).
- **M7** fertig — `aenderungen/2026-11-07-paket-m7-doku.md`: README, `mcp-und-anmeldung.md`,
  `mcp-feedback-werkzeuge.md`, `ui-module.md`, Modul-README, `offene-befunde-und-todo.md` (Deploy, Zurückgestelltes),
  Master-Skill (Übersicht, Zählung, Pläne), `uebergabe-betrieb.md` (vorausgesetzter MCP-Stand). Studio: keine
  eigenen Texte nötig (Werkzeuglisten und Register kommen aus dem Katalog bzw. den Seeds). Das Backend-README
  bleibt: es beschreibt Widget-Auslieferung und Evaluation, nichts davon ändert sich. Doku-Review: 0 MAJOR,
  6 MINOR, 7 NIT behoben.
