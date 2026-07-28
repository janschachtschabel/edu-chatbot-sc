# deploy

## Dev (P0-7)

```powershell
docker compose -f deploy/compose.dev.yml up -d --build
# backend http://localhost:8100/health · Jaeger UI http://localhost:16686
docker compose -f deploy/compose.dev.yml down          # Daten bleiben (Volume pgdata)
docker compose -f deploy/compose.dev.yml down -v       # inkl. DB-Daten
```

- Backend-Port **8100** (ALT belegt lokal 8000). Quellcode ist read-only
  gemountet; `--reload` greift bei jeder Änderung unter `backend/src/`.
- Dependency-Änderung (pyproject/uv.lock): `docker compose -f deploy/compose.dev.yml build backend`.
- Lokal ohne Docker: `cd backend && uv run uvicorn boerdi.main:app --reload --port 8100`
  (Postgres+Jaeger trotzdem via Compose starten).

## Prod-Image (P10-1)

```powershell
docker build -t boerdi-chat .    # Kontext ist die Repo-Wurzel, nicht backend/
```

**Ein** Image bedient alle drei Oberflächen: API (`/api`), Widget-Bündel
(`/widget`) und Studio-SPA (`/studio`) — ALT brauchte dafür drei, weil sein
Studio ein eigener Next.js-Server und seine Chat-Seite ein eigenes nginx war.

**Das Frontend wird im Image gebaut.** ALTs häufigster Deploy-Fehler steht in der
ersten Sektion seiner eigenen CLAUDE.md: `widget_dist` wird von Hand außerhalb
des Images gebaut, ein vergessenes `npm run build:widget` liefert also ein altes
Bündel aus, während Studio und Backend längst die neue Config zeigen. Hier gibt
es diesen Schritt nicht mehr — das Bündel kann nur das aus demselben Commit sein
(im Smoke-Lauf nachgewiesen: SHA-256 im Image = SHA-256 des lokalen Builds).

Migrationen laufen aus demselben Image, aber als **eigener Lauf** — nie aus dem
Web-Prozess, sonst fahren N Replikas gleichzeitig `alembic upgrade head`:

```powershell
docker run --rm -e DATABASE_URL=... boerdi-chat alembic upgrade head
```

Das Backend braucht **kein** beschreibbares Volume: die Config liegt in Postgres
(V2), und der einzige Laufzeit-Schreibzugriff im ganzen `src/`-Baum ist eine
Temp-Datei beim RAG-Datei-Ingest. Genau deshalb läuft der Prozess hier als
non-root (V12) — ALT hatte diesen Block auskommentiert, weil sein Container in
bind-gemountete Host-Pfade schrieb.

Ohne erreichbare Datenbank startet der Container **nicht** — gemessen: der
NOTIFY-Listener im Lifespan wartet gedeckelte 5 s (`ConfigChangeListener.
wait_connected`), und der TimeoutError beendet den Start mit Exit 3. Die
Deckelung ist explizit im Code; dass sie den Start abbricht, fängt niemand ab.
Für den Cluster ist das die brauchbarere Hälfte: eine Instanz ohne
Config-Invalidierung wäre eine, die stumm veraltete Config ausliefert. Praktisch
heißt es, dass Postgres vor den Backends stehen muss (in compose: `depends_on`
mit `condition: service_healthy`).

## Prod-Stack (P10-2)

```powershell
cd deploy
docker build -t boerdi-chat ..
docker compose -f compose.prod.yml --env-file .env up -d
```

Sieben Dienste: **traefik** (TLS + LB) · **backend ×N** (zustandslos) ·
**postgres** · **valkey** (Rate-Limit-Storage) · **migrate** (Einmal-Lauf) ·
**jaeger** · **pg-backup**.

**Kein TEI-Dienst.** Die P10-Zeile im Bauplan nennt ihn noch, V13 hat den
Sidecar aber am 2026-07-12 aus Kostengründen verworfen; `RERANK_URL` liest im
Backend niemand (gemessen). Ein Dienst, mit dem nichts sprechen kann, gehört
nicht ins Compose.

**Nur traefik veröffentlicht Ports.** Docker published Ports laufen an ufw
vorbei (ALT-Audit T-2) — ALT musste deshalb jeden Port einzeln an `127.0.0.1`
binden. Hier hat kein Anwendungsdienst ein `ports:`; einzige Ausnahme ist die
Jaeger-UI, bewusst host-lokal.

### `.env` (nicht im Repo)

Fünf Werte **müssen** gesetzt sein, sonst startet der Stack gar nicht erst —
ein Compose-Default für ein Passwort wäre ein ausgeliefertes Dev-Secret:
`POSTGRES_PASSWORD`, `STUDIO_API_KEY`, `STUDIO_PASSWORD`, `CORS_ORIGINS`,
`PUBLIC_HOST`, `ACME_EMAIL`. Prüfen ohne zu starten:

