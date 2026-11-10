# Paket TB-E2: Studio-Vorschau und Proben zählen nicht als Betrieb (2026-11-10)

Plan `plans/2026-11-10-themenbaum-aus-inhalten.md` §4, Gruppe E. Grundlage ist der Nutzer-Entscheid
N3: „Nein, eventuell gesondert ausweisen.“

**Vorher:** Die Herkunft einer Sitzung hing allein am Präfix ihrer Kennung
(`services/session_origin.py`). Die Widget-Vorschau im Studio nutzt das echte Widget (`bb-…`). Ihre
Gespräche zählten in Auswertung, Kosten, Nutzung und Sitzungsliste als Betrieb, auch die Proben
(Trockenlauf, `entities._probe`).

**Jetzt:**

- **Marke an der Sitzung:**
  - Das Studio setzt an der Vorschau das neue Widget-Attribut `vorschau`; jeder Zug trägt dann
    `vorschau: true`.
  - Mit gültigem Studio-Cookie merkt `setup` die Sitzung (`entities._vorschau`), so wie die Probe.
  - Ohne gültiges Cookie bleibt das Flag wirkungslos, **ohne** 403. Es schränkt nichts ein, anders
    als `probe`.
  - Ohne Flag wird das Cookie nicht gelesen. So zählt ein abgelaufenes Cookie auf Gastseiten nicht
    als Fehlversuch.
  - Eine Probe ist immer auch Vorschau.
- **Spalte statt Marke** (nach dem Review, Befund 1): Die Aufbewahrung leert `entities` nach der
  Frist der Gesprächsverläufe (Vorgabe 30 Tage). Eine Marke dort ginge also verloren, und jede
  Vorschau-Sitzung zählte danach wieder als Betrieb.
  - Darum gibt es die Spalte `sessions.vorschau` (Migration **0022**, Vorgabe `false`, mit Teilindex
    `ix_sessions_vorschau`).
  - `setup` setzt sie, sobald die Marke neu ist (`db_sessions.vorschau_markieren`).
  - Die Migration übernimmt vorhandene Marken (`_probe`, `_vorschau`).
- **Herkunft:**
  - `scope=production` schließt Sitzungen mit `vorschau` aus.
  - Der neue Wert `scope=probe` zeigt nur sie.
  - Der Filter ist ein statisches `NOT IN (SELECT … FROM sessions WHERE vorschau)`
    (`PROBE_SITZUNGEN_SQL`, über den Teilindex) und gilt für die rohen SQL-Abfragen der Qualität
    wie für die Core-Abfragen (Nutzung, Kosten, Sitzungsliste).
  - `session_id` ist Primärschlüssel, also trifft `NOT IN` auf kein NULL.
  - `probe` enthält nur die Widget-Vorschau. Der Chat-Probelauf der Agent-Seite (`studio-`) und
    „Auftrag testen“ (`studio-probe`) sind weder Betrieb noch `probe`; sie stehen unter „Alle“.
    Der Hinweis im Studio sagt das.
- **Studio:** In der Datenbasis gibt es die vierte Wahl „Nur Studio-Vorschau“. Der Hinweis zu
  „Produktion“ sagt jetzt, dass die Vorschau nicht mitzählt.
- **Vertrag:** Neu sind das Feld `ChatRequest.vorschau` und der Scope-Wert `probe`
  (`bewusste-vertragszusaetze.md`, beide OpenAPI-Dateien neu erzeugt). Das Attribut steht in
  `browser-plugin-einbindung.md`.

**Grenzen:**

- Gespräche der Vorschau **vor** diesem Stand tragen keine Marke und bleiben im Betrieb. Proben
  (`_probe`, seit AS-8) übernimmt die Migration.
- Löscht der Betrieb Sitzungen ohne ihre Qualitäts- oder Nutzungszeilen (`purge_all` mit
  `quality_logs=False`), verlieren diese Zeilen die Marke und zählen wieder als Betrieb
  (Querschnitts-Review, Befund 9). Die Aufbewahrung selbst löscht Sitzungen nicht.
- Die Marke klebt an der Sitzung, auch wenn das Attribut wegfällt. Die Vorschau baut jedes Mal ein
  neues Element mit neuer Sitzung.

**Review** (unabhängig): 1 MAJOR, 3 MINOR, 3 NIT. Sicherheit und SQL waren sauber
(`text()` erkennt in `::jsonb` keinen Parameter, die Unterabfrage korreliert nicht).

- **MAJOR:** Die Aufbewahrung leerte die Marke. Behoben durch die Spalte (siehe oben).
- **MINOR:** Die Verdrahtung war ungetestet. Jetzt prüft `test_probe` den Setup-Weg bis zur Spalte.
- **MINOR:** Die PG-Tests deckten nur `_probe` ab. Neu:
  - die Spalte;
  - „die Aufbewahrung nimmt die Herkunft nicht mit“;
  - die Migration mit Rückweg.
- **MINOR:** Leistung: der Teilindex.
- **NIT:** Der Test „Probe ist Vorschau“ prüft jetzt beide Richtungen.
- **NIT:** Die Beschreibung von `scope` an `/api/eval/*` ist berichtigt.
- **NIT:** Der Hinweis zu „Nur Studio-Vorschau“ ist klarer.

**Prüfung:**

- **Neue Tests, zuerst rot:**
  - Backend: `test_vorschau_marke.py` (9 Fälle), Herkunft in `test_session_origin.py`,
    `test_sessions_admin_pg.py` und `test_quality_pg.py` (Postgres).
  - Frontend: Draht (`chat-api-probe.spec`), Widget-Attribut, Studio-Datenbasis, Studio-Vorschau.
- **Backend** rund um Chat, Vertrag, Nutzung, Kosten, Qualität und Sitzungen: 414 grün.
- `export_openapi --check` ohne Abweichung, `check-docs-attributes` sauber, ruff sauber.
- Nach dem Review: die Herkunfts-, Probe- und Setup-Tests mit Postgres und
  `test_migration_sitzung_vorschau` grün (113 + 2); `ng test studio` grün.

**Deploy:** Migration **0022** im `migrate`-Dienst (schnell: eine Spalte mit Vorgabe, ein Teilindex).
Das Image neu bauen, weil sich Widget und Studio geändert haben.
