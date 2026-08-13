# Installation auf Debian 13 (Trixie)

Von einem frischen Server bis zum laufenden Chatbot **mit den Seed-Daten**.
Betrieb danach (Skalieren, Backup, Restore, Rollback, Sicherheits-Checkliste)
steht in [deploy/README.md](deploy/README.md); diese Datei ist der Weg dorthin.

**Der Schritt, den man übersieht:** die Migration legt die Tabellen an, füllt
aber **nichts**. Ohne Schritt 7 läuft ein Chatbot ohne Muster, ohne Begrüssung
und ohne Vokabulare — technisch gesund, inhaltlich leer. Es gibt bewusst keinen
Auto-Import beim Start: bei N Replikas würden alle gleichzeitig schreiben.

## Was der Server braucht

| | Minimum | Ihr Server |
|---|---|---|
| Kerne | 2 | 6 |
| RAM | 4 GB | 8 GB |
| Platte | 20 GB | 200 GB |

Dazu ein **DNS-A-Record**, der auf die Server-IP zeigt — traefik holt das
Zertifikat über HTTP-01, das geht erst, wenn der Name auflöst.

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
`ACME_EMAIL`. Geheimnisse erzeugen:

```bash
openssl rand -base64 32
```

**Für Ihre 6 Kerne** zusätzlich eintragen:

```
BACKEND_REPLICAS=3
BOERDI_IMAGE=ghcr.io/<konto>/<repo>:sha-1234567
```

Drei Replikas auf sechs Kernen lassen jedem zwei. (Die Empfehlung „1" im
Runbook gilt für einen 2-Kern-Server — dort machen drei Replikas es langsamer,
nicht schneller.)

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
```

Der `migrate`-Dienst führt beides aus: `alembic upgrade head`, dann
`boerdi import-config --only-missing`. Der Seed-Baum liegt **im Image** unter
`/app/seeds` (`CONFIG_SEED_DIR`, Default `seeds`) — kein Bind-Mount, kein
Kopieren, der Stand kommt aus demselben Commit wie der Code.

`--only-missing` ist der Grund, warum das automatisch laufen darf: der Import
legt nur an, was noch nicht in der Datenbank steht. Ohne die Option schreibt er
**jeden** Bereich und würde bei jedem Neustart die redaktionelle Arbeit auf den
Auslieferungsstand zurückdrehen.

**Ab jetzt ist die Datenbank die Wahrheit**, nicht mehr der Seed. Änderungen
macht die Redaktion im Studio. Der Seed ist der Startpunkt, keine
Laufzeit-Abhängigkeit.

Einen **vollständigen** Import (überschreibt alles) gibt es weiterhin, aber nur
ausdrücklich und mit Backup davor:

```bash
docker compose -f compose.prod.yml --env-file .env run --rm --no-deps \
  migrate boerdi import-config
```

## 8. Reranker-Modell (optional, aber empfohlen)

Der Reranker sortiert die Suchtreffer nach inhaltlicher Passung nach, bevor der
Bot sie zeigt. Er läuft **im Prozess** (ONNX, kein Netzdienst) und braucht ein
Modell von ~135 MB.

**Optional im Wortsinn:** fehlt das Modell, protokolliert das Backend eine Zeile
und ordnet ohne den Reranker — kein Startfehler, nur schwächere Sortierung. Sie
können diesen Schritt also überspringen und später nachholen.

Das Modell liegt **weder im Repository noch im Image**: es ist ein
heruntergeladenes, quantisiertes Artefakt und kein Quellstand. Eine 113-MB-Datei
würde git ohnehin ablehnen (Grenze 100 MB ohne LFS), und in jeder Image-Schicht
wäre sie eine Bremse für jeden Deploy.

```bash
cd /opt/boerdi/deploy
mkdir -p models && cd models

curl -fL -o reranker-model-v1.tar.gz \
  https://github.com/<konto>/<repo>/releases/download/model-v1/reranker-model-v1.tar.gz

# Prüfen, BEVOR entpackt wird — eine halb geladene Datei entpackt sonst still kaputt.
echo "3579e188d181c6ddfc1023d9ef19d0b4337c900a1aa11515ee9cbb89e1d9d02e  reranker-model-v1.tar.gz" \
  | sha256sum -c -

