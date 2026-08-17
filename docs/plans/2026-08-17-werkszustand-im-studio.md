# Auslieferungsstand aus dem Image — im Studio, ohne SSH

Nutzer-Wunsch 2026-08-17: „kannst du im Studio nicht eine Option integrieren,
dass man den aktuellen Werkszustand aus dem Repo lädt?"

## 1. Ausgangslage (geprüft, nicht vermutet)

| Frage | Befund |
|---|---|
| Liegt der Seed im laufenden Container? | **Ja.** `Dockerfile:90` `COPY backend/seeds ./seeds`, `WORKDIR /app`, `config_seed_dir="seeds"` → `/app/seeds` |
| Gibt es die Import-Logik schon? | **Ja.** `seed_io.import_tree(src, put)` nimmt einen Rückruf — derselbe Code kann trocken vergleichen oder schreiben |
| Gibt es ein Studio-Panel-Muster? | **Ja.** `factory-panel.component.ts` mit `ActionState`, `AsyncData`, Scharfschalt-Bestätigung |
| Kommt ein Löschen im Cluster an? | **NEIN.** `trg_config_notify` feuert `AFTER INSERT OR UPDATE`, nicht bei `DELETE` (`0001_schema.py:153`) |

Der letzte Punkt ist der Grund, warum dieses Paket eine Migration enthält: die
Nutzer-Entscheidung „exakt gleichziehen" schließt Löschen ein, und ein Löschen
ohne NOTIFY wirkt auf einer Replika nicht.

**Der Werksstand des Studios ist etwas anderes** als der Seed: er ist eine
Momentaufnahme des *gelebten* Stands (`config_snapshots`, Zeile `factory`,
gespeichert über `POST /factory/save`). Der Seed ist der *Auslieferungsstand aus
dem Image*. Beide bleiben, sie beantworten verschiedene Fragen — „wie war es bei
uns" gegen „wie kommt es aus dem Build".

## 2. Entscheidungen des Nutzers

| Frage | Entscheidung |
|---|---|
| Umgang mit gepflegten Bereichen | **Zwei Knöpfe + Zählung**: „Fehlende nachziehen" (harmlos) und „Alles auf Auslieferungsstand" (hinter Bestätigung, mit automatischem Schnappschuss davor) |
| Bereiche löschen, die nur in der DB stehen | **Ja, exakt gleichziehen** |

Folge der zweiten Entscheidung, ausdrücklich: der zweite Knopf ist
**verlustbehaftet**. Die Zählung muss deshalb die Löschungen mitzeigen, und der
Schnappschuss davor ist nicht Komfort, sondern der einzige Rückweg.

## 3. Pakete

### S1 — NOTIFY auch beim Löschen (Migration)

Neue Alembic-Revision. Die Funktion muss `OLD` mitlesen, weil `NEW` beim DELETE
`NULL` ist:

```sql
CREATE OR REPLACE FUNCTION notify_config_changed() RETURNS trigger AS $$
BEGIN
  PERFORM pg_notify('config_changed', COALESCE(NEW.area, OLD.area));
  RETURN COALESCE(NEW, OLD);
END $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS trg_config_notify ON config_areas;
CREATE TRIGGER trg_config_notify AFTER INSERT OR UPDATE OR DELETE ON config_areas
  FOR EACH ROW EXECUTE FUNCTION notify_config_changed();
```

Das repariert zugleich den bestehenden `DELETE /api/config/file` — der hat
denselben Fehler, nur fällt er dort seltener auf.

### S2 — `services/seed_sync.py` (neu, ~110 Z.)

Zwei Funktionen, beide über `seed_io.import_tree` gespeist, damit Vergleich und
Schreiben nie auseinanderlaufen:

* `async def seed_lesen(pfad) -> dict[str, dict]` — der Seed als Bereichs-Abbild
* `def vergleiche(seed, live) -> SeedDiff` — rein, testbar ohne DB:
  `neu`, `gleich`, `abweichend`, `nur_in_db` (je Liste von Bereichs-Schlüsseln)
* `async def anwenden(diff, seed, modus, *, schreiben, loeschen) -> dict` —
  `"missing"` schreibt nur `neu`; `"exact"` schreibt `neu` + `abweichend` und
  löscht `nur_in_db`. **Erst schreiben, dann löschen**, damit ein Abbruch mitten
  im Lauf eine Obermenge des Seeds hinterlässt statt einer Lücke. Die beiden
  Rückrufe (gebaut: dieselbe Naht wie `import_tree`) halten das Modul von der
  Loader-Fassade frei und machen den Ablauf ohne Datenbank prüfbar
* `def seed_pfad(roh) -> Path | None` — absolut, sonst relativ zum
  Arbeitsverzeichnis (Bild: `/app`) **und** zu `backend/` (lokaler Start aus dem
  Wurzelverzeichnis). Kein Treffer ⇒ `None` ⇒ `available: false`

### S3 — Zwei Endpunkte (`api/config_snapshots.py`, Werksstand-Familie)

* `GET /api/config/seed` → `{available, area_count, neu, gleich, abweichend, nur_in_db}`
  (Listen, damit das Panel Namen zeigen kann, nicht nur Zahlen)
* `POST /api/config/seed/apply` mit `{"mode": "missing" | "exact"}` →
  `{written, deleted, snapshot_id}`; bei `exact` **zuerst** ein Schnappschuss
  `label="vor Auslieferungsstand"`

