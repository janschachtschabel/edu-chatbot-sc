# Architektur-Grafiken

Sechs interaktive Grafiken zu boerdi-chat, erzeugt mit [archify](https://github.com/tt-a1i/archify).
Die Startseite ist [`index.html`](index.html).

| Grafik | Datei | Quellstand |
|---|---|---|
| Architektur: Widget, Studio, Backend, MCP | [`architektur.html`](architektur.html) | `989ae75` |
| Software-Stack: Bibliotheken und Dienste im Zusammenspiel | [`software-stack.html`](software-stack.html) | `1f069e9` |
| Ablauf eines Zuges im Muster-Modus | [`ablauf-muster-modus.html`](ablauf-muster-modus.html) | `989ae75` |
| Ablauf eines Zuges in der Agent-Schleife | [`ablauf-agent-schleife.html`](ablauf-agent-schleife.html) | `989ae75` |
| Konfiguration im Muster-Modus: was wo auf das Gespräch wirkt | [`konfiguration-muster-modus.html`](konfiguration-muster-modus.html) | `1f069e9` |
| Konfiguration in der Agent-Schleife: was wo auf das Gespräch wirkt | [`konfiguration-agent-schleife.html`](konfiguration-agent-schleife.html) | `1f069e9` |

In den Konfigurations-Grafiken stehen die Schritte eines Zuges in der Mitte. Oben liegen die
Studio-Bereiche, unten alles außerhalb des Studios: Umgebungsvariablen, Attribute der Einbettung
und der Master-Skill. Jeder Pfeil führt von einer Einstellung zu dem Schritt, in dem sie wirkt.
Die Farbe zeigt, wo eingestellt wird.

Die Seiten sind in sich geschlossen: Sie laden keine externen Skripte und keine Web-Fonts.
Jede Komponente verlinkt auf ihre Quellstelle im Repository; die Links setzen dort Zugang voraus.

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

`finalize` legt neben jede Grafik Prüfbelege (`*.delivery.json` u. a.) mit lokalen Pfaden ab.
Die [`.gitignore`](.gitignore) hält sie aus dem Repository.