tar -xzf reranker-model-v1.tar.gz && rm reranker-model-v1.tar.gz
cd ..
```

Danach muss `deploy/models/cross-encoder__mmarco-mMiniLMv2-L12-H384-v1-int8/`
sieben Dateien enthalten. Das Compose hängt `deploy/models` schreibgeschützt
unter `/models` in den Container (`RERANK_MODEL_HOST_DIR`, falls Sie es
woanders hinlegen wollen).

**Ob er wirklich greift**, sagt der Gesundheits-Endpunkt — sofort, ohne auf den
ersten Chat zu warten:

```bash
curl -s https://<PUBLIC_HOST>/api/health | grep -o '"reranker":"[a-z-]*"'
```

| Wert | Bedeutung |
|---|---|
| `ready` | eingeschaltet, Modell auffindbar — so soll es sein |
| `model-missing` | **eingeschaltet, aber kein Modell**: der Pfad stimmt nicht |
| `off` | per `RAG_RERANKER_ENABLED=false` bewusst abgeschaltet |

`model-missing` ist der Fall, der ohne dieses Feld unbemerkt bliebe: der Chat
antwortet weiter, nur schlechter sortiert. Dann prüfen, ob das Slug-Verzeichnis
wirklich **unter** `deploy/models/` liegt und nicht eine Ebene tiefer.

Dass das Modell auch in den Speicher geladen wurde, steht beim ERSTEN Zug im
Protokoll (`ready` sagt nur „auffindbar", nicht „geladen"):

```bash
docker compose -f compose.prod.yml logs backend | grep -i rerank
```

`Reranker geladen: cross-encoder__mmarco-…-int8 · N Worker × M Thread(e)` heisst
ja.

<details>
<summary>Woher das Archiv stammt (Nachvollziehbarkeit)</summary>

Es ist eine dynamische int8-Quantisierung (`optimum`/ONNX Runtime, QUInt8,
QOperator) von `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` — die Herkunft steht
in `ort_config.json` und `config.json` im Archiv selbst.

Prüfsummen:

| Datei | SHA-256 |
|---|---|
| `reranker-model-v1.tar.gz` | `3579e188d181c6ddfc1023d9ef19d0b4337c900a1aa11515ee9cbb89e1d9d02e` |
| `model_quantized.onnx` (entpackt) | `084ef9bfef23ebae01f338df29b192cad84480891f87493efb0e3aec8fbd47e0` |

Wer dem Binärartefakt nicht vertrauen will, kann es aus dem Basismodell neu
erzeugen (`optimum` + `torch` + `transformers`) — das ist ein eigener
Werkzeugkasten von ~2–3 GB und gehört nicht auf den Produktivserver.
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
curl -s https://<PUBLIC_HOST>/api/health
```

Drei Dinge in der Antwort ansehen:

| Feld | erwartet |
|---|---|
| `status` | `ok` |
| `mcp_auth` | `service`, wenn ein `MCP_AUTH_TOKEN` gesetzt ist — sonst `anonymous` |
| Modell-Felder | die aus der `.env`, nicht die Code-Defaults |

Dann im Browser:

* `https://<PUBLIC_HOST>/studio/` — Anmeldung mit `STUDIO_PASSWORD`
* `https://<PUBLIC_HOST>/widget/` — die Demo-Seite mit dem eingebetteten Widget

**Zertifikat wirklich geholt?** Ohne diese Prüfung hängt die Seite an der
Selbstsignatur, und der Fehler sieht aus wie ein DNS-Problem:

```bash
docker compose -f compose.prod.yml logs traefik | grep -i -E "certificate|acme"
```

**Kam der Seed an?** Die Frage beantwortet der Bot selbst — im Studio unter
„Muster" müssen die M-Nummern stehen. Leere Listen heissen: Schritt 7c fehlt.

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
`migrate`-Dienst ruft `import-config --only-missing`: Bereiche, die eine neue
Version mitbringt, kommen dazu; alles Gepflegte bleibt unberührt. So wandert
der aktuelle Stand ohne Handgriff mit, ohne die Redaktion zu überschreiben.

**Kein `import-config` ohne `--only-missing` beim Aktualisieren.** Der volle
Import überschreibt die redaktionelle Arbeit mit dem Seed-Stand. Wenn es
wirklich der ganze Baum sein soll: Backup davor.

---

Alles Weitere — Skalieren, Backup, Restore, Rollback, Logs, Traces und die
Sicherheits-Checkliste vor dem Livegang — steht in
[deploy/README.md](deploy/README.md).
