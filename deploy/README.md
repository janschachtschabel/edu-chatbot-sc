# deploy

## Dev (P0-7)

```bash
docker compose -f deploy/compose.dev.yml up -d --build
# backend http://localhost:8100/health · Jaeger UI http://localhost:16686
docker compose -f deploy/compose.dev.yml down          # Daten bleiben (Volume pgdata)
docker compose -f deploy/compose.dev.yml down -v       # inkl. DB-Daten
```

- Backend-Port **8100** (ALT belegt lokal 8000). Quellcode ist read-only
  gemountet; `--reload` greift bei jeder Änderung unter `backend/src/`.
- Dependency-Änderung (pyproject/uv.lock): `docker compose -f deploy/compose.dev.yml build backend`.
- Lokal ohne Docker: `cd backend && uv run uvicorn boerdi.main:app --reload --port 8100`
  (Postgres+Jaeger trotzdem via Compose starten). Das ist nur der öffentliche Port.
- Lokal wie im Image (beide Ports): `cd backend && uv run python -m boerdi.serve` — 8100
  öffentlich, 8101 intern (`/health`, `/ready`, `/metrics`, `/openapi-full.json`); ohne `--reload`.

## Prod-Image (P10-1)

```bash
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

```bash
docker compose -f compose.prod.yml --env-file .env up migrate
```

Der `migrate`-Dienst bekommt dabei, was die erste Migration braucht: `0001` legt die
Vektor-Spalte mit der Dimension aus `LLM_PROVIDER`/`LLM_EMBED_MODEL`/`EMBED_DIM` an. Ein
nacktes `docker run … alembic upgrade head` ohne diese Werte rät die Dimension.

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

```bash
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

Sechs Werte **müssen** gesetzt sein, sonst startet der Stack gar nicht erst —
ein Compose-Default für ein Passwort wäre ein ausgeliefertes Dev-Secret:
`POSTGRES_PASSWORD`, `STUDIO_API_KEY`, `STUDIO_PASSWORD`, `CORS_ORIGINS`,
`PUBLIC_HOST`, `ACME_EMAIL`. `CORS_ORIGINS` **wirkt erst mit**
`CORS_ALLOW_ALL=false` — die Vorgabe ist offen, siehe Abnahme-Zeile unten. Prüfen ohne zu starten:

```bash
docker compose -f compose.prod.yml --env-file .env config > /dev/null   # Exit 0 = vollständig
```

Alles Weitere ist optional und leer = Code-Default; die kanonischen Namen
stehen in `backend/src/boerdi/settings.py`.

#### `MCP_SERVER_URL` — die korrekte Adresse

```
MCP_SERVER_URL=https://wlo-mcp.87.106.195.152.nip.io/mcp
```

