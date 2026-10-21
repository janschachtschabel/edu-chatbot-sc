# Architektur-Grafiken

Sechs interaktive Grafiken zu boerdi-chat, erzeugt mit [archify](https://github.com/tt-a1i/archify).
**Ansehen:** [https://janschachtschabel.github.io/edu-chatbot-sc/](https://janschachtschabel.github.io/edu-chatbot-sc/) (GitHub Pages). Die Links auf `.html`-Dateien im
Repository zeigen auf GitHub nur den Quelltext — deshalb führen die Links unten auf die
veröffentlichten Seiten.

| Grafik | Ansehen | Bild (hell) | Quelle | Quellstand |
|---|---|---|---|---|
| Architektur: Widget, Studio, Backend, MCP, b-api | [architektur.html](https://janschachtschabel.github.io/edu-chatbot-sc/architektur.html) | [PNG](png/architektur.png) | [`architektur.json`](quellen/architektur.json) | `2a589a6` |
| Software-Stack: Bibliotheken und Dienste im Zusammenspiel | [software-stack.html](https://janschachtschabel.github.io/edu-chatbot-sc/software-stack.html) | [PNG](png/software-stack.png) | [`software-stack.json`](quellen/software-stack.json) | `2a589a6` |
| Ablauf eines Zuges im Muster-Modus | [ablauf-muster-modus.html](https://janschachtschabel.github.io/edu-chatbot-sc/ablauf-muster-modus.html) | [PNG](png/ablauf-muster-modus.png) | [`ablauf-muster-modus.json`](quellen/ablauf-muster-modus.json) | `2a589a6` |
| Ablauf eines Zuges in der Agent-Schleife | [ablauf-agent-schleife.html](https://janschachtschabel.github.io/edu-chatbot-sc/ablauf-agent-schleife.html) | [PNG](png/ablauf-agent-schleife.png) | [`ablauf-agent-schleife.json`](quellen/ablauf-agent-schleife.json) | `2a589a6` |
| Konfiguration im Muster-Modus: was wo auf das Gespräch wirkt | [konfiguration-muster-modus.html](https://janschachtschabel.github.io/edu-chatbot-sc/konfiguration-muster-modus.html) | [PNG](png/konfiguration-muster-modus.png) | [`konfiguration-muster-modus.json`](quellen/konfiguration-muster-modus.json) | `2a589a6` |
| Konfiguration in der Agent-Schleife: was wo auf das Gespräch wirkt | [konfiguration-agent-schleife.html](https://janschachtschabel.github.io/edu-chatbot-sc/konfiguration-agent-schleife.html) | [PNG](png/konfiguration-agent-schleife.png) | [`konfiguration-agent-schleife.json`](quellen/konfiguration-agent-schleife.json) | `2a589a6` |

In den Konfigurations-Grafiken stehen die Schritte eines Zuges in der Mitte. Oben liegen die
Studio-Bereiche, unten alles außerhalb des Studios: Umgebungsvariablen, Attribute der Einbettung
und der Master-Skill. Jeder Pfeil führt von einer Einstellung zu dem Schritt, in dem sie wirkt.
Die Farbe zeigt, wo eingestellt wird. Gezeigt ist nur, was auf das Gespräch wirkt; reine
Betriebswerte (`LOG_FORMAT`, `FORWARDED_ALLOW_IPS`, `INTERNAL_PORT` …) stehen in
[`deploy/README.md`](../../deploy/README.md) und [`deploy/.env.example`](../../deploy/.env.example).

**Stand Paket 17 (2026-10-20):** b-api-Proxy mit dem Schlüssel des Zuges (`B_API_KEY_MODE`),
b-api-Router-Route (`gpt-6-luna` → `gpt-5.6-luna`), interner Port 8101 mit `/health`, `/ready`,
`/metrics`, Prometheus, JSON-Logs mit Trace-ID, Compose oder Kubernetes.

Die Seiten sind in sich geschlossen: Sie laden keine externen Skripte und keine Web-Fonts.
Jede Komponente verlinkt auf ihre Quellstelle im Repository.

## Lokal nutzen

`index.html` im Browser öffnen, per Doppelklick oder über *Datei → Öffnen*. Alles läuft aus dem
Dateisystem und offline; die Startseite verlinkt die drei Grafiken relativ. Über das Menü
**Exportieren** lassen sich die Grafiken zusätzlich als Bild für Folien speichern.

Wer lieber eine Adresse im lokalen Netz zeigt, startet im Ordner einen einfachen Webserver und
öffnet `http://localhost:8000`:

```bash
python -m http.server 8000
```

## Veröffentlichen mit GitHub Pages

Der Workflow [`pages.yml`](../../.github/workflows/pages.yml) veröffentlicht **nur die HTML-Seiten
dieses Ordners**. Ohne die Repo-Variable `PAGES_AKTIV` wird er übersprungen, statt zu scheitern.
**Eingeschaltet seit 2026-10-18** (Quelle „GitHub Actions“, `PAGES_AKTIV=true`); jeder Push auf
`main`, der diesen Ordner ändert, veröffentlicht neu. Die Schritte unten gelten für einen Fork
oder ein neues Repository.

1. **Voraussetzung:** Das Repository ist öffentlich, oder der GitHub-Plan ist bezahlt; für ein
   privates Repository auf GitHub Free gibt es kein Pages. Die Seite selbst ist in jedem Fall
   öffentlich erreichbar.
2. **Einschalten:** *Settings → Pages → Build and deployment → Source:* **GitHub Actions**.
   **Nicht** „Deploy from a branch“ mit dem Ordner `/docs` wählen. Dann wäre der ganze
   `docs/`-Ordner öffentlich, samt Plänen und Audit-Berichten.
3. **Freigeben:** *Settings → Secrets and variables → Actions → Variables:* `PAGES_AKTIV` = `true`.
4. **Erster Lauf:** *Actions → pages → Run workflow*. Danach veröffentlicht jeder Push auf `main`,
   der diesen Ordner ändert, von selbst.

## Neu erzeugen

Die Quellen liegen unter [`quellen/`](quellen/). Nach Änderungen am Quelltext:

1. In den Quellen die Belege nachziehen: Pfade, Zeilen und `meta.repository.revision`
   (der neue Commit).
2. Aus der Wurzel eines sauberen Klons, der diesen Commit enthält, neu erzeugen:

```bash
node <archify>/bin/archify.mjs finalize architecture docs/architektur-grafiken/quellen/architektur.json docs/architektur-grafiken/architektur.html --repo-root . --quality showcase
```

```bash
node <archify>/bin/archify.mjs finalize workflow docs/architektur-grafiken/quellen/ablauf-muster-modus.json docs/architektur-grafiken/ablauf-muster-modus.html --repo-root . --quality showcase
```

```bash
node <archify>/bin/archify.mjs finalize workflow docs/architektur-grafiken/quellen/ablauf-agent-schleife.json docs/architektur-grafiken/ablauf-agent-schleife.html --repo-root . --quality showcase
```

```bash
node <archify>/bin/archify.mjs finalize architecture docs/architektur-grafiken/quellen/software-stack.json docs/architektur-grafiken/software-stack.html --repo-root . --quality showcase
```

```bash
node <archify>/bin/archify.mjs finalize architecture docs/architektur-grafiken/quellen/konfiguration-muster-modus.json docs/architektur-grafiken/konfiguration-muster-modus.html --repo-root . --quality showcase
```

```bash
node <archify>/bin/archify.mjs finalize architecture docs/architektur-grafiken/quellen/konfiguration-agent-schleife.json docs/architektur-grafiken/konfiguration-agent-schleife.html --repo-root . --quality showcase
```

Jede Quelle trägt ihren eigenen Stand in `meta.repository.revision`. archify prüft die Belege
gegen diesen Commit; der Klon unter `--repo-root` muss ihn also enthalten.

**Bilder für Folien und Dokumente:** Unter [`png/`](png/) liegt jede Grafik als PNG im hellen
Modus — exportiert über *Exportieren → PNG* des Viewers bei hellem Thema. Nach dem Neu-Erzeugen
ebenso neu exportieren.

`finalize` legt neben jede Grafik Prüfbelege (`*.delivery.json` u. a.) mit lokalen Pfaden ab.
Die [`.gitignore`](.gitignore) hält sie aus dem Repository.
