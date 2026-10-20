# Installation auf Debian 13 (Trixie)

Von einem frischen Server bis zum laufenden Chatbot **mit den Seed-Daten**.
Betrieb danach (Skalieren, Backup, Restore, Rollback, Sicherheits-Checkliste)
steht in [deploy/README.md](deploy/README.md); diese Datei ist der Weg dorthin.

**Der Schritt, den man übersieht:** Schritt 7. Der Dienst `migrate` legt die
Tabellen an und füllt dabei fehlende Bereiche aus dem Seed im Image
(`import-config --werksabgleich`) — einmal, vor den Backends, nicht je Replika.
Ohne diesen Lauf läuft ein Chatbot ohne Muster, ohne Begrüssung und ohne
Vokabulare — technisch gesund, inhaltlich leer.

## Was der Server braucht

| | Minimum | Ihr Server |
|---|---|---|
| Kerne | 2 | 6 |
| RAM | 4 GB | 8 GB |
| Platte | 20 GB | 200 GB |

Dazu ein **DNS-A-Record**, der auf die Server-IP zeigt — traefik holt das
Zertifikat über TLS-ALPN-01 auf Port 443 (`tlschallenge` in `compose.prod.yml`),
das geht erst, wenn der Name auflöst.

Das Image wird **nicht** auf dem Server gebaut (siehe Schritt 5); Node und der
Quellbaum werden dort also nie gebraucht.

---

## 1. Grundsystem

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y ca-certificates curl git ufw
```

## 2. Firewall

**Vor** Docker einrichten, und in dem Wissen, dass Docker sie umgehen kann:
veröffentlichte Container-Ports schreiben eigene iptables-Regeln und laufen an
ufw vorbei (Audit-Erbe T-2). In diesem Stack veröffentlicht nur traefik — die
Firewall ist die zweite Linie, nicht die einzige.

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
```

Nach dem ersten Start gegenprüfen — hier darf **nur** traefik stehen:

```bash
docker ps --format "{{.Names}}\t{{.Ports}}" | grep 0.0.0.0
```

## 3. Docker

Aus Dockers eigenem Repository, nicht aus Debian: `docker.io` in den
Debian-Quellen hinkt hinterher und bringt kein `docker compose` v2.

```bash
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

`$VERSION_CODENAME` ist auf Debian 13 `trixie`. Sollte Docker für Trixie noch
keine Pakete führen, meldet `apt update` das als 404 — dann `trixie` in der
Zeile oben durch `bookworm` ersetzen (die Pakete laufen auf Trixie).

```bash
docker --version && docker compose version
```

Optional, damit `sudo` beim Betrieb entfällt (neu anmelden danach):

```bash
sudo usermod -aG docker "$USER"
```

> **Wissen, was das heisst:** die Docker-Gruppe ist root-äquivalent. Auf einem
> Server mit mehreren Konten lieber bei `sudo docker` bleiben.

## 4. Dateien holen

Auf den Server gehören nur `deploy/` und die `.env` — der Quellbaum wird nicht
gebraucht, weil das Image fertig aus der Registry kommt.

```bash
sudo mkdir -p /opt/boerdi && sudo chown "$USER" /opt/boerdi
cd /opt/boerdi
git clone --depth 1 https://github.com/<konto>/<repo>.git .
cd deploy
```

## 5. Image aus der Registry

Die GitHub-Action `image.yml` baut das Image bei jedem Push auf `main`, fährt
die Smokes dagegen und veröffentlicht **nur bei Erfolg** nach GHCR. Der Server
zieht also ein geprüftes Artefakt statt selbst zu bauen.

```bash
# Bei einem privaten Repository einmalig anmelden (Token mit `read:packages`):
echo "<token>" | docker login ghcr.io -u "<konto>" --password-stdin

