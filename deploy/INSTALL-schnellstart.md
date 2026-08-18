# Schnellstart: Debian 13 → laufender Chatbot

Befehlsabfolge für einen frischen Server, **ohne Editor** — jede Datei entsteht
per Kommando. Getestet am 2026-08-13 auf Debian 13 (Trixie).

Diese Datei ist die knappe, wiederverwendbare Fassung. Die ausführliche
Begründung jedes Schritts steht in [../INSTALL.md](../INSTALL.md), der Betrieb
danach (Skalieren, Backup, Rollback) in [README.md](README.md).

**Was hier eingerichtet wird:** b-api staging als LLM-Anbieter mit
`gpt-5.6-luna`, kein Reranker, eine Backend-Replika, Hostname über nip.io mit
Let's-Encrypt-Zertifikat.

---

## 0. Parameter — einmal setzen

Alles Weitere leitet sich hieraus ab. Für einen anderen Server nur diese Zeile
ändern.

```bash
export SERVER_IP=87.106.127.225
export HOST=${SERVER_IP}.nip.io
export ACME_MAIL=technik@example.org
```

`nip.io` löst `<ip>.nip.io` auf `<ip>` auf — damit gibt es einen echten
Hostnamen ohne eigene DNS-Zone, und Let's Encrypt kann ausstellen.

## 1. Grundsystem und Firewall

```bash
apt update && apt upgrade -y && apt install -y ca-certificates curl git ufw && ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp && ufw --force enable
```

## 2. Docker

Aus Dockers eigenem Repository — `docker.io` aus Debian bringt kein
`docker compose` v2.

```bash
install -m 0755 -d /etc/apt/keyrings && curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc && chmod a+r /etc/apt/keyrings/docker.asc && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" > /etc/apt/sources.list.d/docker.list && apt update && apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin && docker compose version
```

Meldet `apt update` einen 404, führt Docker für Trixie noch keine Pakete — dann
`trixie` in der Zeile durch `bookworm` ersetzen und wiederholen.

## 3. Quellen holen

```bash
mkdir -p /opt/boerdi && cd /opt/boerdi && git clone https://github.com/janschachtschabel/edu-chatbot-sc.git . && git log -1 --format='%h %s'
```

## 4. Image bauen

```bash
cd /opt/boerdi && free -m | awk '/^Mem:/ {print "  RAM: "$2" MB"; if ($2 < 3500) print "  ACHTUNG: unter 3,5 GB — der Angular-Build kann am Speicher scheitern"}' && docker build -t boerdi-chat .
```

Dauert einige Minuten (zwei Angular-Builds im Image). `boerdi-chat` ist genau
der Name, den `compose.prod.yml` als Default erwartet — `BOERDI_IMAGE` in der
`.env` bleibt deshalb leer.

Gegenprobe, dass die Seed-Daten im Image liegen (Schritt 7 braucht sie):

```bash
docker run --rm boerdi-chat sh -c 'find /app/seeds -type f | wc -l'
```

Erwartet: **61**.

## 5. Geheimnisse abfragen

Der b-api-Schlüssel wird nicht angezeigt und landet nicht in der Shell-History.

```bash
read -rsp "b-api-Schluessel (staging): " B_API_KEY_IN && echo && export B_API_KEY_IN
```

## 6. `.env` schreiben

```bash
cd /opt/boerdi/deploy && umask 077 && cat > .env <<EOF
POSTGRES_PASSWORD=$(openssl rand -hex 32)
STUDIO_API_KEY=$(openssl rand -hex 32)
STUDIO_PASSWORD=$(openssl rand -hex 16)
PUBLIC_HOST=${HOST}
ACME_EMAIL=${ACME_MAIL}
CORS_ORIGINS=https://${HOST}
BACKEND_REPLICAS=1
LLM_PROVIDER=b-api-openai
B_API_BASE_URL=https://b-api.staging.openeduhub.net/api/v1/llm
B_API_KEY=${B_API_KEY_IN}
LLM_CHAT_MODEL=gpt-5.6-luna
LLM_EMBED_MODEL=text-embedding-3-small
LLM_MAX_CONCURRENCY=2
BG_LLM_MAX_CONCURRENCY=1
LLM_READ_TIMEOUT=75
LOG_LEVEL=INFO
EOF
chmod 600 .env && unset B_API_KEY_IN && docker compose -f compose.prod.yml --env-file .env config >/dev/null && echo "OK — .env vollstaendig"
```

