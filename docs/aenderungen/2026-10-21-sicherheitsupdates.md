# Änderungsnotiz — Sicherheitsupdates nach neuen Audit-Meldungen

Stand 2026-10-21 · Basis `main` `8a5f468` · nur Abhängigkeiten, kein eigener Code.

**Warum:** Über Nacht erschienen neue Meldungen; beide Audit-Gates der CI wurden auf `main` rot
(`npm-Audit-Gate`, `pip-audit`), ohne dass sich Code geändert hatte. Solange `ci` rot ist, baut
`image` kein neues `latest`.

| # | Commit | Was | Wo |
|---|---|---|---|
| 1 | Frontend | Angular 22.2.1 → **22.2.3** (alle `@angular/*`, Patch) — bringt `@modelcontextprotocol/server` 2.3.1 (GHSA-jm63-cq47-j5jp, GHSA-46jr-4wx8-v453; nur über `@angular/cli`, ein Entwicklungswerkzeug). `vite` 8.3.0 → **8.3.5** per `overrides` (GHSA-587h-7wmj-h5pm, Dev-Server unter Windows): `@angular/build` 22.2.3 legt `vite` exakt auf 8.3.0 fest, eine Angular-Version mit behobenem `vite` gibt es noch nicht. Mit dabei als Folge-Patches: `nanoid`, `postcss`, `zod` | `frontend/package.json`, `frontend/package-lock.json` |
| 2 | Backend | `certifi` 2026.6.17 → 2026.10.19 (PYSEC-2026-4320); `pillow` 12.3.0 → **13.0.0** (acht CVEs). `pillow` kommt nur über `markitdown` (PDF- und PPTX-Umwandlung beim RAG-Import im Studio) | `backend/uv.lock` |
| 3 | Diese Notiz | | `docs/aenderungen/` |

**Aufräumen später:** Das `overrides`-Feld für `vite` entfernen, sobald eine Angular-Version
`vite` ≥ 8.3.3 selbst mitbringt (dann `npm ls vite` prüfen).

**Hinweis zum Lockfile:** Ein Patch-Update der Angular-Familie lässt sich mit `npm install` nicht
schrittweise machen (exakte Peer-Pins der alten Version blockieren). Ohne `--force`: die
`@angular/*`-Einträge aus `package-lock.json` und `node_modules/@angular` entfernen, dann
`npm install` — alle übrigen Pakete bleiben durch das Lockfile festgehalten.

## Prüfung

- Frontend: `check:audit` grün (`npm audit`: 0 Funde); Unit-Tests ui 943, widget 71, studio 1813
  bestanden; Lint sauber; Widget-Build im Budget (164/175 kB gzip); Studio-Build; `check:tokens`,
  `check:contrast`, `check:radii`, `check:docs`; Lizenzprüfung; Playwright-E2E 50 bestanden.
- Backend: `pip-audit --strict` ohne Funde; RAG-Umwandlungstests (58) bestanden; echte Umwandlung
  einer PPTX mit Bild und einer PDF mit Text über `markitdown` mit `pillow` 13; volle Suite gegen
  Postgres und Valkey.
