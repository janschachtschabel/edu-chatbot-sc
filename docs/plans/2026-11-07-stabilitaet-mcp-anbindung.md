# Plan: MCP-Anbindung stabiler, Anmeldung verlässlicher (Chatbot-Seite, 2026-11-07)

Status: **umgesetzt 2026-11-07** (Auftrag des Nutzers: „passe den Chatbot passend dazu an“, nachdem das MCP-Team
S1–S7 ausgerollt hatte; Abschnitt „Umsetzung“ am Ende). Gegenstück für das MCP-Team:
[`../mcp-auftrag-stabilitaet.md`](../mcp-auftrag-stabilitaet.md) — dort stehen die Befunde B1–B8 mit Belegen und der
gemeinsame Vertrag (§3). Dieser Plan nennt dieselben Punkte aus Chatbot-Sicht und ist so geschnitten, dass
**CB-1 … CB-5 sofort und ohne MCP-Änderung** gehen; CB-6/CB-7 nutzen, was das MCP-Team mit S1–S5 liefert.

## Ziel

- Mehrere Personen gleichzeitig ohne 429 am MCP (heute: ~40 Werkzeugaufrufe/min für alle zusammen).
- Eine kurze Störung am MCP kostet die angemeldete Person weder ihr Schreibrecht noch eine offene Abnahme.
- Ein MCP-Ausfall macht den Chat nicht für jeden Zug 30–60 s langsam, sondern sagt es sofort.
- Kein bestätigter Schreibvorgang endet mehr in „bitte in WLO nachsehen“, wenn nur die Antwort verloren ging (mit S3).

Leitregeln (unverändert): Schreiben nur mit Schreibrecht und ausdrücklichem Ja; ein bestätigter Schreibaufruf wird
nur wiederholt, wenn der Server die Wiederholung zusagt (S3); keine neuen Abhängigkeiten; Block nur an den primären
Server.

## Pakete

### CB-1 — Eine MCP-Sitzung je Zug (sofort; wirkt wie ⅓ der Last)

- `services/mcp/transport.py`: Sitzungen in einem Zug-Speicher (ContextVar, gebunden in `graph/build.begin_turn`,
  geschlossen am Zugende), Schlüssel `(Server-Adresse, Fingerabdruck des Blocks)`. Der erste Aufruf öffnet und
  initialisiert, jeder weitere ist **ein** POST. Belegt (ein Aufruf läuft) → eine zweite Sitzung statt warten
  (Vorabrufe laufen parallel). Außerhalb eines Zugs (Studio-Abgleich, Hintergrund) wie heute.
- Fehler in einer wiederverwendeten Sitzung → sie fällt aus dem Speicher, der Aufruf geht über eine frische.
- Nebenbei: TCP/TLS werden innerhalb des Zugs wiederverwendet.
- *Tests:* Attrappe zählt POSTs (5 Aufrufe in einem Zug → 1 `initialize`); zwei Blöcke → zwei Sitzungen; Abbruch
  des Zugs schließt alles; parallel zwei Aufrufe → zwei Sitzungen, keine Verschränkung.

### CB-2 — Überlast sauber behandeln (sofort)

- `transport.py`: HTTP 429/503 → Art `busy` mit `retry_after` (aus `Retry-After`, gedeckelt). `client.py`: `busy`
  wird **nicht** sofort wiederholt; passt `retry_after` in die Zugfrist (höchstens 5 s), ein Versuch danach, sonst
  Ende. `McpAntwort.art = "busy"`.
- Texte (DE/EN): „WLO ist gerade ausgelastet — bitte gleich noch einmal.“ Im Muster- und Agent-Weg als Werkzeug-
  ergebnis, beim Einlösen eigener Satz (die Abnahme bleibt liegen, sie wurde nicht ausgeführt — 429 kommt vor dem
  Werkzeug).
- Metrik `mcp_aufruf{outcome="busy"}`; Log gedrosselt.
- *Tests:* 429 mit `Retry-After: 2` → ein verzögerter Versuch; `Retry-After: 60` → kein Versuch, Art `busy`;
  Einlösen bei 429 → Merkposten bleibt, Text.

### CB-3 — Ausfall-Schalter und kurze Verbindungsfrist (sofort)

- Verbindungsfrist 5 s (`MCP_CONNECT_TIMEOUT_S`) in der httpx-Fabrik; die Gesamtfrist (`MCP_CALL_TIMEOUT_S`, 60 s)
  bleibt.
