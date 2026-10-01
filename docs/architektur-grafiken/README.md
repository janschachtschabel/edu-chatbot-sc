# Architektur-Grafiken

Drei interaktive Grafiken zu boerdi-chat, erzeugt mit [archify](https://github.com/tt-a1i/archify)
aus dem Quellstand `989ae75`. Die Startseite ist [`index.html`](index.html).

| Grafik | Datei |
|---|---|
| Architektur: Widget, Studio, Backend, MCP | [`architektur.html`](architektur.html) |
| Ablauf eines Zuges im Muster-Modus | [`ablauf-muster-modus.html`](ablauf-muster-modus.html) |
| Ablauf eines Zuges in der Agent-Schleife | [`ablauf-agent-schleife.html`](ablauf-agent-schleife.html) |

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

`finalize` legt neben jede Grafik Prüfbelege (`*.delivery.json` u. a.) mit lokalen Pfaden ab.
Die [`.gitignore`](.gitignore) hält sie aus dem Repository.