Fehlt das Seed-Verzeichnis (fremd gebautes Image, `CONFIG_SEED_DIR` falsch), ist
die Antwort `{available: false}` und der Panel-Abschnitt bleibt aus — kein 500,
und kein Knopf, der ins Leere greift.

### S4 — Studio: eigenes Panel `seed-panel.component`

Nicht in `factory-panel` hinein: das trägt schon vier Aktionen auf einer Zeile
und beantwortet eine andere Frage. Neues Panel unter dem Werksstand in
`backup.component.html`, plus zwei Methoden in `SnapshotsApi` und die i18n-Keys.

### S5 — Vertrag und Doku

Zwei neue Routen ⇒ `docs/api/openapi-v1.json` wird **absichtlich** neu erzeugt
(`uv run python scripts/export_openapi.py`). `deploy/README.md` bekommt den
Hinweis, dass der Weg über SSH (`docker compose run --rm migrate …`) damit für
den Regelfall entfällt.

## 4. Verifikation

```bash
uv run --directory backend pytest -q
uv run ruff check .
uv run --directory backend python scripts/export_openapi.py --check   # nach Neuerzeugung
cd frontend && npm test
```

Erwartung: Suite grün bis auf den vorbestehenden
`tests/test_auth.py::test_http_matrix_on_studio_route`; der OpenAPI-Check ist
**nach** dem Neuerzeugen grün und zeigt genau zwei neue Pfade.

Live gegen den lokalen Backend: `GET /api/config/seed` muss die echte Zählung
gegen den Seed im Repo liefern, und ein `{"mode":"missing"}` darf auf einer
vollständigen Datenbank **0** schreiben.

## 4a. Gemessen (17.08.2026)

| Prüfung | Befehl | Ergebnis |
|---|---|---|
| Backend-Suite | `uv run --directory backend pytest -q` | **3850 grün**, 1 rot (`test_http_matrix_on_studio_route`, vorbestehend: `/api/debug/mcp-test` antwortet 503 statt 401) |
| Linter | `uv run ruff check .` | „All checks passed!" |
| Vertrag | `export_openapi.py --check` | „openapi contract unchanged" — 91 → **93 Pfade**, neu genau `/api/config/seed` und `/api/config/seed/apply`, nichts entfallen |
| Studio | `npx ng test studio` | **980 grün** in 80 Dateien, davon 7 im neuen `seed-panel.component.spec.ts` (namentlich belegt) |

**S1 rot-grün belegt.** Gegen eine nur bis `0002` migrierte Datenbank kam auf
`LISTEN config_changed` **eine** Meldung (das INSERT), nach `0003` **zwei** —
`['t/rot']` gegen `['t/rot', 't/rot']`. Ohne diesen Nachweis hätte der neue Test
auch bei einer wirkungslosen Funktion bestanden: ein `tgtype`-Bitvergleich sieht
nicht, dass `NEW.area` beim DELETE `NULL` ist.

**Live gegen den echten Bestand** (eigener Prozess auf 8101, damit der laufende
unberührt bleibt):

```
GET  /api/config/seed        → available true · area_count 61
                               gleich 61 · neu 0 · abweichend 0 · nur_in_db 0
POST /api/config/seed/apply  {"mode":"missing"} → {"written":0,"deleted":0,"snapshot_id":null}
POST /api/config/seed/apply  {"mode":"unfug"}   → HTTP 422
```

Die Planzahl „35 Bereiche" war veraltet — der ausgelieferte Baum trägt heute
**61**. Datenbank und Abbild stehen gleich; der harmlose Lauf schreibt wie
erwartet nichts.

## 5. Grenzen

* **Der zweite Knopf bleibt verlustbehaftet.** Kein UI-Text macht daraus eine
  sichere Aktion; der Schnappschuss davor ist der Rückweg, nicht die Absicherung.
* **Der Knopf lädt nichts nach.** Er liest den Baum aus dem *laufenden Abbild* —
  also den Stand des Commits, aus dem es gebaut wurde. „Neueste Konfiguration
  aktivieren" heisst weiterhin: Abbild bauen, deployen, dann drücken. Der Gewinn
  ist der entfallende SSH-Schritt und die Vorschau, nicht ein übersprungenes
  Deployment.
* **Die Auto-Schnappschüsse häufen sich an.** Jeder scharfe Lauf legt einen
  neuen an, und keiner räumt auf; bei `MAX_SNAPSHOTS = 50` verweigert der
  Endpunkt dann den Lauf (400) statt ohne Rückweg zu arbeiten. Aufräumen bleibt
  Handarbeit im Schnappschuss-Panel — bewusst, weil automatisches Löschen von
  Rückwegen die falsche Voreinstellung wäre.
* **Nur Config.** Sitzungen, Gedächtnis, Qualitätslogs und RAG-Abschnitte bleiben
  unberührt — dieselbe Zusage wie beim Werksstand (`_apply_config` schreibt
  ausschließlich Config-Bereiche).
* **Die Skills selbst sind nicht betroffen.** Freigegebene Anleitungen kommen zur
  Laufzeit über den MCP-Server aus edu-sharing; kein Seed-Import erreicht sie.
* Commit, Image-Bau (Backend **und** Studio) und Deploy bleiben beim Nutzer.