docker pull ghcr.io/<konto>/<repo>:sha-1234567
```

Die **commit-genaue** Marke nehmen, nicht `:latest` — dann ist ein Rollback
eine Zeile in der `.env` statt einer Suche.

<details>
<summary>Falls doch auf dem Server gebaut werden soll</summary>

Geht mit 8 GB RAM, dauert aber Minuten (zwei Angular-Builds im Image) und
verlangt den vollständigen Quellbaum:

```bash
cd /opt/boerdi && docker build -t boerdi-chat .
```

Dann `BOERDI_IMAGE` in der `.env` weglassen — der Compose-Default ist
`boerdi-chat`.
</details>

## 6. Konfiguration

```bash
cp .env.example .env
chmod 600 .env
nano .env
```

Sechs Werte sind Pflicht, sonst startet nichts: `POSTGRES_PASSWORD`,
`STUDIO_API_KEY`, `STUDIO_PASSWORD`, `CORS_ORIGINS`, `PUBLIC_HOST`,
`ACME_EMAIL`. `CORS_ORIGINS` wirkt erst, wenn `CORS_ALLOW_ALL=false`
gesetzt ist — die Vorgabe lässt jede Domäne einbetten und dort anmelden. Mit `false`
läuft das Widget nur noch auf den gelisteten Seiten (und in Browser-Erweiterungen,
solange `CORS_ALLOW_EXTENSIONS=true`), und nur dort bietet es die WLO-Anmeldung an —
der Zugangsblock liegt im Speicher der einbettenden Seite (`docs/mcp-und-anmeldung.md`).
Geheimnisse erzeugen:

```bash
openssl rand -base64 32
```

Optional, aber oft gefragt: `MASTER_SKILL_ENABLED=true` schaltet die
redaktionelle Gesamtanleitung als Prompt-Kopf ein (Agent-Modus,
Knoten in `MASTER_SKILL_NODE_ID`). Vorgabe ist aus - Begruendung und
Wirkung in `docs/agent-modus.md`.

Zusätzlich eintragen:

```
BOERDI_IMAGE=ghcr.io/<konto>/<repo>:sha-1234567
```

`BACKEND_REPLICAS` bleibt bei der Vorgabe 1. Mehrere Replikas sind möglich: Züge
derselben Sitzung sperrt seit Paket 7 ein Eintrag in Postgres (`session_locks`,
Migration 0008) über alle Replikas hinweg. Drei Replikas auf sechs Kernen lassen
jedem zwei; auf einem 2-Kern-Server bleibt es bei 1. Die b-api zählt je Schlüssel,
nicht je Replik — `LLM_MAX_CONCURRENCY` dann teilen (`.env.example`).

Vollständigkeit prüfen, ohne zu starten:

```bash
docker compose -f compose.prod.yml --env-file .env config >/dev/null && echo "vollständig"
```

## 7. Datenbank und Seed-Daten

**Der Schritt, ohne den der Bot leer bleibt.** Drei Teile, in dieser Reihenfolge:

```bash
# 7a — Postgres allein hochfahren, damit die Migration ein Ziel hat
docker compose -f compose.prod.yml --env-file .env up -d postgres

# 7b — Schema anlegen und fehlende Seed-Bereiche füllen (ein Lauf, idempotent)
docker compose -f compose.prod.yml --env-file .env up migrate

# 7c — Wissensbestand einlesen (RAG): am backend-Dienst, er braucht die LLM-Zugangsdaten
docker compose -f compose.prod.yml --env-file .env run --rm --no-deps backend boerdi import-rag
```

7c bettet die mitgelieferten Abschnitte (`/app/seeds/rag`, 909 in 8 Bereichen) neu ein —
wenige Minuten. Ohne diesen Schritt bleiben die Wissensbereiche leer, und der Bot
antwortet aus Modellwissen statt aus den Dokumenten. Wiederholbar: belegte Bereiche
bleiben unberührt (Einzelheiten: `deploy/README.md`, „Und der Wissensbestand dazu“).

Der `migrate`-Dienst führt beides aus: `alembic upgrade head`, dann
`boerdi import-config --werksabgleich`. Der Seed-Baum liegt **im Image** unter
`/app/seeds` (`CONFIG_SEED_DIR`, Default `seeds`) — kein Bind-Mount, kein
Kopieren, der Stand kommt aus demselben Commit wie der Code.

`--werksabgleich` (Paket 12) ist der Grund, warum das automatisch laufen darf: er
legt an, was fehlt, hebt unberührte Bereiche auf die neue Werksfassung und fasst
im Studio Angepasstes oder Gelöschtes nicht an. Ohne Option schreibt der Import
**jeden** Bereich und würde bei jedem Neustart die redaktionelle Arbeit auf die
Werksfassung zurückdrehen.

**Ab jetzt ist die Datenbank die Wahrheit**, nicht mehr der Seed. Änderungen
macht die Redaktion im Studio. Der Seed ist der Startpunkt, keine
Laufzeit-Abhängigkeit.

Einen **vollständigen** Import (überschreibt alles) gibt es weiterhin, aber nur
ausdrücklich und mit Backup davor:

```bash
docker compose -f compose.prod.yml --env-file .env run --rm --no-deps \
  migrate boerdi import-config