- Schalter je Server: 3 Transport-/Fristfehler in 60 s → 30 s **offen** (Aufrufe scheitern sofort mit Art
  `transport`, Text „WLO ist gerade nicht erreichbar“), danach **ein** Probeaufruf (halb offen). Werte als
  Einstellungen (`MCP_BREAKER_FAILURES`, `MCP_BREAKER_OPEN_S`). Je Prozess — bei mehreren Repliken je Replik.
- Metrik `mcp_breaker_state`; Studio-Kosten/Status unverändert.
- *Tests:* drei Fehler → offen, kein Transport; nach Frist ein Probeaufruf; Erfolg schließt.

### CB-4 — Anmeldung bei Störung behalten (sofort)

- `services/mcp/anmeldung.py`: drei Ausgänge statt zwei — **Person**, **abgelehnt**, **unklar** (Frist, Netz,
  `busy`, Schalter offen).
  - *unklar* mit einer Bestätigung derselben Person in den letzten `AUTH_GRACE_S` (Vorgabe 1800 s = 30 min, Nutzer
    2026-11-07) → gilt weiter als
    Person (Kennung wie zuletzt), Log „Anmeldung nicht prüfbar — letzte Bestätigung gilt“.
  - *unklar* ohne frühere Bestätigung → wie heute anonym, aber **nicht** 30 s gemerkt (nächster Zug fragt wieder).
  - *abgelehnt* → wie heute (Block weg, Widget bietet Anmeldung an).
- `services/write_approval.py`: verweigert das Einlösen nur wegen *unklar* (kein Schreibrecht, Block nicht
  abgelehnt) → Merkposten **bleibt**, Text „Deine Anmeldung ließ sich gerade nicht prüfen — bitte gleich noch einmal
  ‚ja‘“, Chip. Heute geht die Abnahme dabei verloren.
- *Tests:* Störung nach Bestätigung → Schreibrecht bleibt; Störung ohne Bestätigung → anonym, nächster Zug fragt;
  Ablehnung → wie heute; Einlösen bei *unklar* → Merkposten bleibt.

### CB-5 — Budget-Wächter im Prozess (sofort, mit Werten aus F1)

- Ein Zähler je Server über die POSTs der letzten 60 s (`MCP_BUDGET_RPM`, Vorgabe **300**, Nutzer 2026-11-07) und
  höchstens `MCP_MAX_CONCURRENCY` (Vorgabe 8) gleichzeitige Aufrufe. Ist das Budget erschöpft, wartet ein Aufruf bis
  zur Zugfrist und endet sonst als `busy` (CB-2) — der Chatbot läuft nicht selbst in das 429.
- **Bedingung:** 300 setzt S1 voraus — der MCP muss dem Chatbot mindestens **360 Anfragen/min** zugestehen (20 %
  Puffer). Bis das live ist, gilt das Limit des Servers (Vorgabe 120); dann `MCP_BUDGET_RPM` im Betrieb auf 100
  setzen (Hinweis in `uebergabe-betrieb.md`), sonst wartet der Wächter nicht, bevor der Server ablehnt. Beim Start
  meldet der Chatbot den Wert einmal im Log.
- *Tests:* Zähler, Warten, Ende als `busy`; Studio-Lasttest-Szenario „30 Personen“ (startet der Nutzer).

### CB-6 — Nutzt S2/S3 (nach dem MCP)

- `error.code = "upstream_busy"` → wie `busy` (CB-2).
- **Sichere Wiederholung bestätigter Schreibaufrufe:** meldet der Server Unterstützung (Version oder ein
  `replayed`-Feld in der ersten Antwort, zu klären in F2/F4), wiederholt `client.py` einen bestätigten Aufruf nach
  Netzfehler/Frist **genau einmal** mit demselben Schlüssel; `write_approval` meldet dann das echte Ergebnis statt
  „bitte in WLO nachsehen“. Ohne Zusage bleibt es wie heute (offener Befund 1.2 bleibt die Regel).
- *Tests:* verlorene Antwort → Wiederholung → `replayed` → Erfolgstext; ohne Zusage keine Wiederholung.

### CB-7 — Nutzt S1/S4/S5 (nach dem MCP)

- Kopf `X-WLO-Client-Key` (Geheimnis `MCP_CLIENT_KEY`, nur an den primären Server, nie ins Log).
- Anmeldeprüfung über `GET /auth/status` (eine Anfrage) mit Rückfall auf `wlo_auth_status`; `expiresAt` → kurz vor
  Ablauf bietet das Widget die Anmeldung neu an (Signal wie bei `abgelehnt`, ohne den Block zu verwerfen).