Das ist der WLO-MCP-Server, gegen den boerdi-chat läuft (lesende und kuratierende
Werkzeuge; der aktuelle Katalog kommt über `tools/list`, siehe unten). Weitere MCP-Server
lassen sich seit Paket 11 **nur lesend** einbinden — ihre Werkzeuge heißen im Zug
`server__werkzeug` (Studio → Gemeinsam → „Werkzeuge“). Die frühere Vercel-Instanz ist **abgelöst** — ihr fehlte
`get_wlo_content_text`, weshalb M17 („Inhalt anzeigen") dort ins Leere rief.
Steht sie noch in einer `.env` auf einem Server, **überschreibt sie den
Code-Default** und der Volltext bleibt kaputt. Beim Deployen also nachsehen.

Leer lassen ist unkritisch: dann greift der Code-Default, und der zeigt auf
denselben Server (zwei Stellen — `settings.mcp_server_url` und
`transport._DEFAULT_MCP_URL`; ein Test hält sie zusammen).

**Beim Wechsel auf einen anderen MCP-Server** die Werkzeugliste nicht abtippen,
sondern holen — sie steuert die Server-Zuordnung, und ein fehlender Name fällt
still auf die Default-URL zurück:

```bash
curl -s -X POST "$MCP_SERVER_URL" -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

Antwort ist SSE (`data: {…}`). Namen nach
`backend/seeds/05-knowledge/mcp-servers.yaml` übertragen und mit dem nächsten Image
ausliefern — der `migrate`-Dienst (`--werksabgleich`) hebt den Bereich, solange er im
Studio nicht angepasst wurde; sonst die Liste im Studio unter „Werkzeuge“ pflegen. Ein
voller `import-config` überschreibt seit Paket 12 jede redaktionelle Arbeit. Zwei Wächter in der Suite prüfen das
Ergebnis: die Registry muss `TOOL_DEFINITIONS` abdecken, und die beiden
Default-URLs müssen gleichziehen.

#### `MCP_AUTH_TOKEN` — Zugangsblock, optional (C2, 2026-08-10)

```
MCP_AUTH_TOKEN=wlo2.…
```

**Ein Geheimnis** — wie `STUDIO_API_KEY` behandeln: nur in die `.env` auf dem
Server, nie ins Repository, nie in ein Ticket. Der Wert steht als `SecretStr` in
den Einstellungen und taucht weder in Protokollen noch in Fehlermeldungen auf.

Den Block holt man **einmal** auf der `/auth`-Seite des MCP-Servers
(`https://wlo-mcp.87.106.195.152.nip.io/auth`) mit einem WLO-Konto; dort ist er
auch jederzeit widerrufbar. Wir bauen kein eigenes OAuth — die Anmeldung gehört
dem MCP-Server.

Zwei Betriebsarten, kein dritter Zustand:

| `MCP_AUTH_TOKEN` | Betriebsart | Wirkung |
|---|---|---|
| leer (Default) | `anonymous` | nur lesend. Der Server antwortet weiter mit `200` und der vollen Werkzeugliste |
| gesetzt | `service` | jeder Aufruf trägt `Authorization: Bearer …`. Lesend wirkt er immer; schreiben (kuratierende Werkzeuge) nur mit dem Studio-Schalter „Gastkonto darf schreiben" (System → Betrieb, Vorgabe aus) |

**Schreiben ohne persönliche Anmeldung ist seit Paket 7 aus** (P5-9, Nutzer-Entscheid
2026-10-09). In beiden Modi schreibt nur, wer mit dem eigenen WLO-Konto angemeldet ist
(Anmelde-Knopf im Widget). Der Schalter oben erlaubt dem Dienstkonto das Schreiben für
jede Person im Chat — eine bewusste Entscheidung, deshalb nur im Studio und nicht per
Umgebung.

Ein `401` kommt laut Server-Doku **nur bei einem vorgelegten, aber
unbrauchbaren** Block — anonym zu bleiben ist kein Fehler.

**Prüfen, ob der Block greift**, ohne ihn auszugeben:

```bash
curl -s -H "X-Studio-Key: $STUDIO_API_KEY" https://<PUBLIC_HOST>/api/health
```

(Seit Paket 17 nur mit Studio-Schlüssel.) Das Feld `mcp_auth` nennt `service` oder `anonymous`.

**Wenn der Bot nicht kuratiert**, obwohl ein Muster es vorsieht, steht der Grund
im Protokoll (INFO — ohne Anmeldung ist das der Normalfall). Die Zeile nennt das
Muster, die fehlenden Werkzeuge und beide Stellschrauben:

```
Muster M13 verlangt kuratierende Werkzeuge ['wlo_create_collection'], aber in diesem
Zug ist niemand persönlich angemeldet. Ohne Anmeldung schreibt der Bot nur mit dem
Block der Anlage (MCP_AUTH_TOKEN) und der Studio-Erlaubnis „Gastkonto darf
schreiben" — sie werden dem Modell nicht angeboten.
```

Im Chat selbst erscheint **keine** Adresse und kein Block: der Bot sagt offen, dass
Anlegen und Ändern eine Anmeldung brauchen, und bietet den Anmelde-Knopf an.

---

# Runbook

### Erstinstallation

Ein neuer Server folgt **[../INSTALL.md](../INSTALL.md)** — dort steht der Weg
vom leeren Debian bis zum laufenden Stack, samt Schema, Konfiguration und
Wissensbestand.

**Der `migrate`-Dienst füllt die Konfiguration selbst** (seit Paket 12:
`alembic upgrade head && boerdi import-config --werksabgleich`) — einmal vor den
Backends, nicht je Replika. Er legt an, was fehlt, hebt unberührte Bereiche auf
eine neue Werksfassung und lässt im Studio Angepasstes und Gelöschtes stehen. Den
vollen Import, der **jeden** Bereich überschreibt, gibt es nur ausdrücklich:

```bash
docker compose -f compose.prod.yml --env-file .env run --rm --no-deps \
  migrate boerdi import-config
```

Der Seed-Baum liegt **im Image** (`/app/seeds`, `CONFIG_SEED_DIR`), kommt also
aus demselben Commit wie der Code. Die Wörter hinter dem Dienstnamen ersetzen den
Befehl des `migrate`-Dienstes (sonst liefe wieder `alembic upgrade head`);
`--no-deps` startet die abhängigen Dienste nicht mit.

**Und der Wissensbestand dazu** (RAG, seit 2026-08-19). Ohne diesen Schritt
startet die Anlage mit leeren Wissensbereichen: das Studio zeigt sie mit
`0 Dokumente`, und der Chatbot antwortet aus Modellwissen statt aus euren
Dokumenten — eine Antwort, die gut aussieht und nichts belegt.

```bash
docker compose -f compose.prod.yml --env-file .env run --rm --no-deps \
  backend boerdi import-rag
```

**Am `backend`-Dienst, nicht am `migrate`** (live gemessen 2026-08-19): `migrate`
bekommt nur `DATABASE_URL`. Der Import bettet neu ein und braucht dafür die
LLM-Zugangsdaten, die allein das Backend gesetzt bekommt — sonst bricht er mit
`Missing credentials` ab. Die Schlüssel gehören auch nicht an `migrate`
nachgereicht: der Dienst führt Schema und Konfiguration aus, und ein Zugang, den
er nicht braucht, vergrößert nur die Angriffsfläche. `run --rm` startet dafür
einen eigenen Container neben den laufenden Replikas.

Ohne Argument gilt `/app/seeds/rag` (909 Abschnitte in 8 Bereichen). Der Lauf
**bettet neu ein** — die Vektoren reisen bewusst nicht mit, weil sich das
Einbettungsmodell ändern darf; rechnet mit wenigen Minuten und entsprechend
vielen Einbettungs-Aufrufen.

Der Aufruf ist **gefahrlos wiederholbar**: belegte Bereiche bleiben unberührt und
werden am Ende namentlich gemeldet. Soll wirklich der Werkszustand zurück, sagt
das `--force` ausdrücklich — es leert die betroffenen Bereiche vorher, also mit
Backup davor.

**Einen einzelnen Bereich auffrischen** — etwa wenn ein Image einen neuen Stand
mitbringt (Paket 16: `Plattformwissen` 2.0). Weil belegte Bereiche übersprungen
werden, behält eine bestehende Anlage sonst die alte Fassung. Die eine Datei allein
in ein Verzeichnis legen und nur sie einlesen:

```bash
docker compose -f compose.prod.yml --env-file .env run --rm --no-deps \
  backend sh -c 'mkdir -p /tmp/rag && cp /app/seeds/rag/Plattformwissen.jsonl /tmp/rag/ && boerdi import-rag --seed /tmp/rag --force'
``` `--sqlite <KOPIE der ALT-badboerdi.db>` bleibt als einmalige
Brücke aus dem Altsystem bestehen.

### Einbettungsmodell wechseln (etwa auf die AcademicCloud)

Die Wissensbasis liegt im Vektorraum von `text-embedding-3-small` (1536 Dimensionen). Ein anderes
Modell ist kein Schalter: Die Spalte hat eine feste Dimension, und Vektoren verschiedener Modelle
lassen sich nicht vergleichen. `boerdi rag-einbettung-wechseln` überführt **alle** Abschnitte — Seed
und Studio-Uploads — in den neuen Raum (Paket 11).

1. Sicherung ziehen (`pg-backup`, siehe „Restore“).
2. In der `.env` das Modell setzen. Über die AcademicCloud leitet das Backend Modelle, deren Name
   nicht mit `text-embedding-` beginnt, nur bei `LLM_PROVIDER=b-api-academiccloud` dorthin:
   ```
   LLM_EMBED_MODEL=<Modell>
   EMBED_DIM=<Dimension>   # nur, wenn das Modell nicht in llm_models._EMBED_MODEL_DIMS steht
   ```
3. Probe — misst die Dimension mit einem Aufruf und zählt, ändert nichts:
   ```bash
   docker compose -f compose.prod.yml --env-file .env run --rm --no-deps \
     backend boerdi rag-einbettung-wechseln --probe
   ```
   Bricht ab, wenn die gemessene Dimension nicht zu `EMBED_DIM` passt oder über 2000 liegt (Grenze
   des Suchindex).
4. Backend mit der neuen `.env` neu starten und **direkt danach** wechseln:
   ```bash
   docker compose -f compose.prod.yml --env-file .env up -d backend
   docker compose -f compose.prod.yml --env-file .env run --rm --no-deps \
     backend boerdi rag-einbettung-wechseln
   ```
   Bis der Lauf fertig ist, findet die Wissenssuche nur schon neu eingebettete Abschnitte (909
   Seed-Abschnitte: wenige Minuten). Bleiben Abschnitte ohne Vektor (Ausgabe und Rückgabewert 1),
   mit `--fortsetzen` erneut laufen lassen.

Zurück geht es genauso mit dem alten Modell. Am `backend`-Dienst, nicht am `migrate`: nur das Backend
hat die LLM-Zugangsdaten. Stand 2026-10-15 führt die AcademicCloud über die b-api **kein**
Einbettungsmodell. Für e5-Modelle setzt der Anbieter-Weg die Präfixe `query:`/`passage:` nicht —
vor einem Wechsel auf ein e5-Modell nachrüsten.

### Auf eine Route des b-api-Routers umstellen

Der Router der b-api bündelt Modelle unter einem Namen und weicht bei Ausfall aus
(`docs/architektur.md` §5.6). Reihenfolge — eine unbekannte Route antwortet sofort mit 400:

1. In der b-api die Route anlegen (global durch die Administration oder am Konto). Sie darf
   nur Modelle **einer** Familie bündeln: für die Vorgabe `gpt-6-luna` etwa
   `gpt-6-luna` (Priorität 0) und `gpt-5.6-luna` (Priorität 1). Beim Ändern „Cache dieser
   Route beim Speichern leeren“ einschalten.
2. In der `.env` `B_API_ROUTE=<Routenname>` setzen. `LLM_CHAT_MODEL` bleibt das Modell, dessen
   Parameter und Preis gelten — **nicht** der Routenname (der Start warnt bei Verwechslung).
3. `docker compose -f compose.prod.yml up -d backend`. Prüfen: Studio › Evaluation zeigt in
   den Messbedingungen `weg.route`; gebucht wird unter `LLM_CHAT_MODEL`.

Zurück: `B_API_ROUTE` leeren und das Backend neu starten.

### Woher der b-api-Schlüssel kommt (`B_API_KEY_MODE`)

| Wert | Verhalten | Wann |
|---|---|---|
| `auto` (Vorgabe, auch leer oder unbekannt) | `Authorization: Bearer …` vom b-api-Proxy, sonst `B_API_KEY` | gemischter Betrieb: hinter dem Proxy und direkt |
| `static` | immer `B_API_KEY`; der Kopf zählt nicht | wie vor Paket 17; schließt beliebige Schlüssel direkter Aufrufer aus |
| `forward` | jeder Zug braucht den durchgereichten Schlüssel, sonst **401** | Anlage nur hinter dem Proxy |

Gilt für Chat, Strom, Agent und Sprache; `/api/speech/status` ist eine Auskunft und bleibt
offen. Hintergrundläufe (Evaluation, Lasttest, RAG-Import, Vorwärmung) nehmen in jedem Modus
`B_API_KEY`. Züge der Anlage selbst sind auch unter `forward` frei: Studio-Proben (der
Studio-Proxy reicht `Authorization` nie durch) und Züge mit gültigem `X-Studio-Key` — so
schickt sie der Lasttest im Prozess und der Eval-Runner an die eigene Loopback-Adresse; an
eine fremde `EVAL_CHAT_URL` geht der Studio-Schlüssel nie, dort gilt deren Modus.

Grenzen: `forward` **verlangt** einen Schlüssel, es prüft ihn nicht — das tut die b-api
(ungültig → 401 dort). Nur `static` verhindert, dass direkte Aufrufer beliebige Schlüssel
vorlegen (jeder kostet einen eigenen HTTP-Client im LiteLLM-Zwischenspeicher). Wirkt nur mit
`LLM_PROVIDER=b-api-*` — sonst warnt der Start, ebenso bei einem unbekannten Wert (es gilt
dann `auto`).

### Deployen / aktualisieren

```bash
docker compose -f compose.prod.yml exec pg-backup \
  pg_dump -Fc -f /backup/vor-deploy-$(date +%Y%m%d-%H%M%S).dump   # 0. Sicherung
docker build -t boerdi-chat ..                                     # 1. Image
docker compose -f compose.prod.yml --env-file .env up -d migrate   # 2. Migration allein
docker compose -f compose.prod.yml --env-file .env up -d           # 3. Rest (NICHT rollierend)
```

Schritt 0, weil die Tagessicherung bis zu 24 h alt ist und „der sichere Weg ist
der Restore" (Rollback unten) sonst einen Tag kostet. Schritt 2 getrennt, weil
ein Migrationsfehler dann sichtbar ist, bevor Replikas neu starten. Schritt 3 ist
**kein** rollierendes Update: außerhalb von Swarm erzeugt `up -d` alle
`backend`-Replikas gleichzeitig neu — laufende Streams brechen ab, und bis die
neuen den HEALTHCHECK bestehen, hat traefik kein Ziel. Der `migrate`-Dienst ist ein Einmal-Lauf; die Backends
warten per `service_completed_successfully` auf ihn.

**Paket 17:** `migrate` hebt auf **0015** (0014: Herzschlag der Lasttest- und Eval-Läufe,
höchstens ein laufender Lasttest; 0015: geteilter Master-Skill-Stand). Während des Umstiegs
keinen Lasttest und keine Evaluation starten — alte Backends schreiben keinen Herzschlag.

**Hier KEIN `import-config`.** Ab dem ersten Import ist die Datenbank die
Wahrheit und das Studio der Weg, sie zu ändern; ein zweiter Import überschreibt
redaktionelle Arbeit mit dem Seed-Stand. Soll wirklich der ganze Baum neu
gesetzt werden, gehört ein Backup davor (siehe unten).

### Den mitgelieferten Konfigurationsstand übernehmen — im Studio

Seit 17.08.2026 braucht das keinen SSH-Zugang mehr: **Sicherung → „Werksfassung
aus dem Repository"** (bis Paket 12 „Auslieferungsstand aus dem Abbild“) liest denselben Baum (`/app/seeds`) aus dem laufenden Abbild,
zeigt vorher die Zählung (wie viele Bereiche fehlen, weichen ab, stehen nur in
der Datenbank) und bietet zwei Wege an:

| Knopf | Wirkung | Verlust |
|---|---|---|
| „Fehlende nachziehen" | schreibt nur Bereiche, die es in der Datenbank **nicht** gibt — im Studio gelöschte Werksbereiche nicht | keiner |
| „Alles auf die Werksfassung" | schreibt neue **und abweichende**, löscht Bereiche, die nur in der Datenbank stehen (außer solchen mit stillgelegter eigener Fassung) | ja — vorher legt das Backend selbst einen Schnappschuss „vor Werksfassung" an |

Je Bereich umschalten, vergleichen oder „Als geprüft markieren“ geht in der Karte
**„Werk und eigene Fassung“** darüber — meist der bessere Weg als einer der beiden
Knöpfe.

**Das Abbild bleibt die Quelle.** Der Knopf lädt nichts aus dem Repository nach;
er zeigt den Stand des Commits, aus dem *dieses* Abbild gebaut wurde. „Neueste
Konfiguration aktivieren" heisst also weiterhin: Abbild bauen, deployen, **dann**
im Studio drücken.

Ein Neustart ist danach nicht nötig — der DB-Trigger benachrichtigt jede Replika
(seit Migration `0003` auch beim Löschen).

Seit Paket 6 (2026-10-08) prüft „Alles auf die Werksfassung" den Seed vorher
wie ein Wiederherstellen (Modell, Schlüssel, Lotsen- und Policy-Regex): ein
ungültiger Baum wird mit 422 abgewiesen, ohne Schnappschuss und ohne dass etwas
geschrieben wird.

### Werkszustand per Kommandozeile

Derselbe Ablauf wie „Alles auf die Werksfassung", für den Fall, dass das Studio
nicht erreichbar ist oder ein Skript den Reset fährt:

```bash
# Erst ansehen, was sich ändern würde (schreibt nichts):
docker compose -f compose.prod.yml --env-file .env run --rm --no-deps \
  migrate boerdi import-config --exact --dry-run
# Dann herstellen: Schnappschuss, schreiben, löschen — eine Transaktion:
docker compose -f compose.prod.yml --env-file .env run --rm --no-deps \
  migrate boerdi import-config --exact
```

Der Rückweg ist der Schnappschuss „vor Werksfassung (Kommandozeile)" im
Studio unter Sicherung. Ist die Grenze von 50 Schnappschüssen erreicht, verweigert
der Lauf ohne Änderung. Der Import ohne Option überschreibt nur, löscht nichts und
sichert nicht — ein im Studio angelegtes Muster überlebt ihn; für einen echten
Werkszustand also `--exact`.

### Einen einzelnen Bereich aus dem Abbild nachziehen

Seit Paket 12 meist unnötig: `migrate` ruft `import-config --werksabgleich`, und ein
**unberührter** Bereich folgt der neuen Werksfassung beim Start von selbst. Ein im
Studio **angepasster** Bereich bleibt — das Studio zeigt ihn unter Sicherung →
„Werk und eigene Fassung“ als „neue Werksfassung verfügbar“, mit Unterschied und
Knopf „Werksfassung verwenden“ (die eigene Fassung wird stillgelegt, nicht gelöscht).
Der Weg über die Kommandozeile bleibt für Server ohne Studio-Zugang:

```bash
# 0. Rückweg: im Studio unter Sicherung einen Schnappschuss anlegen.
# 1. Was weicht ab? (schreibt nichts; der Bereich muss unter „abweichend“ stehen)
docker compose -f compose.prod.yml --env-file .env run --rm --no-deps \
  migrate boerdi import-config --exact --dry-run
# 2. Nur diesen einen Bereich aus /app/seeds schreiben:
docker compose -f compose.prod.yml --env-file .env run --rm --no-deps migrate \
  sh -c 'mkdir -p /tmp/nur/01-base \
    && cp /app/seeds/01-base/classify-overrides.yaml /tmp/nur/01-base/ \
    && boerdi import-config --from /tmp/nur'
# Erwartet: „imported 1 areas (1 yaml, 0 md)“
```

`--from` auf einen Teilbaum schreibt genau die Dateien darin; der Bereichsname
ergibt sich aus dem Pfad unterhalb von `--from`. Wirksam ohne Neustart (DB-Trigger).
Hat die Redaktion denselben Bereich im Studio geändert, überschreibt der Import
diese Änderungen — dann stattdessen im Studio unter „Alle Bereiche“ den Bereich
öffnen und die neuen Blöcke im Rohtext von Hand übernehmen.

### Werk und eigene Fassung beim Umzug

Sicherungen, Snapshots und `export-config` enthalten die **gelebte** Fassung je Bereich — eine im
Studio stillgelegte eigene Fassung (Sicherung → „Werk und eigene Fassung“) und die gemerkte
Werksbasis reisen nicht mit. Auf dem neuen Server gilt ein eingespielter Bereich deshalb als
angepasst, bis er der Werksfassung gleicht; wer eine stillgelegte Fassung behalten will, holt sie
vor dem Umzug zurück („Eigene Fassung verwenden“).

### Was der Werkszustand umfasst — und was nicht

| Umfasst (Seed-Baum, 60 Bereiche) | Bleibt unberührt |
|---|---|
| alle Muster (`03-patterns`), Personas (`04-personas`), Domänen-Regeln, Lotse und Lotsen-Regeln, Begrüßung, Anzeige-, Sicherheits- und Datenschutz-Einstellungen, Dimensionen, Wissens- und MCP-Registry, Preistafel, Gold-Flows, Maschine (`01-base/engine`) | Wissensbasis-Dokumente (`boerdi import-rag`), Master-Skill und Skills (kommen aus edu-sharing), Umgebungsvariablen, Sitzungen, Logs, Eval- und Lasttest-Läufe, Schnappschüsse |

**Achtung, Maschine:** Der Seed stellt `01-base/engine` auf `mode: agent`
(seit Paket 7). Ein Werkszustand stellt eine Anlage, die im Studio auf die
Muster-Maschine umgestellt ist, also auf den Agenten zurück. Danach unter
System → „Betrieb" wieder umstellen.

**Achtung, Wissensbereiche:** Der Werkszustand schreibt auch den Wissens-Katalog
(`05-knowledge/rag-config`) zurück. Ein Bereich, der erst nach der Auslieferung
im Studio angelegt wurde, verschwindet daraus — seine Dokumente bleiben in der
Wissensbasis, werden aber nicht mehr durchsucht, bis der Bereich wieder im
Katalog steht. Vorher unter „Wissen“ notieren oder danach aus dem Schnappschuss
„vor Werksfassung“ zurückholen.

**Image aus der Registry statt selbst gebaut.** `image.yml` veröffentlicht nach
bestandenem Smoke nach GHCR; dann entfällt Schritt 1 und `BOERDI_IMAGE` in der
`.env` zeigt auf die commit-genaue Marke. Das ist zugleich der Rollback-Schalter
— eine Zeile statt einer Suche.

**Abhängigkeit geändert (`pyproject.toml`/`uv.lock`)? Image neu bauen — sonst
Neustart-Schleife.** Beim Bauen von P10-2 real passiert: das Compose setzte
`RATE_LIMIT_STORAGE_URI=redis://…`, das Image stammte aber von vor `uv add
redis`. Ergebnis: `limits.errors.ConfigurationError: 'redis' prerequisite not
available` und drei Container in `Restarting (1)` statt `healthy`. `docker
compose ps` zeigt nur die Schleife, den Grund zeigt erst:

```bash
docker compose -f compose.prod.yml logs --tail 20 backend
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

```bash
docker compose -f compose.prod.yml --env-file .env up -d --remove-orphans
```

### Skalieren

```bash
docker compose -f compose.prod.yml --env-file .env up -d --scale backend=5
```

Oder dauerhaft `BACKEND_REPLICAS=5` in der `.env`. Zustandslos, deshalb keine
Sticky-Sessions nötig — Session und Config liegen in Postgres (V2/V6).

**Vorgabe ist 1.** Mehrere Replikas sind möglich: Züge derselben Sitzung sperrt
seit Paket 7 ein Eintrag in Postgres (`session_locks`, Migration 0008) über alle
Replikas hinweg (`docs/cluster-checkliste.md`). Auf einem 2-Kern-Server bringt es
nichts: drei Replikas teilen sich dieselben zwei Kerne und machen es langsamer,
nicht schneller. Die b-api zählt je Schlüssel, nicht je Replik — `LLM_MAX_CONCURRENCY`
dann teilen (`.env.example`).

### Vor einem CDN oder weiteren Proxy

`TRUST_FORWARDED_FOR: "true"` (in `compose.prod.yml`) nimmt für Rate-Limit, Login-Drossel
und Logs den **ersten** Eintrag von `X-Forwarded-For`. Das stimmt nur, solange traefik
direkt am Netz steht: von nicht vertrauten Quellen verwirft traefik fremde
`X-Forwarded-*`-Kopfzeilen und setzt die echte Adresse selbst (Audit 2026-10-10, L-5).

Steht ein CDN oder ein weiterer Proxy davor, der Einträge **anhängt**, ist der erste
Eintrag vom Client frei wählbar — Chat-Limit und Login-Drossel ließen sich dann mit
einer erfundenen Adresse je Anfrage umgehen. In dem Fall:

* in traefik `entryPoints.<name>.forwardedHeaders.trustedIPs` auf die Adressen des
  vorgeschalteten Proxys setzen (nicht `insecure: true`), und
* prüfen, welcher Eintrag dann die Adresse des Clients ist. Das Backend nimmt heute
  fest den ersten; „rechts minus vertraute Hops“ ist nicht eingebaut — bis dahin
  `TRUST_FORWARDED_FOR` nur einschalten, wenn der erste Eintrag verlässlich vom
  eigenen Proxy stammt.

### Welche Proxys Uvicorn glaubt (`FORWARDED_ALLOW_IPS`)

Zwei Stufen entscheiden über die Client-Adresse (Drosselung je IP, Logs) und das Schema
der Weiterleitungen:

1. **Uvicorn** liest `X-Forwarded-For`/`-Proto` nur von Absendern in `FORWARDED_ALLOW_IPS`
   (Adressen oder CIDR, kommagetrennt). Vorgabe `*` = jedem glauben — richtig für
   `compose.prod.yml`, weil dort kein App-Port veröffentlicht ist und nur traefik das
   Backend erreicht.
2. **`TRUST_FORWARDED_FOR=true`** lässt zusätzlich die App den ersten Eintrag des Kopfes
   lesen (siehe oben).

| Aufbau | `FORWARDED_ALLOW_IPS` | `TRUST_FORWARDED_FOR` |
|---|---|---|
| `compose.prod.yml` (traefik davor, kein App-Port veröffentlicht) | `*` (Vorgabe) | `true` (gesetzt) |
| Kubernetes mit Ingress | Pod-CIDR des Ingress-Controllers | `false` |
| **Testbetrieb ohne Proxy** (`docker run -p …` oder Compose mit `ports:`) | `127.0.0.1` | `false` (Vorgabe) |

Ohne Proxy davor erreicht jeder den Port direkt; mit `*` könnte er sich per
`X-Forwarded-For` eine beliebige Adresse geben und die Drosselung umgehen. Ein leerer Wert
gilt als „nicht gesetzt“ (also `*`) — deshalb ausdrücklich `127.0.0.1`.

**Testbetrieb mit `docker run`** (eigenes Image, Datenbank im Dev-Compose-Netz). Die
Env-Datei (`deploy/.env.test`, nicht im Repo) trägt mindestens `DATABASE_URL` auf eine
eigene Test-Datenbank, `LLM_PROVIDER`/`LLM_EMBED_MODEL` bzw. `EMBED_DIM` (die erste Migration
legt damit die Vektor-Spalte an, siehe oben) und `STUDIO_API_KEY`/`STUDIO_PASSWORD`:

```bash
docker build -t boerdi-chat:test .
docker run --rm --network boerdi-chat-dev_default --env-file deploy/.env.test \
  boerdi-chat:test sh -c "alembic upgrade head && boerdi import-config --werksabgleich"
docker run -d --name boerdi-chat-test --network boerdi-chat-dev_default \
  -p 127.0.0.1:8180:8100 -p 127.0.0.1:8181:8101 \
  --env-file deploy/.env.test -e FORWARDED_ALLOW_IPS=127.0.0.1 boerdi-chat:test
curl -s http://127.0.0.1:8181/ready     # {"status":"ready",…} — dann ist 8180 bereit
```

**Mit Compose** dasselbe als Dienst:

```yaml
  backend:
    image: boerdi-chat:test
    ports: ["127.0.0.1:8180:8100", "127.0.0.1:8181:8101"]
    environment:
      FORWARDED_ALLOW_IPS: "127.0.0.1"
```

Migrationen laufen nie im Web-Prozess: nach jedem neuen Image erst den Migrationsschritt
(erster `docker run` oben bzw. der `migrate`-Dienst), dann das Backend.

### Backup

Läuft von selbst (`pg-backup`, täglich, Aufbewahrung `BACKUP_KEEP_DAYS`, Default
14). Es ist eine `sleep 86400`-Schleife und kein cron: das offizielle
Postgres-Image bringt keinen Cron-Daemon mit, und ein zweites Image dafür wäre
mehr Lieferkette als Nutzen. Preis: der Takt verschiebt sich bei jedem Neustart
des Containers.

```bash
docker compose -f compose.prod.yml exec pg-backup ls -lh /backup   # Dumps ansehen
docker compose -f compose.prod.yml exec pg-backup pg_dump -Fc -f /backup/vor-deploy.dump
```

Ein **fehlgeschlagener** Dump wird gelöscht statt halb liegen gelassen und
protokolliert `BACKUP FEHLGESCHLAGEN` — eine 0-Byte-Datei im Backup-Verzeichnis
wäre schlimmer als keine, weil sie wie ein Backup aussieht.

### Was der Server von selbst löscht

Ein Lauf im Backend (alle 6 Stunden, der erste 5 Minuten nach dem Start, über alle
Kopien nur einer zugleich) löscht, was älter ist als seine Frist — **unwiderruflich**:

| Was | Frist (Vorgabe) | Gepflegt in |
|---|---|---|
| Chatnachrichten und Sitzungsgedächtnis | 30 Tage | Studio → Datenschutz (`01-base/privacy-config`) |
| Gesprächsstand ruhender Sitzungen (Thema, Seitentitel, Suchbegriffe, Signale, Tour) | dieselbe, ab der letzten Aktivität | wie oben |
| Sicherheitsprotokoll | 90 Tage | Studio → Agent „Rolle & Schutz“ bzw. Muster „Identität & Schutz“ (`01-base/safety-config`) |
| Qualitätsprotokoll | 180 Tage | Studio → Gemeinsam → Datenschutz (`01-base/quality-log-config`) |
| Text im Qualitätsprotokoll (Nachricht, erkannte Begriffe, Begründungen, Fehlertexte) | wie die Chatnachrichten (30 Tage) — die Zeile mit ihren Kennzahlen bleibt bis zur Protokollfrist | wie die Chatnachrichten |

Das Sicherheitsprotokoll hält die ersten 500 Zeichen der Nachricht und die IP
(riskante und gedrosselte Züge, mit `log_all_turns` alle) — also länger als die
Nachrichten selbst; bei Bedarf die Fristen angleichen. Im Qualitätsprotokoll leert
der Lauf den Text nach der Gesprächsfrist (seit Paket 16, Marke `text_geleert`;
Teilindex aus Migration 0013).

`0` heißt unbegrenzt. Die Sitzungen selbst und ihre Verbrauchszahlen bleiben (sonst
ginge die Kostenübersicht mit); löschen lassen sie sich einzeln in der Studio-Ansicht
„Sessions“ oder über „Gespräche löschen“. Das Studio zeigt unter Datenschutz →
Aufbewahrung je Bereich, was fällig ist, und löst den Lauf auf Wunsch sofort aus.
**Die Sicherungen** (`pg-backup`) enthalten gelöschte Daten noch bis zu
`BACKUP_KEEP_DAYS` Tage — eine Auskunft oder Löschung auf Anfrage muss sie mitdenken.

**Auf `b-api-academiccloud`** gibt es keine Moderation (die Nachrichten bleiben dort),
aber die Einbettungen für die Wissenssuche gehen über den OpenAI-Pfad der b-api an
OpenAI — die Wissensbasis liegt in deren Vektorraum, und die AcademicCloud führt kein
Einbettungsmodell. Das betrifft jede Muster-Nachricht, für die die Wissenssuche
vorab eingebettet wird. So entschieden (2026-10-15); ein Wechsel auf ein Einbettungsmodell der
AcademicCloud: Abschnitt „Einbettungsmodell wechseln“.

### Restore

```bash
docker compose -f compose.prod.yml --env-file .env stop backend
docker compose -f compose.prod.yml exec pg-backup \
  sh -c 'pg_restore --clean --if-exists -d "$PGDATABASE" /backup/<datei>.dump'
docker compose -f compose.prod.yml --env-file .env start backend
```

Backends **vorher** stoppen: `--clean` wirft Tabellen weg, an denen sonst noch
laufende Turns hängen. Danach eine Config-Änderung im Studio speichern und
prüfen, dass sie ankommt (der NOTIFY-Kanal überlebt den Restore, die
Prozess-Caches werden erst durch das nächste NOTIFY frisch).

### Rollback

```bash
docker tag boerdi-chat boerdi-chat:vorher        # VOR dem Build, sonst ist er weg
docker compose -f compose.prod.yml --env-file .env up -d
# zurück:
BOERDI_IMAGE=boerdi-chat:vorher docker compose -f compose.prod.yml --env-file .env up -d
```

Dauerhaft wird der Rollback erst mit `BOERDI_IMAGE=boerdi-chat:vorher` in der
`.env` — die Zeile oben gilt nur für diesen einen Aufruf.

**Migrationen rollen nicht mit zurück.** Es gibt dreizehn (0001–0013, unter
`backend/alembic/versions/`). Brachte der neue Stand eine Migration mit, scheitert
der `migrate`-Dienst des alten Images (`Can't locate revision`), und die Backends
werden nicht ersetzt. Dann ZUERST mit dem NEUEN Image zurückmigrieren (`run --rm
--no-deps migrate alembic downgrade <revision>`), danach das Image wechseln — oder
den Restore oben nehmen (Sicherung aus Schritt 0 beim Deploy). Beim Zurückmigrieren
beachten: `0007` hat kein wirksames `downgrade()` (die entfernten Auslöser kommen
nicht zurück), `0009` löscht Verbrauchszeilen ohne Sitzung (etwa Eval-Kosten), `0013`
entfernt seinen Index `CONCURRENTLY`.

### Logs & Traces

```bash
docker compose -f compose.prod.yml logs -f backend      # alle Replikas gemischt
ssh -L 16686:127.0.0.1:16686 <server>                   # dann http://localhost:16686
```

Die Jaeger-UI ist absichtlich nur host-lokal gebunden: Traces enthalten
Prompt-Metadaten und gehören nicht ins Internet.

`LOG_FORMAT=json` schreibt eine JSON-Zeile je Eintrag (Vorgabe `text`); jede Zeile trägt die
Trace-ID der Anfrage (`x-client-trace-id` bzw. B3, sonst neu vergeben). Metriken im
Prometheus-Format liefert der interne Port:

```bash
docker compose -f compose.prod.yml exec backend python -c \
  "import urllib.request as u; print(u.urlopen('http://127.0.0.1:8101/metrics').read().decode()[:2000])"
```

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
| — | Agenten-Endpunkt | ⚠️ `AGENT_OPEN` **nicht** setzen — es öffnet `/api/agent` ohne jede Anmeldung und ist für Testläufe gedacht. Der normale Weg herein ist die Anmeldung der Person (`WLO-Access-Block`), Server-zu-Server der `STUDIO_API_KEY`. Die Drosselung greift in allen drei Fällen. |
| — | Master-Skill | Aus, solange `MASTER_SKILL_ENABLED` nicht `true` ist. Angeschaltet laedt der Agent-Modus die Anleitung aus `MASTER_SKILL_NODE_ID` als Prompt-Kopf (Abnahme: eine Zeile `Master-Skill ... geladen` im Log des ersten Zuges). Scheitert der Abruf, antwortet der Chat ohne sie und warnt - kein Ausfall. |
| — | CORS | ⚠️ **Die Vorgabe ist OFFEN.** Zum Schließen `CORS_ALLOW_ALL=false` **und** `CORS_ORIGINS` mit den einbettenden Domänen setzen — die Liste allein bleibt sonst wirkungslos. Der Start warnt, wenn eine gesetzte Liste übersteuert wird; diese Zeile ist die Abnahme. Browser-Erweiterungen (`safari-web-extension://`, `chrome-extension://`) dürfen auch bei enger Liste — `CORS_ALLOW_EXTENSIONS=false` nimmt ihnen das. Geschlossen bietet das Widget die WLO-Anmeldung (Knopf, Ticket-Tausch) nur den gelisteten Seiten an (`/api/config/guide-mode` liefert sonst kein `mcp_auth_base`); Abnahme: von einer nicht gelisteten Seite ist kein Anmeldeknopf zu sehen. |
| — | Reranker | Vorgabe **aus** (`off` in `/api/health`). Eingeschaltet (`RAG_RERANKER_ENABLED=true`) bezieht das Backend das Modell beim Start selbst ins Volume `reranker_models` — Status `downloading`, dann `ready`; `download-failed` heißt Netz/Prüfwert, Protokoll lesen. Auf 2 Kernen `RERANK_INTRA_OP_THREADS=2`, `RERANK_MAX_CONCURRENCY=1`. Ablauf: `INSTALL.md` §8. |
| — | Lasttest | ✅ `BOERDI_ALLOW_LOADTEST` ohne Eintrag = `false` (compose.prod) = auf Prod abgelehnt; er teilt sonst den LLM-Pool mit Live-Nutzern. Bis 2026-09-29 lieferte das leere `${…:-}` den Code-Default `true`. |
| — | TLS | ⚠️ Nach dem ersten Start prüfen, dass ACME wirklich ein Zertifikat gezogen hat (`docker compose logs traefik`), sonst hängt die Seite an der Selbstsignatur. |
| — | HSTS | ✅ Jede Antwort trägt `Strict-Transport-Security: max-age=86400` (Paket 8). Läuft HTTPS stabil, `HSTS_MAX_AGE=31536000` setzen; `0` schaltet ab. Abnahme: `curl -sI https://<host>/health` zeigt die Zeile. |
| — | Studio-CSP | ✅ Die Studio-Seite trägt eine `Content-Security-Policy`: Skripte nur vom eigenen Ursprung (Paket 8, Audit 2026-09-29 A-M6/F-M5). Steht das Studio leer oder ohne Stil da, nennt die Browser-Konsole den Verstoß; `STUDIO_CSP=report` lässt die Seite laufen und meldet nur. Abnahme: `curl -sI https://<host>/studio/` zeigt `content-security-policy`. |

Die §8-Cluster-Abnahme (Advisory-Lock, NOTIFY-Schranke, Rate-Limit, SSE über
LB, Graceful Shutdown) steht getrennt in
[../docs/cluster-checkliste.md](../docs/cluster-checkliste.md) — mit der klaren
Trennung, welche Punkte automatisiert sind und welche einen laufenden Cluster
brauchen.