```powershell
docker compose -f compose.prod.yml --env-file .env config > $null   # Exit 0 = vollständig
```

Alles Weitere ist optional und leer = Code-Default; die kanonischen Namen
stehen in `backend/src/boerdi/settings.py`.

---

# Runbook

### Deployen / aktualisieren

```powershell
docker build -t boerdi-chat ..                                     # 1. Image
docker compose -f compose.prod.yml --env-file .env up -d migrate   # 2. Migration allein
docker compose -f compose.prod.yml --env-file .env up -d           # 3. Rest rollierend
```

Schritt 2 getrennt, weil ein Migrationsfehler dann sichtbar ist, bevor
Replikas neu starten. Der `migrate`-Dienst ist ein Einmal-Lauf; die Backends
warten per `service_completed_successfully` auf ihn.

**Abhängigkeit geändert (`pyproject.toml`/`uv.lock`)? Image neu bauen — sonst
Neustart-Schleife.** Beim Bauen von P10-2 real passiert: das Compose setzte
`RATE_LIMIT_STORAGE_URI=redis://…`, das Image stammte aber von vor `uv add
redis`. Ergebnis: `limits.errors.ConfigurationError: 'redis' prerequisite not
available` und drei Container in `Restarting (1)` statt `healthy`. `docker
compose ps` zeigt nur die Schleife, den Grund zeigt erst:

```powershell
docker compose -f compose.prod.yml logs backend | Select-Object -Last 20
```

**Seit P10-5 fängt CI genau das ab, bevor es auf den Server kommt.**
`.github/workflows/image.yml` baut `boerdi-chat` und fährt einen Smoke dagegen
(Migration aus demselben Image · `/health` 200 · Widget-Redirect auf die gehashte
URL · `/studio/` 200 · uid 1000 · HEALTHCHECK `healthy`) — mit
`RATE_LIMIT_STORAGE_URI=redis://…`, also unter derselben Bedingung, unter der der
Fehler oben aufgetreten ist. Er läuft auf `main` und bei PRs, die Dockerfile,
`pyproject.toml`/`uv.lock`, `backend/src`, alembic oder `frontend/` anfassen;
manuell über „Run workflow". **Er ersetzt die Regel nicht** — lokal gilt sie
unverändert, CI sieht nur, was gepusht wurde.

**Valkey statt Redis (P10-6).** Der Rate-Limit-Speicher ist `valkey/valkey:8-alpine`,
nicht Redis: Redis 8 steht unter RSALv2 / SSPLv1 / AGPLv3 — **alle drei auf der
Verbotsliste der Eisernen Regel 1** —, Valkey unter BSD-3-Clause. Gleiches
Protokoll, 42 statt 114 MB Image (Redis 8 bringt die Stack-Module mit, von denen
hier keines gebraucht wird). Das URI-Schema wählt auch den Client: `limits` liest
`valkey://` mit valkey-py und `redis://` mit redis-py, und nur ersteres ist
Abhängigkeit — eine übriggebliebene `redis://`-URI scheitert also laut beim Start,
statt still pro Prozess zu zählen.

**Neuer Dienst im Compose? Lizenz zuerst (C7).** Die Lizenz-Gates in CI sehen nur
Python- und npm-*Pakete* — genau deshalb konnte der Redis-Server als Image an
beiden vorbeilaufen. `backend/tests/test_image_licenses.py` prüft seit C7 jede
Image-Referenz im Repo gegen eine Positivliste mit belegter Lizenz und wird rot,
sobald ein Image dazukommt **oder ein Tag springt** (Redis war bis 7.2 noch
BSD-3-Clause). Ein neues Image also erst upstream nachlesen, dann dort eintragen.

Beim Umbenennen eines Dienstes bleibt der alte Container als Waise zurück und
hält seinen Port. Einmalig:

```powershell
docker compose -f compose.prod.yml --env-file .env up -d --remove-orphans
```

### Skalieren

```powershell
docker compose -f compose.prod.yml --env-file .env up -d --scale backend=5
```

Oder dauerhaft `BACKEND_REPLICAS=5` in der `.env`. Zustandslos, deshalb keine
Sticky-Sessions nötig — Session und Config liegen in Postgres (V2/V6). **Auf
einem 2-Kern-Server `BACKEND_REPLICAS=1`**: drei Replikas teilen sich dieselben
zwei Kerne und machen es langsamer, nicht schneller.

### Backup

Läuft von selbst (`pg-backup`, täglich, Aufbewahrung `BACKUP_KEEP_DAYS`, Default
14). Es ist eine `sleep 86400`-Schleife und kein cron: das offizielle
Postgres-Image bringt keinen Cron-Daemon mit, und ein zweites Image dafür wäre
mehr Lieferkette als Nutzen. Preis: der Takt verschiebt sich bei jedem Neustart
des Containers.

