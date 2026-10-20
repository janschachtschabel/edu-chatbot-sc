# Änderungsnotiz — Architektur-Grafiken auf Paket 17, Service-Steckbrief

Stand 2026-10-20 · Basis `main` `2a589a6` · nur Dokumentation, kein Code, kein Deploy-Schritt.

| # | Commit | Was | Wo |
|---|---|---|---|
| 1 | Architektur-Grafiken auf Paket 17 | Alle sechs Grafiken neu auf `2a589a6` verankert (Belegzeilen nachgezogen) und neu erzeugt, PNGs (hell) neu exportiert. Architektur: b-api-Proxy mit dem Schlüssel des Zuges (`B_API_KEY_MODE`), Kubelet/Prometheus am internen Port 8101, LLM-Route `gpt-6-luna` → `gpt-5.6-luna`, Compose oder Kubernetes. Software-Stack: `prometheus-client`, Prometheus, zwei Uvicorn-Ports, JSON-Logs mit Trace-ID. Konfiguration: LLM-Knoten mit Route. Abläufe: Schlüssel und Trace-ID je Zug. Startseite und README mit neuem Stand; Testzahlen in der Architektur-Doku | `docs/architektur-grafiken/` (Quellen, HTML, PNG, README, `index.html`), `docs/architektur.md` |
| 2 | Service-Steckbrief für die Übergabe | Steckbrief nach der Vorlage „Technischer Service-Steckbrief“ (Owner T4 – Jan Schachtschabel, Jira GEN-329, empfohlene LLM-Route); Ansprechperson in der Übergabe-Doku eingetragen | `docs/steckbrief-uebergabe.md`, `docs/uebergabe-betrieb.md` |
| 3 | Diese Notiz | | `docs/aenderungen/` |

Nach dem Merge veröffentlicht GitHub Pages die neuen Grafiken (Workflow `pages`).