```

Er löscht aber nichts: was nur in der Datenbank steht (etwa ein im Studio
angelegtes Muster), bleibt. Den echten **Werkszustand** stellt `--exact` her —
derselbe Ablauf wie „Alles auf die Werksfassung" im Studio: Seed prüfen,
Schnappschuss anlegen, schreiben und löschen in einer Transaktion. Mit
`--dry-run` zeigt er vorher nur die Liste (Einzelheiten: `deploy/README.md`,
„Werkszustand per Kommandozeile"):

```bash
docker compose -f compose.prod.yml --env-file .env run --rm --no-deps \
  migrate boerdi import-config --exact --dry-run
```

## 8. Reranker (optional, Vorgabe aus)

Der Reranker sortiert Abschnitte der Wissensbasis nach inhaltlicher Passung und verwirft thematisch
verfehlte WLO-Karten. Er läuft **im Prozess** (ONNX, kein Netzdienst), braucht ein Modell von
~135 MB und kostet CPU. Ohne ihn antwortet der Chat genauso, nur schwächer sortiert.

**Einschalten — kein weiterer Handgriff:**

```bash
cd /opt/boerdi/deploy
echo "RAG_RERANKER_ENABLED=true" >> .env
# auf 2 Kernen zusätzlich:
echo "RERANK_INTRA_OP_THREADS=2" >> .env && echo "RERANK_MAX_CONCURRENCY=1" >> .env
docker compose -f compose.prod.yml --env-file .env up -d backend
```

Beim Start bezieht das Backend das Modell selbst: die offizielle int8-ONNX-Datei des Herausgebers
(`cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`, Apache-2.0) von Hugging Face, an einer festen
Version, mit Größen- und SHA-256-Prüfung, atomar in das Volume `reranker_models`. Mehrere Kopien
teilen das Volume, eine lädt. Bis das Modell da ist, rechnet nichts damit; danach greift es ohne
Neustart.

**Server ohne Internet:** `RERANK_AUTO_DOWNLOAD=false` und das Modell von Hand in einen Ordner
legen, den `RERANK_MODEL_HOST_DIR` statt des Volumes einhängt. Erwartet wird darunter
`cross-encoder__mmarco-mMiniLMv2-L12-H384-v1__quint8-avx2/` mit `model_quint8_avx2.onnx` und
`tokenizer.json` (Quelle und Prüfwerte: `backend/src/boerdi/services/rag/reranker_bezug.py`). Ein
älterer Export unter `cross-encoder__mmarco-mMiniLMv2-L12-H384-v1-int8/` wird weiter erkannt.

**Ob er wirklich greift**, sagt der Gesundheits-Endpunkt — sofort, ohne auf den
ersten Chat zu warten:

```bash
curl -s -H "X-Studio-Key: $STUDIO_API_KEY" https://<PUBLIC_HOST>/api/health | grep -o '"reranker":"[a-z-]*"'
```

| Wert | Bedeutung |
|---|---|
| `off` | Vorgabe — `RAG_RERANKER_ENABLED` nicht gesetzt oder `false` |
| `downloading` | eingeschaltet, das Modell wird gerade bezogen |
| `ready` | eingeschaltet, Modell auffindbar — so soll es sein |
| `download-failed` | Bezug gescheitert (Netz, Prüfwert, Platte) — Protokoll lesen; der nächste Start versucht es neu |
| `model-missing` | eingeschaltet, Selbstbezug aus (`RERANK_AUTO_DOWNLOAD=false`) und kein Modell im eingehängten Ordner |

Dass das Modell auch in den Speicher geladen wurde, steht beim ERSTEN Zug im
Protokoll (`ready` sagt nur „auffindbar", nicht „geladen"):

```bash
docker compose -f compose.prod.yml logs backend | grep -i rerank
```

`Reranker geladen: cross-encoder__mmarco-…__quint8-avx2 · N Worker × M Thread(e)`
heisst ja.

**Schwellen der Karten-Auswahl:** Sie wurden mit dem früheren Export gemessen, nicht mit der
Hugging-Face-Datei (andere Quantisierung). Ein Stichprobenvergleich (20 Paare, 2026-10-15) ergab an
den wirksamen Schwellen dieselben Entscheidungen (Sammlungen −1,0, Einzelinhalte −1,5; knappster Fall
0,12 von der Schwelle). Vor dem Einschalten im Wirkbetrieb mit Golden-Läufen nachmessen;
überschreibbar per `CARD_CE_GATE_COLLECTION` / `CARD_CE_GATE_CONTENT`. Beide reicht
`compose.prod.yml` nicht durch — wer sie braucht, ergänzt sie dort unter
`backend: environment:`.

<details>
<summary>Herkunft und Prüfwerte (Nachvollziehbarkeit)</summary>

Hugging Face `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` (Apache-2.0), Commit
`1427fd652930e4ba29e8149678df786c240d8825`:

| Datei | Größe | SHA-256 |
|---|---|---|
| `onnx/model_quint8_avx2.onnx` | 118 620 016 | `6c2513767fb63d008a4377bef7a7a3555433d9436342bb53e35a3a72ffc52d4b` |
| `tokenizer.json` | 17 082 660 | `62c24cdc13d4c9952d63718d6c9fa4c287974249e16b7ade6d5a85e7bbb75626` |

Ein älterer Export (`…-int8`, `model_quantized.onnx`, SHA-256 `084ef9bf…`, erzeugt mit `optimum`)
wird weiter erkannt, wenn er schon daliegt.
</details>

## 9. Starten

```bash
docker compose -f compose.prod.yml --env-file .env up -d
docker compose -f compose.prod.yml ps
```

Alle Dienste sollen `healthy` oder `running` zeigen. Steht etwas in
`Restarting (1)`, zeigt `ps` nur die Schleife — der Grund steht im Log:

```bash
docker compose -f compose.prod.yml logs backend | tail -40
```

## 10. Abnahme

```bash
curl -s -H "X-Studio-Key: $STUDIO_API_KEY" https://<PUBLIC_HOST>/api/health
```

Drei Dinge in der Antwort ansehen:

| Feld | erwartet |
|---|---|
| `status` | `ok` |
| `mcp_auth` | `service`, wenn ein `MCP_AUTH_TOKEN` gesetzt ist — sonst `anonymous` |
| Modell-Felder | die aus der `.env`, nicht die Code-Defaults |

`docker compose -f compose.prod.yml ps` zeigt das Backend erst als `healthy`, wenn es
Anfragen annimmt: der HEALTHCHECK fragt `/ready` am internen Port 8101 (Start fertig,
Postgres antwortet). Den internen Port veröffentlicht dieses Compose nicht; von innen:

```bash
docker compose -f compose.prod.yml exec backend python -c \
  "import urllib.request as u; print(u.urlopen('http://127.0.0.1:8101/ready').read())"