Drei Werte sind nicht beliebig:

* **`POSTGRES_PASSWORD` in Hex, nicht Base64.** Es landet in der DSN
  `postgresql+asyncpg://user:PASS@postgres:5432/db`; ein `/` aus
  `openssl rand -base64` zerlegt die URL.
* **`LLM_MAX_CONCURRENCY=2`** — die b-api erlaubt exakt zwei parallele Aufrufe
  und antwortet darüber mit 429 ohne `retry-after`. Der Code-Default ist 20.
* **`BACKEND_REPLICAS=1`** — das b-api-Limit gilt pro Schlüssel, nicht pro
  Prozess. Zwei Replikas mit je zwei Aufrufen wären vier.

**Kein Reranker:** es gibt kein `RERANK_MODEL_HOST_DIR` und kein
`deploy/models`. Ohne Modell findet der Code keine `.onnx` und sortiert nicht
um — kein Startfehler.

## 7. Schema und Seed-Daten

```bash
cd /opt/boerdi/deploy && docker compose -f compose.prod.yml --env-file .env up -d postgres && sleep 10 && docker compose -f compose.prod.yml --env-file .env up migrate
```

Erwartet: zwei Alembic-Upgrades, dann
`imported 61 areas (31 yaml, 30 md) from seeds`.

Der `migrate`-Dienst führt `alembic upgrade head` **und**
`boerdi import-config --only-missing` aus. Das `--only-missing` ist der Grund,
warum er automatisch laufen darf: er legt nur an, was fehlt. Ein Lauf ohne die
Option überschreibt jede redaktionelle Änderung aus dem Studio.

## 8. Stack starten

```bash
cd /opt/boerdi/deploy && docker compose -f compose.prod.yml --env-file .env up -d && sleep 20 && docker compose -f compose.prod.yml --env-file .env ps
```

## 9. Abnahme

```bash
curl -sS https://${HOST}/api/health | python3 -m json.tool
```

Erwartet:

```json
{
    "status": "ok",
    "provider": "b-api-openai",
    "chat_model": "gpt-5.6-luna",
    "embed_model": "text-embedding-3-small",
    "mcp_auth": "anonymous",
    "reranker": "model-missing"
}
```

`reranker: model-missing` heisst „eingeschaltet, aber kein Modell da" — genau
der gewünschte Zustand. `mcp_auth: anonymous` heisst: WLO-Werkzeuge nur lesend.

Zertifikat prüfen:

```bash
echo | openssl s_client -connect ${HOST}:443 -servername ${HOST} 2>/dev/null | openssl x509 -noout -issuer -dates
```

Erwartet `issuer=… O=Let's Encrypt …`. Steht dort etwas anderes, hat ACME nicht
geklappt und traefik liefert sein eigenes selbstsigniertes Zertifikat aus — die
Seite läuft, der Browser warnt. Ursache im Log suchen:

```bash
docker compose -f /opt/boerdi/deploy/compose.prod.yml --env-file /opt/boerdi/deploy/.env logs traefik | grep -i "acme\|certificate\|rateLimited"
```

Keine Treffer bei gültigem Zertifikat sind normal — traefik protokolliert einen
erfolgreichen ACME-Vorgang auf `INFO` nicht.

Nur traefik darf Ports veröffentlichen:

```bash
docker ps --format "{{.Names}}\t{{.Ports}}" | grep 0.0.0.0
```

## 10. Studio-Zugang

```bash
grep -E '^STUDIO_(PASSWORD|API_KEY)=' /opt/boerdi/deploy/.env
```

`STUDIO_PASSWORD` ist die Anmeldung für Menschen, `STUDIO_API_KEY` der
Maschine-zu-Maschine-Schlüssel. Beide gehören in einen Passwortspeicher.

---

## URLs