- `GET /ready` als Probe des Ausfall-Schalters (CB-3).

### CB-9 — Gegenstück zu S7 (Anmeldung, zweite Stufe; nach Entscheid des MCP-Teams)

Empfehlung an das MCP-Team: R1-A, R2-A, R4-A (Begründung im Auftrag, S7). Dazu im Chatbot:

- **R1:** `expiresAt` aus `/auth/status` (CB-7) → das Widget bietet die Anmeldung kurz vor Ablauf neu an (Signal wie
  bei `abgelehnt`, Block bleibt bis zum Ablauf); ein abgelaufener Block wird wie ein abgewiesener behandelt (gibt es
  schon). Eine offene Abnahme überlebt die Neu-Anmeldung derselben Person (Bindung an die Kennung, nicht an den Block).
- **R2:** „Abmelden“ im Widget ruft `POST /api/auth/abmelden` am Backend (Block im Kopf wie bei jedem Zug); das
  Backend widerruft server-zu-server am MCP (`/auth/revoke` mit Bearer), dann löscht das Widget den Block. Auf dem
  Ticket-Weg tauscht das Widget danach im selben Tab nicht von selbst neu.
- **R4:** Betriebs-Hinweis: `TICKET_ALLOWED_ORIGINS` am MCP = `CORS_ORIGINS` am Chatbot (Abschnitt in
  `uebergabe-betrieb.md`); das Studio zeigt die Chatbot-Liste, damit der Abgleich sichtbar ist.
- **Später (unabhängig):** den Block nicht mehr im `sessionStorage` der Gastseite, sondern im Backend an die Sitzung
  binden — schließt R1 auf Chatbot-Seite.

### CB-8 — Doku, Studio, Betrieb (mit jedem Paket)

- `docs/uebergabe-betrieb.md` (neue Einstellungen, Geheimnis `MCP_CLIENT_KEY`), `deploy/README.md`,
  Studio-Infotafel „Wissensquellen“ (Überlast, Ausfall-Schalter), `docs/mcp-und-anmeldung.md` §5.
- Änderungsnotiz je Paket unter `docs/aenderungen/`, Review je Paket.

## Abstimmung mit dem MCP-Auftrag

| MCP (S) | Chatbot (CB) | Wirkung zusammen |
|---|---|---|
| — | CB-1 | ⅓ der POSTs, sofort |
| S1 Budget je `tools/call` / Client-Schlüssel | CB-5, CB-7 | genug Luft für viele Personen; der Chatbot bleibt unter dem Budget |
| S2 `Retry-After` genau, `upstream_busy` | CB-2, CB-6 | ehrliche Wartezeit statt Fehler |
| S3 Wiederholung eingelöster Schlüssel | CB-6 | kein „bitte nachsehen“ mehr nach verlorener Antwort |
| S4 `/auth/status` + `expiresAt` | CB-4, CB-7 | billige Prüfung, rechtzeitige Neu-Anmeldung |
| S5 `/ready` | CB-3, CB-7 | Ausfall-Schalter mit billiger Probe |
| S6 kalter Pfad | — | keine 22-s-Ausreißer |
| S7 Auth zweite Stufe (Empfehlung R1-A, R2-A, R4-A) | CB-9 | Block verfällt (12 h), Abmelden widerruft, Tausch nur von bekannten Seiten |

## Reihenfolge

1. CB-1, CB-2 (eine Runde, Transport) → Review → Suite.
2. CB-4 (Anmeldung) → Review.
3. CB-3, CB-5 (Schalter, Budget) → Review; Lasttest durch den Nutzer.
4. Nach Antwort des MCP-Teams: CB-6, CB-7 → Review.

## Abnahme gesamt

- Lasttest 30 Personen, 5 min: 0 × 429 am MCP (mit S1 ≥ 360/min und `MCP_BUDGET_RPM` 300), ohne S1 (Budget 100)
  keine Sofort-Wiederholungen und ehrliche Texte.
- Gestörte Anmeldeprüfung (Attrappe, Frist) nach Bestätigung: Schreibwerkzeuge bleiben, Abnahme bleibt.
- MCP nicht erreichbar: erster Zug ≤ 10 s mit Text, folgende Züge sofort, bis der Probeaufruf gelingt.

## Umsetzung (2026-11-07)

Gegen den ausgerollten MCP-Stand (S1–S7) geprüft; Änderungsnotiz
[`../aenderungen/2026-11-07-stabilitaet-mcp-anbindung.md`](../aenderungen/2026-11-07-stabilitaet-mcp-anbindung.md).

