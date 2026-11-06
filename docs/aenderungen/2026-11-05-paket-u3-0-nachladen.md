# Paket U3-0: Nachladen seltener UI-Module (2026-11-05)

Plan: [`../plans/2026-11-04-pakete-sammlungsstrukturen-upload-mcp.md`](../plans/2026-11-04-pakete-sammlungsstrukturen-upload-mcp.md)
(Fassung 3, §5.4, §9 U3-0, §16). Entwicklerdoku: [`../ui-module.md`](../ui-module.md) §2.5.

## Warum

Das Widget-Bündel lag bei 189,0 kB gzip (Warnung ab 190, Grenze 200). Jedes weitere Modul — zuerst
`ui_upload` (U3-1) — muss deshalb außerhalb des Haupt-Bündels liegen und erst geladen werden, wenn sein
Block erscheint. Angulars eigene Lazy-Chunks brechen die klassische `<script defer>`-Einbettung; gewählt
ist deshalb ein rahmenloses Custom Element je Modul in einem eigenen Bündel mit SRI.

## Was sich ändert

| Bereich | Änderung |
|---|---|
| Manifest | neues Feld `laden: "sofort" \| "bei_bedarf"` (Schema, TS-Typ, Backend-Katalog) |
| Register | `module-register.mjs`: Module mit `bei_bedarf` → Platzhalter + Element-Name, Quelltext `ui-<name>.element.ts` |
| ui-module | `_nachladen/`: Element-Vertrag, Host-Brücke (eingefroren, ohne `markdown`/`treffer`), Platzhalter-Komponente |
| ui | `ui-bloecke/nachladen.ts` (Lader mit SRI, Trusted Types, Frist, einmal je Modul), `nachlade-index.ts` (leer, beim Build ersetzt), `<boerdi-ui-bloecke>` Eingabe `nachladen`, Shell gibt den Lader weiter; `ChatApiClient.apiBasis()` |
| Build | `scripts/build-nachlade-module.mjs` (esbuild, `iife`, Hash im Namen, SRI-Index), `build:widget` ruft es zuerst; `fileReplacements` im Ziel `build-widget`; `esbuild` 0.28.2 als ausdrückliche devDependency (war transitiv da) |
| Budget | `scripts/check-module-budget.mjs` (je Modul ≤ 15 kB gzip, zusammen ≤ 60 kB), in `npm run budget` und CI |
| Backend | `GET /widget/module/{datei}`: nur gehashte Namen aus `widget_dist/module/`, immutable, CORS `*`, `nosniff`; OpenAPI (`openapi-v1.json`) neu erzeugt, Eintrag in `docs/api/bewusste-vertragszusaetze.md` |
| Auslieferung | Dockerfile kopiert `dist/widget-module` → `widget_dist/module` |
| CI | Tests der Nachlade-Skripte und Modul-Budget als eigene Schritte |

Noch kein nachgeladenes Modul im Bestand — das erste kommt mit U3-1 (`ui_upload`); dort folgen der
Studio-Lader für die Vorschau und der E2E-Nachweis im Browser.

## Prüfung (nach der Review-Runde)

- Backend ganz mit Postgres: **8052 bestanden, 4 übersprungen, 1 rot** — `test_i18n_messages` kannte den
  neuen Auslieferungstext `asset not found` nicht; als bewusst einsprachig eingetragen (wie die übrigen
  Texte von `widget.py`), danach `test_i18n_messages.py` 31/31. ruff sauber. OpenAPI `--check` nach
  Neuerzeugung unverändert, Bereichs-Schemas unverändert.
- Frontend: `ng test` ui-module 166, ui 1150, widget 76, studio 1959 bestanden; Skript-Tests
  (`module-register` 13, `build-nachlade-module` 4, `check-module-budget` 4); eslint sauber;
  `module:register --pruefen` aktuell; `check:tokens`, `check:a11y`, `check:radii` sauber.
- `npm run build:widget` mit Bündel-Schritt: Haupt-Bündel **189,74 kB gzip** (+0,74 kB gegenüber main),
  654,23 kB roh; Widget- und Modul-Budget grün.
- Nicht geprüft: Laden eines echten Bündels im Browser — es gibt noch kein nachgeladenes Modul; der
  E2E-Nachweis kommt mit `ui_upload` (U3-1).

## Review (2026-11-05) — Befunde und Behebung

| # | Schwere | Befund | Behebung | Test |
|---|---|---|---|---|
| 1 | MAJOR | Neue öffentliche Route fehlte im Routen-Inventar und in der Liste öffentlicher Routen des Vertragstests → Backend-CI rot | `tests/test_openapi_contract.py`: `GET /widget/module/{datei}` in `EXPECTED_ROUTES` und `PUBLIC_ROUTES` | `test_openapi_contract.py` 5/5 (vorher 2 rot) |
| 2 | MINOR | Trusted-Types-Richtlinie hielt die API-Basis des ersten Ladens fest | Richtlinie prüft den aufgelösten Pfad gegen das Muster gehashter Bündel, unabhängig von der Basis | Spec „neue API-Basis“, „`..`-Umweg“ |
| 3 | MINOR | Lader und Richtlinie je Shell: zweites Widget → doppeltes `createPolicy` (wirft unter CSP), Bündel läuft zweimal | Richtlinie und laufende Ladevorgänge je Seite, Schlüssel Adresse; Pflicht „nur definieren, wenn frei“ im Element-Vertrag und §2.5 | Specs „zwei Widgets“, „schon geladen“ |
| 4 | MINOR | Zuweisungen ans Element liefen verfolgt: Signale, die das Element beim Zeichnen liest, lösten neue Läufe aus; `host` bei jedem Lauf neu | Zuweisungen in `untracked`, `host` nur beim Erzeugen | Specs „beschaeftigt/Host einmal“, „fremde Signale“ (vorher rot) |
| 5 | MINOR | Lokal und im E2E lagen die Bündel nicht dort, wo das Backend sucht | Einstellung `WIDGET_MODULE_DIR` (leer = `<WIDGET_DIST_DIR>/module`); README, `.env.example`, Helm, Compose-Kommentar, §2.5 | `test_the_module_directory_can_live_elsewhere` (vorher rot) |
| 6 | NIT | Einrückung in `ui-bloecke.component.spec.ts` | korrigiert | — |
| 7 | NIT | halb maskierte Regex im Bündel-Test | Vergleich mit dem erwarteten Literal | Bündel-Tests 4/4 |

## Deploy

Keine Migration. Neue **optionale** Umgebungsvariable `WIDGET_MODULE_DIR` (im Image nicht nötig). Das Image muss mit dem neuen Dockerfile gebaut werden
(kopiert `widget_dist/module`). Ein Proxy vor dem Backend muss `/widget/module/*` durchreichen.