Alle am 2026-08-13 gegen den laufenden Server geprüft.

| Zweck | URL |
|---|---|
| Gesundheit / Konfigurationsnachweis | `https://<HOST>/api/health` |
| Studio (Redaktion) | `https://<HOST>/studio` |
| Widget-Demo, schwebender Knopf | `https://<HOST>/widget/` |
| Widget-Demo, eingebettet in Seite | `https://<HOST>/widget/inline` |
| Widget-Demo, klassische Ansicht | `https://<HOST>/widget/classic` |
| **Widget-Bundle zum Einbetten** | `https://<HOST>/widget/boerdi-widget.js` |
| Öffentliches Konfigurations-Bündel | `https://<HOST>/api/config/guide-mode` |
| Chat-API | `POST https://<HOST>/api/chat` |
| Chat-API im Strom (SSE) | `POST https://<HOST>/api/chat/stream` |

Das Bundle antwortet mit **302** auf eine Digest-URL
(`/widget/boerdi-widget.<digest>.js`) — Absicht: die kurze URL ist `no-store`,
die Digest-URL `immutable`. Immer die kurze einbinden, nie die Digest-URL
festschreiben.

**Einbetten in eine fremde Seite:**

```html
<script src="https://<HOST>/widget/boerdi-widget.js" defer></script>
<boerdi-chat></boerdi-chat>
```

Das funktioniert **ohne Zutun aus jeder Domäne**: CORS ist standardmäßig offen
(`CORS_ALLOW_ALL=true`). Wer zumachen will, setzt den Schalter auf `false` — dann
gilt `CORS_ORIGINS`, und nur dann. Mehrere Domänen kommagetrennt:

```bash
cd /opt/boerdi/deploy && sed -i "s|^CORS_ORIGINS=.*|CORS_ORIGINS=https://${HOST},https://wirlernenonline.de|;s|^CORS_ALLOW_ALL=.*|CORS_ALLOW_ALL=false|" .env && docker compose -f compose.prod.yml --env-file .env up -d backend
```

**Jaeger (Traces)** ist bewusst nicht öffentlich. Zugriff über einen
SSH-Tunnel vom Arbeitsplatz aus:

```bash
ssh -N -L 16686:127.0.0.1:16686 root@<SERVER_IP>
```

Danach `http://localhost:16686` im Browser.

---

## Aktualisieren

Neuer Stand aus GitHub, Image neu bauen, rollierend austauschen:

```bash
cd /opt/boerdi && git pull && docker build -t boerdi-chat . && cd deploy && docker compose -f compose.prod.yml --env-file .env up migrate && docker compose -f compose.prod.yml --env-file .env up -d
```

Der `migrate`-Lauf ist dabei ungefährlich: neue Config-Bereiche einer Version
kommen dazu, gepflegte bleiben unberührt.

**Die `.env` überlebt das** — sie liegt nur auf dem Server und steht in
`.gitignore`. Ein `git pull` fasst sie nicht an.

Zurück auf einen früheren Stand:

```bash
cd /opt/boerdi && git log --oneline -10
```

Dann `git checkout <sha>`, neu bauen, `up -d`. Der Datenbank-Inhalt bleibt.

---

## Was schiefgehen kann

**Der Bau scheitert am Speicher.** Zwei Angular-Builds brauchen zusammen
mehrere GB. Mit unter 3,5 GB RAM entweder Swap ergänzen oder das Image
anderswo bauen und als Tar übertragen:

```bash
docker save boerdi-chat | ssh root@<SERVER_IP> 'docker load'
```

**`migrate` bricht ab mit `no such file /app/seeds`.** Dann läuft ein Image von
vor der Seed-Auslieferung. Neu bauen.

**Der Chat antwortet mit 429.** `LLM_MAX_CONCURRENCY` oder `BACKEND_REPLICAS`
zu hoch — siehe Schritt 6.

**Das Studio meldet 401 trotz richtigem Passwort.** `STUDIO_COOKIE_SECURE` steht
auf 1 und der Cookie kommt nur über HTTPS zurück. Prüfen, dass die Seite
tatsächlich über `https://` aufgerufen wird.
