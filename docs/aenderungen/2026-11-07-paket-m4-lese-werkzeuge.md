# Paket M4: neue und erweiterte Lese-Werkzeuge (2026-11-07)

Plan [`../plans/2026-11-07-mcp-vertrag.md`](../plans/2026-11-07-mcp-vertrag.md) (M4).

## Was sich ändert

- **`get_collection_overview`** (neu): eine Sammlung auf einen Blick, in einem Aufruf statt fünf. Titel,
  Pfad, Gliederung des Redaktionstexts, Statistik, die ersten Skills, Untersammlungen und Inhalte;
  `include` engt ein. Unbekannte Teile fallen weg, die Zahlen werden auf die Grenzen des Servers
  gekappt. Angeboten im Agent-Modus und in den Mustern M08 (Sammlungs-Drilldown) und M19
  (Qualitätssicherung).
- **`count_wlo_content_matches`** (neu): Trefferzahlen für bis zu 30 Anfragen zugleich, je mit den besten
  Treffern. Gedacht für die Abdeckung eines Lehrplans oder Entwurfs; die Beschreibung warnt, dass
  `total` auch schwache Treffer zählt. Angeboten im Agent-Modus und in M19.
- **`browse_collection_tree`:** Tiefe bis 3 (höchstens 300 Knoten, eine gekappte erste Ebene in
  `truncatedAt`).
- **`get_skill_registry` mit `task`:** Der Server wählt den passenden freigegebenen Skill und liefert
  dessen Anleitung samt Vorgaben der Redaktion gleich mit. Ist die Wahl nicht eindeutig, nennt er
  Kandidaten.
- Server-Register (`05-knowledge/mcp-servers.yaml`) und die Vertrauensgrenze (`test_untrusted_text`)
  kennen die neuen Werkzeuge; die `docs/dimensionen` sind neu erzeugt.

## Bewusst nicht gebaut

- **`resolve_wlo_filters`:** Unsere Argumentauflösung bildet Filter-Bezeichnungen schon vor jeder Suche
  ab (Vokabular-Cache, Ähnlichkeit, Modell als Rückfall). Sie auf den neuen Aufruf umzustellen, ändert
  jede Suche und ihre Zeiten. Das ist ein eigener Schritt mit Messung, kein Werkzeug für das Modell.
- **`get_node_details` mit `nodeIds`:** `get_nodes_details` deckt den Stapel schon ab.

## Review

Unabhängiges Review: 2 MAJOR, 11 MINOR, 3 NIT. Alle behoben bis auf die unten genannten Reste.

- **Skill über `task` (MAJOR):** Die mitgelieferte Anleitung wurde im Muster-Weg bei 4 000 Zeichen abgeschnitten,
  bei unklarer Wahl fiel das Urteil des Servers weg. Jetzt kommt die Anleitung ungekürzt an (wie bei `get_skill`),
  bei `ambiguous`/`none` steht der Kopf des Servers vor dem gekürzten Katalog. Erkannt wird die Form des Servers
  (seine Zeilen vor dem Dokument; Anleitung = H1 mit `nodeId:` darunter), nicht deutscher Text.
- **Skill über `task` merken (MAJOR):** Die gewählte Anleitung läuft wie nach `get_skill` — Faden für den
  Folgezug und die feste Ansage „… wird geladen“, in Muster- und Agent-Weg.
- **Zählung:** jede Anfrage einzeln geprüft (Kennung als Text, leere Filter weg, Altnamen
  `subject`/`educationalLevel`/`resourceType`); eine Anfrage mit fremdem Filter oder Überlänge fällt einzeln weg,
  statt den ganzen Aufruf zu kippen oder still ohne Filter gezählt zu werden. Bei persönlichen Daten gesperrt
  (`SPERRE_PERSOENLICH`).
- **Prompt-Sicht:** Übersicht und Zählung mit eigenem Deckel (12 000), Fehlzeilen („Nicht geladen“, „nicht
  gezählt“) nach vorn. Im Gruppiermodus nennt die Übersicht keine Einzelinhalte (nur ihre Zahl).
- **Cache:** Übersicht 180 s (wie Skills); eine Teilantwort (`missing`) wird nicht gespeichert;
  `get_skill_registry` mit `task` geht am Cache vorbei.
- **Argumente:** Übersicht nimmt `nodeId` als `collectionId` und einen Teil als Text; `task` wird auf 300 Zeichen
  gekürzt statt verworfen.
- **Beschreibungen:** „zählt über ganz WLO, nicht in einer Sammlung“ samt `fuzzyFilters`; „wann nicht“ bei der
  Übersicht; Hauptsatz von `get_skill_registry` nennt die Ausnahme `task`; Werkzeugliste im Antwort-Prompt: Tiefe 1
  bis 3.
- **M20:** „Ohne Anmeldung“ — Schritte 1–3 anonym, ab 4 Anmeldung; Ablaufbild: ein Aufruf mit
  `addToCollectionId`, der Chat löst ein.
- **Eval GV-RED-1 und Master-Skill:** Metadaten werden mit `lookup_wlo_vocabulary`/`lookup_wlo_publishers` belegt,
  nicht mit `wlo_suggest_metadata` (das braucht einen vorhandenen Datensatz); Zug 3 erwartet `wlo_create_content`.
  Im Master-Skill zusätzlich Dublette zuerst per `find_content_by_url`.

Offen (in `offene-befunde-und-todo.md`): `browse_collection_tree` Tiefe 3 als JSON im Muster-Weg strukturell
kürzen; `search_wlo_collections`/`search_wlo_within_collection` in `SPERRE_PERSOENLICH` (älter).

## Beim Deploy

- Seeds geändert: `03-patterns/m08-sammlung-drilldown.md`, `03-patterns/m19-qualitaetssicherung.md`, `03-patterns/m20-erschliessen.md` (Review),
  `05-knowledge/mcp-servers.yaml`. Übernehmen mit `boerdi import-config --werksabgleich`.
- MCP-Stand 07.11.2026 vorausgesetzt (wie M3).
- **Master-Skill neu einspielen** (Review-Fix: Metadaten belegen, Dublette per Adresse).
- **Eval-Erwartung GV-RED-1 geändert** (`seeds/eval/gold-flows.yaml`) — den Lauf startet der Nutzer.

## Tests

- `tests/test_mcp_vertrag_m4_review.py` (neu, 14): Sicht des Modells auf eine Skill-Wahl, Merken in beiden Wegen,
  Prüfung je Zählanfrage, Fehlzeilen vor dem Deckel, Gruppiermodus, Cache.

- `tests/test_mcp_vertrag_m4.py` (neu, 5): Teile und Grenzen der Übersicht, Kappung der Anfragen, Tiefe
  3, `task`, Register. Liefen vor dem Code rot.
- Bewusst geändert: `test_mcp_tool_defs.py` (Reihenfolge der Werkzeugliste, Tiefe wird auf 3 statt 2
  geklemmt).