- **CB-1 entfällt.** S1 zählt nur `tools/call`, das Protokoll-Budget ist das Dreifache — genau eine Sitzung je
  Aufruf. Eine Sitzung je Zug brächte nur noch TCP/TLS-Wiederverwendung. Das ist kein Grund für geteilten
  Sitzungszustand.
- **CB-2** wie geplant (`busy` aus 429/503, `upstream_busy`; eine kurze `Retry-After` bis
  `MCP_BUSY_RETRY_MAX_S` 5 s wird abgewartet).
  - Beim Einlösen bleibt die Abnahme liegen (`write.busy`), ein Plan ebenso (`write.planBusy`).
- **CB-3:**
  - Die Schalterwerte sind einstellbar, Vorgabe wie vorgeschlagen 3 Fehler / 60 s, 30 s offen. Die Werte
    hatte der Nutzer offen gelassen.
  - Die Probe ist `GET /ready`.
  - Der Schalter zählt nur Fehler ohne Antwort (und 503), nie 429 oder Ablehnungen.
- **CB-4** wie geplant (`AUTH_GRACE_S` 1800). Dazu: `authority: null` gilt als nicht prüfbar (Rückmeldung
  Befund 2), und eine Bestätigung gilt nie über `expiresAt` hinaus.
- **CB-5:** Budget-Wächter ja (`MCP_BUDGET_RPM` 300; ohne Client-Schlüssel 280, der Server gesteht der
  Adresse live 300 zu). Die Gleichzeitigkeitsgrenze `MCP_MAX_CONCURRENCY` **entfällt**: Der Server begrenzt
  Aufrufe je Minute, nicht gleichzeitige, und eine Warteschlange hätte nur Züge gebremst.
- **CB-6:**
  - Ein bestätigter Schreibaufruf ohne Antwort holt seine Antwort mit demselben Schlüssel nach.
  - `inProgress` wird bis zu 4 × 2,5 s abgewartet, alles in höchstens 20 s.
  - `confirm_*`, `login_*` oder Fehler ohne Code lassen den Ausgang offen. Pläne nehmen nicht teil.
  - Neu aus S3: `outcomeOpen: true` heißt bei jedem Code „Ausgang offen“ (vorher nur bei `timeout`).
  - `requiresNewPreview` allein legt **nicht** neu vor (Review, Befund 1). Neu vorgelegt wird nur bei
    `confirm_*`/`plan_*` oder ausdrücklichem `outcomeOpen: false`.
  - `upstream_busy` nach der Einlösung gilt als „Ausgang offen“.
  - Das Nachholen der Antwort geht am Ausfall-Schalter vorbei (Befund 3).
- **CB-7:** Client-Schlüssel (`MCP_CLIENT_KEY`) nur an den primären Server, auch an `/auth/status` und
  `/auth/revoke`. Die Anmeldeprüfung läuft über `GET /auth/status` mit Rückfall auf das Werkzeug.
- **CB-9:**
  - R1: `auth_expires_at` an der Antwort. Das Widget tauscht ein Ticket nach dem Ablauf neu, nach einer
    Abweisung einmal je Ticket still; ohne Ticket weist es zehn Minuten vorher mit Anmelde-Chip hin.
  - R2: `POST /api/auth/abmelden`. Nach dem Abmelden tauscht das Widget im selben Tab kein Ticket mehr.
  - R4: Betriebshinweis in `uebergabe-betrieb.md` §11.
  - Das Studio zeigt die `CORS_ORIGINS` auf der Seite „Vorschau“ (Abschnitt „Einbettende Seiten“), dazu die
    kopierbaren Zeilen `TICKET_ALLOWED_ORIGINS` und `WIDGET_OAUTH_ORIGINS` für den MCP-Server (nachgetragen
    2026-11-07).
- **CB-8:** `uebergabe-betrieb.md`, `deploy/README.md`, `.env.example`, Helm, Compose, Studio-Infotafel
  „Wissensquellen“, `mcp-und-anmeldung.md`, `architektur.md`.

## Offene Fragen an den Nutzer

- Freigabe des Plans. Vorgaben entschieden (Nutzer 2026-11-07): `AUTH_GRACE_S` 30 min, `MCP_BUDGET_RPM` 300 (mit
  S1); offen: Schalter 3 Fehler/30 s.
- Soll CB-4 die Gnadenfrist auch für das Gastkonto (Block der Anlage) gelten lassen? Vorschlag: nein — dort prüft
  der Chatbot ohnehin nicht über `wlo_auth_status`.