```

Dann im Browser:

* `https://<PUBLIC_HOST>/studio/` — Anmeldung mit `STUDIO_PASSWORD`
* `https://<PUBLIC_HOST>/widget/` — die Demo-Seite mit dem eingebetteten Widget

**Zertifikat wirklich geholt?** Ohne diese Prüfung hängt die Seite an der
Selbstsignatur, und der Fehler sieht aus wie ein DNS-Problem:

```bash
docker compose -f compose.prod.yml logs traefik | grep -i -E "certificate|acme"
```

**Kam der Seed an?** Im Studio unter Muster → „Patterns" müssen die M-Nummern
stehen; leere Listen heissen: Schritt 7b fehlt. Unter Gemeinsam → „Wissen" tragen
die Bereiche Dokumente; `0 Dokumente` heisst: Schritt 7c fehlt.

## 11. Aktualisieren

```bash
docker pull ghcr.io/<konto>/<repo>:sha-<neu>
sed -i 's|^BOERDI_IMAGE=.*|BOERDI_IMAGE=ghcr.io/<konto>/<repo>:sha-<neu>|' .env
docker compose -f compose.prod.yml --env-file .env up -d migrate   # erst die Migration
docker compose -f compose.prod.yml --env-file .env up -d           # dann rollierend
```

Die Migration getrennt, damit ein Fehler dort sichtbar wird, **bevor** Replikas
neu starten.

**Der Seed läuft beim Aktualisieren mit — und das ist ungefährlich.** Der
`migrate`-Dienst ruft `import-config --werksabgleich`: neue Bereiche kommen dazu,
**unberührte Bereiche folgen der neuen Werksfassung**, alles im Studio Angepasste
bleibt. Was angepasst ist und eine neue Werksfassung hat, zeigt das Studio unter
Sicherung → „Werk und eigene Fassung“; dort lässt sich je Bereich zwischen Werk
und eigener Fassung wechseln, ohne dass eine verloren geht.

Sicherungen und Snapshots enthalten die gelebte Fassung, nicht die stillgelegte eigene — beim
Umzug auf einen anderen Server vorher zurückholen (`deploy/README.md`, „Werk und eigene Fassung
beim Umzug“).

**Kein `import-config` ohne Option beim Aktualisieren.** Der volle
Import überschreibt die redaktionelle Arbeit mit dem Seed-Stand. Wenn es
wirklich der ganze Baum sein soll: Backup davor.

---

Alles Weitere — Skalieren, Backup, Restore, Rollback, Logs, Traces und die
Sicherheits-Checkliste vor dem Livegang — steht in
[deploy/README.md](deploy/README.md).
