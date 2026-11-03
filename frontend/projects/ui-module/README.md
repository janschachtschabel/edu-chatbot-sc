# UI-Module

Kleine Oberflächen, die der Chatbot in einer Antwort zeigt und die die KI wie Werkzeuge nutzt
(Paket U1, Plan `docs/plans/2026-11-02-paket-u1-ui-module.md`). Sie werden im selben Bündel wie
das Widget gebaut und sehen aus wie das Widget.

## Ein neues Modul

```bash
npm run module:neu -- linkbox            # anzeigend
npm run module:neu -- entscheidung --abfragen
```

Das legt `src/ui-<name>/` an:

| Datei | Inhalt |
|---|---|
| `manifest.json` | Was das Modul tut, wann die KI es nutzen soll, **Eingabe** (`eingabe`) und bei abfragenden Modulen **Antwort** (`antwort`) als JSON Schema, Textfassung, Beispiele |
| `ui-<name>.component.ts` | Angular-Komponente mit den Eingaben `daten` und `kontext` |
| `ui-<name>.component.scss` | Stil, nur über die Tokens des Widgets (`--mat-sys-*`, Radien der M3-Skala) |
| `ui-<name>.component.spec.ts` | Tests der Komponente |
| `README.md` | wofür, Grenzen, Beispiel |

Nach jeder Änderung an einem Manifest: `npm run module:register`. Das erzeugt
`src/register.generated.ts` und im Backend `boerdi/ui_module/manifeste.json`; die CI prüft, dass
beides aktuell ist, und das Backend prüft jedes Manifest samt Beispielen gegen
`src/_vertrag/manifest.schema.json`.

## Ein- und Ausgabe

Jedes Modul bestimmt seine Datenform selbst. Ein Inhaltsrahmen braucht nur Titel und Markdown,
ein Themenbaum eine verschachtelte Struktur. Die KI erfährt das aus dem Manifest: `eingabe` wird
die Parameterbeschreibung des Werkzeugs — deshalb trägt **jedes Feld eine `description`**.
Große Daten (Bäume, Trefferlisten) gibt die KI nicht selbst an; dafür nennt das Manifest eine
`datenquelle`, und das Backend holt die Daten. Das Backend prüft die Daten beim Werkzeugaufruf
gegen `eingabe` und meldet Abweichungen der KI zurück (seit U1-d1 für jedes Modul mit
`agent: true` über `ui_module/werkzeuge.modul_aufruf_annehmen`; der Inhaltsrahmen hat sein
eigenes Dokument-Werkzeug, Linkbox und Trefferliste entstehen ohne Aufruf).

## Regeln

- **Keine eigenen Netzaufrufe, keine Zugangsdaten.** Was nach außen wirkt (Datei speichern,
  Drucken, Antworten), geht über `MODUL_HOST` (`src/_vertrag/modul-host.ts`). Markdown
  rendert ebenfalls der Host (`markdown(text)`, bereinigt wie die Bot-Antworten) — nie selbst
  `innerHTML` mit ungeprüftem Text setzen. Links baut der Host (`link(url)` → `href` mit
  Sitzungs-Kennung bei vertrauten Seiten, `hinweis` bei fremden).
- **Fähigkeiten:** Jeder Block bekommt seinen eigenen Host (seit U1-d1). Er lässt nur zu, was
  `faehigkeiten` im Manifest nennt — `herunterladen`, `drucken`, `oeffnen` (`link`, `aktion`),
  `antworten`; sonst passiert nichts außer einer Warnung in der Konsole. `markdown`, `treffer`
  und `beschaeftigt` sind immer erlaubt.
- **Abfragende Module** (`art: abfragen`, erstes: `ui_entscheidung`) antworten mit
  `host.antworten(daten, text)`: `daten` nach `antwort`, `text` die lesbare Fassung (Nutzerblase).
  Die Shell sendet das als nächsten Zug (`ui_antwort`), das Backend prüft es gegen die offene
  Frage. Danach ist der Block `beantwortet` (nur lesend mit `kontext().antwort`); jeder andere
  Zug der Person macht offene Fragen `veraltet`.
- **Platz:** `darstellung.platz` — `oben` (Vorgabe) vor den Trefferboxen, `unten` danach.
- **Abgeleitete Module** (Linkbox, später Trefferliste) entstehen ohne Werkzeugaufruf aus der
  Antwort (`backend/src/boerdi/ui_module/abgeleitet.py`, Namen in `namen.py`); ein Muster wählt
  sie mit `ui_module:`.
- **Importe:** aus `_vertrag/` und aus Einzeldateien von `@boerdi/ui` (Icons, Druck-Helfer,
  Markdown) — nie aus der Chat-Shell oder dem Sammel-Export `@boerdi/ui` (ESLint prüft das).
  Die Shell liest von hier nur Vertrag und Register.
- **Fehler:** Angular fängt einen Fehler beim Rendern nicht je Modul ab. Die Spec eines Moduls
  rendert darum jedes Beispiel aus dem Manifest (das Gerüst legt diese Spec an).
- **Barrierefrei** (WCAG 2.2 AA), bedienbar ab 320 px Breite, Texte auf Deutsch und Englisch
  (`kontext().sprache`).
- **`kontext().nurLesen`** heißt: beantwortet oder veraltet — nur zeigen, nichts auslösen.
- Eine neue Hauptversion (`version`) nur, wenn alte Daten nicht mehr passen; ein altes Widget
  zeigt dann die Textfassung.
- **Studio (U1-f):** Die Seite „UI-Module“ zeigt jedes Modul mit seinen Manifest-Beispielen
  (echte Komponente, Host ohne Wirkung nach außen) und schaltet es an/aus bzw. „für den Agenten“
  (`display_rules.ui_module` in `01-base/display-rules`). Ein neues Modul kommt dort von selbst an;
  die Studio-Spec `ui-modul-vorschau.component.spec.ts` verlangt nur, dass sein Manifest dort
  importiert wird. `ui_inhaltsrahmen` ist fest (Systemarten).