```powershell
docker compose -f compose.prod.yml exec pg-backup ls -lh /backup   # Dumps ansehen
docker compose -f compose.prod.yml exec pg-backup pg_dump -Fc -f /backup/vor-deploy.dump
```

Ein **fehlgeschlagener** Dump wird gelöscht statt halb liegen gelassen und
protokolliert `BACKUP FEHLGESCHLAGEN` — eine 0-Byte-Datei im Backup-Verzeichnis
wäre schlimmer als keine, weil sie wie ein Backup aussieht.

### Restore

```powershell
docker compose -f compose.prod.yml --env-file .env stop backend
docker compose -f compose.prod.yml exec pg-backup `
  sh -c 'pg_restore --clean --if-exists -d "$PGDATABASE" /backup/<datei>.dump'
docker compose -f compose.prod.yml --env-file .env start backend
```

Backends **vorher** stoppen: `--clean` wirft Tabellen weg, an denen sonst noch
laufende Turns hängen. Danach eine Config-Änderung im Studio speichern und
prüfen, dass sie ankommt (der NOTIFY-Kanal überlebt den Restore, die
Prozess-Caches werden erst durch das nächste NOTIFY frisch).

### Rollback

```powershell
docker tag boerdi-chat boerdi-chat:vorher        # VOR dem Build, sonst ist er weg
docker compose -f compose.prod.yml --env-file .env up -d
# zurück:
$env:BOERDI_IMAGE="boerdi-chat:vorher"; docker compose -f compose.prod.yml --env-file .env up -d
```

**Migrationen rollen nicht mit zurück.** Es gibt genau eine Migration (0001);
sobald eine zweite dazukommt, gehört zu jedem Rollback die Frage, ob das alte
Image mit dem neuen Schema läuft. Der sichere Weg ist der Restore oben.

### Logs & Traces

```powershell
docker compose -f compose.prod.yml logs -f backend      # alle Replikas gemischt
ssh -L 16686:127.0.0.1:16686 <server>                   # dann http://localhost:16686
```

Die Jaeger-UI ist absichtlich nur host-lokal gebunden: Traces enthalten
Prompt-Metadaten und gehören nicht ins Internet.

---

# Security-Checkliste vor dem Livegang

Aus dem Audit-Erbe (`../badboerdi/docs/audits/`), auf diesen Stack übersetzt.

| # | Punkt | Stand hier |
|---|---|---|
| T-2 | Docker-Ports laufen an ufw vorbei | ✅ Nur traefik veröffentlicht (80/443); Jaeger auf `127.0.0.1`. **Trotzdem prüfen:** `docker ps --format "{{.Names}} {{.Ports}}"` darf sonst nichts mit `0.0.0.0` zeigen. |
| T-9 | Prozess läuft als root | ✅ non-root uid 1000 (V12), im Image belegt (`docker exec … id`). |
| T-9 | Docker-Socket = root-äquivalent | ➗ traefik braucht ihn, bekommt ihn **`:ro`** und routet nur bei `traefik.enable=true`. Ein Socket-Proxy wäre die nächste Stufe, wenn traefik je Schreibrechte bräuchte. |
| — | Secrets | ✅ Keine Defaults im Compose (`:?`), keine `.env` im Image (im Smoke geprüft: kein Fund im ganzen Dateisystem). `.env` gehört dem Server, nicht dem Repo. |
| — | Log-Rotation | ✅ `json-file`, 10 MB × 3 je Dienst — unbegrenzte Logs haben ALT den Platz gefressen. |
| — | Rate-Limit | ✅ Default an (V7), Storage `valkey://` = ein Kontingent für den Cluster (`test_cluster_checklist.py`). |
| — | Admin-Oberfläche | ⚠️ Prüfen, dass `STUDIO_API_KEY` **und** `STUDIO_PASSWORD` gesetzt sind und `BOERDI_ALLOW_OPEN_ADMIN` **nicht** gesetzt ist. |
| — | CORS | ⚠️ `CORS_ORIGINS` explizit setzen. `*` ist zulässig, aber eine Entscheidung — nicht der Default aus Versehen. |
| — | Lasttest | ✅ `BOERDI_ALLOW_LOADTEST` leer = auf Prod abgelehnt; er teilt sonst den LLM-Pool mit Live-Nutzern. |
| — | TLS | ⚠️ Nach dem ersten Start prüfen, dass ACME wirklich ein Zertifikat gezogen hat (`docker compose logs traefik`), sonst hängt die Seite an der Selbstsignatur. |

Die §8-Cluster-Abnahme (Advisory-Lock, NOTIFY-Schranke, Rate-Limit, SSE über
LB, Graceful Shutdown) steht getrennt in
[../docs/cluster-checkliste.md](../docs/cluster-checkliste.md) — mit der klaren
Trennung, welche Punkte automatisiert sind und welche einen laufenden Cluster
brauchen.
