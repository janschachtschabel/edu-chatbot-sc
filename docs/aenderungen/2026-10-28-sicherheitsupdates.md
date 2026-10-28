# Änderungsnotiz — Sicherheitsupdates nach neuen Audit-Meldungen

Stand 2026-10-28 · Basis `main` `56671f8` · nur Abhängigkeiten, kein eigener Code.

**Warum:** Seit dem letzten Update (2026-10-21) sind neue Meldungen erschienen; beide Audit-Gates
der CI wurden rot (`pip-audit`, `npm-Audit-Gate`), ohne dass sich Code geändert hatte. Aufgefallen
im PR #27 (Paket 18A/18B), betrifft aber `main` genauso.

| # | Commit | Was | Wo |
|---|---|---|---|
| 1 | Backend | `litellm` 1.91.5 → **1.100.4** (CVE-2026-114612, GHSA-g5ff-637f-6q2m; kleinste behobene Version). `huggingface-hub` 1.23.0 → 2.3.0, damit `filelock` 3.29.7 → **4.2.4** kommt (CVE-2026-112940, -112913, -112907; `huggingface-hub` 1.x deckelte `filelock` unter 4 — unser Code nutzt es nicht direkt, nur `tokenizers` 0.23.1 → 0.23.3). OpenTelemetry 1.43.0 → **1.45.1** bzw. 0.64b0 → 0.66b1 (CVE-2026-114603). Neu im Baum über `litellm`: `boto3`, `botocore`, `s3transfer`, `jmespath` u. a. (Lizenzen geprüft) | `backend/uv.lock` |
| 2 | Frontend | `dompurify` 3.4.16 → **3.4.17** (GHSA-cg2g-xh64-v4q7 critical, GHSA-mrv2-3pqr-j5jr high — der HTML-Bereiniger des Widgets). `undici` 7.30.0 → **7.30.1** (vier High-Meldungen; nur über `jsdom` in den Tests) und 6.29.0 → 6.29.1 (über `node-gyp`). Per `npm update` im erlaubten Bereich, `package.json` unverändert | `frontend/package-lock.json` |
| 3 | Diese Notiz | | `docs/aenderungen/` |

**Betrieb:** Image neu bauen. Keine Migration, keine neue Einstellung. Das Image wird durch
`boto3`/`botocore` etwas größer.

## Prüfung

- Backend: `pip-audit --strict` ohne Funde, Lizenz-Gate grün; volle Suite gegen Postgres und Valkey
  (6690 bestanden, 2 übersprungen). Live-Smoke mit `litellm` 1.100.4 gegen OpenAI direkt
  (`gpt-6-luna` über `/v1/responses`): Werkzeugaufruf, Textantwort und Moderation laufen.
- Frontend: `check:audit` ohne Fund ab high; Unit-Tests ui, widget und studio bestanden; Lint
  sauber; Widget-Build im Budget (563/600 kB roh, 164/175 kB gzip).
