# Doku und Grafiken nach Paket N (2026-11-19)

Nach dem Merge von Paket N (PR #89, main `b7aad91`) geprüft, ob README, Doku und
Architekturgrafiken den Stand von N1–N4 zeigen. Nur Doku, kein Code.

## Was veraltet war

- `docs/ablaeufe.md` („Aufträge, die schreiben“): „eine eigene Freigabe-Box gibt es dort nicht“ —
  seit N4 falsch. `docs/b-api-betrieb.md` §5 und `docs/mcp-und-anmeldung.md` §1a beschrieben die
  Bestätigung der Vorschau noch im selben Zug wie die Rückfrage.
- `README.md`: Migration **0016** (Stand ist 0023), kein Hinweis auf Paket N, `B_API_KEY_MODE`
  ohne den Satz, dass `auto` auch ohne gesetzte Variable gilt.

## Was ergänzt ist

- `README.md`: Zeile „Nachbesserungen Themenbaum und Betrieb (Paket N)“ mit Plan und Notizen;
  Kestra-Zeile um die Freigabe-Box, Upload-Zeile um Vokabular und Zuordnung; „Betrieb in Kürze“
  mit Migration 0023, `auto` ohne Variable und Betriebsanzeige.
- `docs/ablaeufe.md`: Freigabe-Box (Ablauf, Knöpfe, Schlüssel nur im Server, Ablauf nach zehn
  Minuten, Stapel, kein Feld am Schritt, Simulation ohne Box); in beiden Themenbaum-Abläufen die
  Box nach der Rückfrage und die Zuordnung `inhalte`/`nicht_zugeordnet` beim Entwurf aus Dateien.
- `docs/architektur.md`: §5.6 Betriebsanzeige (N1), §5.8 Freigabe-Box (N4) im Bild und als Punkt,
  §5.9 Absatz „Was ein Entwurf aus den Teilen macht“ (N2/N3).
- `docs/ui-module.md`: Feld `freigabe` (`x-nur-system`) am Inhaltsrahmen, Tabellenzeile mit
  Fähigkeit `auftrag`, Zuordnung und Vokabular beim Dienst `strukturentwurf`.
- `frontend/projects/ui-module/src/ui-inhaltsrahmen/README.md`: Abschnitt Freigabe-Box.
- `docs/b-api-betrieb.md`, `docs/mcp-und-anmeldung.md`: Start erst nach „Freigeben“.

Jeder genannte Pfad und Name ist gegen den Staging-Stand geprüft (u. a.
`services/mcp/vokabular_labels.py`, `services/auftraege/mcp_vorschau.vorschau`,
`services/ablauf/auftrag_freigabe.vorlegen`, Vorgabe `auto` in `settings.b_api_key_mode`).

## Grafiken

Mit archify neu erzeugt, Belege auf `b7aad91` (main nach PR #89), voller Durchlauf
(`finalize --quality showcase`, Belegstand gegen den Klon) bestanden. Belegdateien unter
`.archify/doku-n-1911/`, keine unter `docs/`.

- **Datenstrom (`datenstrom-upload-kestra`):** Kette Stapel-Ablage → Vorschau (`wlo_start_flow`
  ohne Schlüssel) → **Freigabe-Box** (Freigeben · Abbrechen, Schlüssel nur im Server) →
  `wlo_start_flow` mit `confirmToken` → Repository-Proxy → Kestra. Die Bahn „Teile im Vorgang“
  steht jetzt unter dem Upload-Feld (keine Kreuzungen). Neue Karten „Freigabe-Box“ und „Themenbaum
  aus Inhalten“ (Zuordnung, Schwelle 0,36, `nicht_zugeordnet`, Vokabular) — nur interaktiv.
- **Architektur:** Karte „Kestra über den MCP“ mit Vorschau und Freigabe-Box; Karte „Betrieb“ mit
  der Betriebsanzeige (`/api/health` hinter dem Studio-Schlüssel, Statusleiste; offenes `/health`
  unverändert).
- **UI-Module:** Karte „Drei Wege zum Block“ nennt die Freigabe-Box als vom System gesetzten
  Inhaltsrahmen (Feld `freigabe`, `x-nur-system`). Felder des Strukturentwurfs zeigt die Grafik
  nicht.
- Grafiken-README (Quellstand `b7aad91`, Absatz „Stand Paket N“) und `index.html` nachgezogen.
  Software-Stack, Abläufe und Konfiguration je Modus bleiben: Paket N ändert dort nichts
  (`B_API_KEY_MODE` „auto: Authorization vom Proxy, sonst B_API_KEY“ stimmt weiter).

## Review (19.11.)

Unabhängiges Review: 2 MAJOR, 5 MINOR, 6 NIT, alle gegen den Code geprüft und behoben.

- MAJOR: Filter in der Box erst bei **mehr als** 20 Einträgen (`SEITE = 20`, `> SEITE`); das
  Aufrufbild in `architektur.md` §5.8 nannte nur `mcp_starter.starten`. Es zeigt jetzt beide Äste:
  `auftrag_freigabe.vorlegen` → `mcp_vorschau.vorschau` → Box, „Freigeben“ →
  `auftrag_freigabe_zug.starten` → `mcp_vorschau.bestaetigen`. `mcp_starter.starten` nur noch für
  spätere Teile eines Stapels.
- MINOR: „nur aus dem Vokabular“ gilt nur, wenn es erreichbar ist (sonst die bisherige Prüfung) —
  README, `ablaeufe.md`, `architektur.md`, `ui-module.md`, Datenstrom-Karte. Die Betriebsanzeige in
  `architektur.md` §5.6 steht jetzt hinter dem Absatz zu Paket 17 (der Verweis „unten“ stimmt
  wieder). Probe und Simulation zeigen keine Box (`ablaeufe.md`, „Probe“). `steckbrief-uebergabe.md`
  auf Migration 0023. Deploy-Hinweise zu Paket N in `uebergabe-betrieb.md` §15 und
  `offene-befunde-und-todo.md` §4.
- NIT: Halt an `wartet_freigabe` setzt der Treiber; `node_id`-Satz klarer; Abgleich am Entwurf in
  `strukturentwurf_vokabular.py`; die Box entsteht im Ablauf, nicht im Trichter; `x-nur-system` als
  Liste oder `true`; `aufteilen.hoechstens` (ab Werk 50) und „höchstens zehn Minuten“; „überschriebene
  Felder“ nur beim Metadaten-Flow.
