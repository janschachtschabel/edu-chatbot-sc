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

## Veröffentlichen mit GitHub Pages

Der Workflow [`pages.yml`](../../.github/workflows/pages.yml) veröffentlicht **nur die HTML-Seiten
dieses Ordners**. Er läuft bei jedem Push auf `main`, der den Ordner ändert, und auf Knopfdruck.

- **Einmalig einschalten:** *Settings → Pages → Build and deployment → Source:* **GitHub Actions**.
- **Nicht** „Deploy from a branch“ mit dem Ordner `/docs` wählen. Dann wäre der ganze
  `docs/`-Ordner öffentlich, samt Plänen und Audit-Berichten.
- **Privates Repository:** Pages braucht dafür einen bezahlten GitHub-Plan. Die Seite selbst ist
  trotzdem öffentlich erreichbar.
- **Erster Lauf:** Ist Pages beim Merge noch nicht eingeschaltet, scheitert der Workflow. Danach
  einschalten und ihn unter *Actions → pages → Run workflow* einmal von Hand starten.

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
