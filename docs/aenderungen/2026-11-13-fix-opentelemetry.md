# Fix: OpenTelemetry 1.45.1 → 1.45.2 (2026-11-13)

Der CI-Lauf auf `main` nach dem Merge von PR #65 war rot: Job `licenses-backend`, Schritt
`pip-audit`. Für `opentelemetry-api 1.45.1` war eine Lücke neu veröffentlicht worden
(CVE-2026-126360, behoben ab 1.45.2). Der PR-Lauf mit demselben Stand war gut drei Stunden vorher
noch grün; der Code von PR #65 war nicht die Ursache. Weil der Lauf rot war, wurde der Image-Bau
für `da1ccd5` übersprungen.

- `opentelemetry-api` lässt sich nicht allein anheben: Die übrigen Pakete der Familie binden die
  Version fest. `uv lock --upgrade-package …` für alle 16 OpenTelemetry-Pakete hebt sie zusammen
  an, auf 1.45.2 und 0.66b2. Sonst ändert sich im Lock nichts; `pyproject.toml` bleibt unverändert.
- Geprüft:
  - `pip-audit` wie in der CI: keine bekannten Lücken;
  - Lizenzprüfung grün;
  - 132 Tests rund um Tracing, Start, OpenAPI und den MCP-Client grün.
- Deploy: Das Image neu bauen genügt.
