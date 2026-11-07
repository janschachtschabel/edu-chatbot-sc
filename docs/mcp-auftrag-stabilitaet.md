# Auftrag an das MCP-Team: Anbindung des Chatbots stabiler, Anmeldung verlässlicher

Stand 2026-11-07 · vom Chatbot-Team (BOERDi) · Gegenstück: der Chatbot-Plan
[`plans/2026-11-07-stabilitaet-mcp-anbindung.md`](plans/2026-11-07-stabilitaet-mcp-anbindung.md). Beide Aufträge
sind aufeinander abgestimmt: der Chatbot kann sofort beginnen und braucht eure Punkte erst für die zweite Stufe.

Grundlage ist der Code beider Seiten (MCP-Stand 07.11., Klon `wlo-mcp-server-sc`) — keine Messung am Live-Server.
Die Live-Werte von `RATE_LIMIT_RPM` und `TRUST_PROXY` kennen wir nicht (Frage F1).

> **Stand 2026-11-07, abends: umgesetzt und ausgerollt.** Das MCP-Team hat S1–S6 und S7 (R4, R2, R1 nach unserer
> Empfehlung) geliefert; live `RATE_LIMIT_RPM` 300. Unsere Prüfung am Quelltext und am Live-Server samt drei
> kleinen Befunden: [`mcp-rueckmeldung-2026-11-07.md`](mcp-rueckmeldung-2026-11-07.md). Der Chatbot nutzt alles
> (Plan, Abschnitt „Umsetzung“). Der Text unten ist der Auftrag, wie er ging.

## 1. Was wir gefunden haben

| # | Befund | Beleg |
|---|---|---|
| B1 | **Ein Werkzeugaufruf kostet drei POSTs.** Der Server ist zustandslos (`sessionIdGenerator: undefined`), das Python-SDK schickt trotzdem je Sitzung `initialize`, `notifications/initialized` und `tools/call`. Der Chatbot öffnet heute je Aufruf eine Sitzung. | `mcp-transport.ts`; SDK `streamable_http.py` |
| B2 | **120 Anfragen je Minute und Adresse für alle Personen des Chatbots zusammen.** Der Chatbot ist für alle seine Nutzer EINE Adresse; mit B1 sind das rund **40 Werkzeugaufrufe pro Minute insgesamt**. Ein Agent-Zug braucht 3–8, dazu Vorabrufe und die Anmeldeprüfung. Ab wenigen gleichzeitigen Personen kommt 429. | `http.ts` `RATE_LIMIT_RPM=120`, `http-app.ts` Zähler vor jedem POST `/mcp` |
| B3 | **429 ist ein fester Block von 60 s** (`Retry-After: 60`), ohne Code im JSON-RPC-Format — der Chatbot hält es für einen Netzfehler. | `http-app.ts` |
| B4 | **Ein bestätigter Schreibaufruf ist nicht wiederholbar.** Geht die Antwort verloren (Netz, Frist), meldet ein zweiter Versuch mit demselben Schlüssel `confirm_unknown`; der Chatbot muss die Person „in WLO nachsehen“ lassen. Für Pläne gibt es den Weg schon (`byConfirmKey`). | `services/write/confirm.ts` `consumeToken` |
| B5 | **`wlo_auth_status` ist ein volles MCP-Werkzeug** (drei POSTs) und nennt keine Ablaufzeit. Jeder Zug mit Anmeldung prüft damit (der Chatbot hält das Ergebnis 5 min). | `apps/tool-status.ts`; `mcp-und-anmeldung.md` §4 Wunsch 6 |
| B6 | **`/health` sagt nur „Prozess läuft“**, nicht, ob edu-sharing erreichbar ist. Ein Ausfall-Schalter im Chatbot hätte nichts Billiges zum Prüfen. | `http-app.ts` |
| B7 | **Erste Anfrage nach Ruhe: 22 s** (Lasttest 2026-10-17), danach 2–3 s. | `mcp-und-anmeldung.md` §6 |
| B8 | Offene Auth-Punkte aus `mcp-und-anmeldung.md` §3/§4: Block ohne Frist (R1), Abmelden widerruft nicht (R2), `/auth/ticket` für jede Herkunft (R4). | dort |

Bereits gut gelöst und von uns genutzt: Abuse-Grenze für Blöcke je `jti` statt je Adresse; Upload-Platz nicht am
Adress-Budget; `error.code` mit `outcomeOpen`; Pläne mit Fortsetzung über den Bestätigungsschlüssel.

## 2. Aufträge an das MCP-Team

Reihenfolge nach Wirkung. **S1–S3 sind die wichtigen**, S4–S6 runden ab, S7 ist die zweite Stufe der Anmeldung.

### S1 — Budget, das zur Bauart passt (B1, B2)

1. **Nur `tools/call` zählen** (oder `initialize`/`notifications/*` deutlich billiger) — die beiden anderen POSTs
   tun bei einem zustandslosen Server nichts, was das Upstream belastet. Der Kommentar in `http.ts` begründet das
   Limit mit dem Fan-out zu edu-sharing; das hat nur `tools/call`.
2. **Vertrauter Client mit eigenem Budget:** ein geheimer Kopf (Vorschlag `X-WLO-Client-Key`, Liste in der
   Umgebung `TRUSTED_CLIENT_KEYS`, je Schlüssel eigenes RPM) statt einer IP-Ausnahme — Adressen ändern sich, ein
   Schlüssel nicht. Ohne gültigen Schlüssel bleibt alles wie heute. **Für den Chatbot mindestens 360 Anfragen/min**:
   er selbst begrenzt sich auf 300 (`MCP_BUDGET_RPM`), die 20 % darüber sind Puffer für Uhrabweichung und Fenstergrenzen.
3. **`TRUST_PROXY` im Betrieb prüfen** — sonst teilen sich hinter dem Proxy alle Clients ein Budget (F1).

*Abnahme:* 30 parallele Chat-Personen (Lasttest im Studio) über 5 min ohne 429 am MCP; der Chatbot-Schlüssel hat
≥ 360/min; ein Client ohne Schlüssel wird weiter bei 120 gebremst.

### S2 — Überlast als Code, mit genauer Wartezeit (B3)

- 429 mit **verbleibenden Sekunden** im festen Fenster als `Retry-After` (nicht pauschal 60), Rumpf weiter JSON.
- Für Überlast **im** Werkzeug (edu-sharing antwortet 429/503): `structuredContent.error = {code: "upstream_busy",
  retryAfter: <s>}` statt `upstream_error` — so kann der Chatbot „WLO ist ausgelastet, gleich noch einmal“ sagen
  statt „hat nicht geklappt“.

*Abnahme:* Test je Fall; `retryAfter` ≤ Rest des Fensters.

### S3 — Bestätigte Schreibaufrufe sicher wiederholbar (B4)

- Der Server merkt sich für einen **eingelösten** Bestätigungsschlüssel das Ergebnis (Hash des Schlüssels →
  Antwort, 30 min, gebunden an Identität und Änderung wie heute). Wird **derselbe Schlüssel mit derselben Änderung**
  erneut vorgelegt, kommt **dasselbe Ergebnis** zurück (Kennzeichen `replayed: true`), keine zweite Ausführung und
  kein `confirm_unknown`. Läuft die erste Ausführung noch, antwortet er wie bei Plänen mit `inProgress`.
- Mit anderer Änderung bleibt es `confirm_mismatch` (wie heute).

*Abnahme:* Test „Antwort verloren → derselbe Aufruf → gleiches Ergebnis, ein Datensatz“; Test „parallel zweimal →
einmal geschrieben“.

### S4 — Anmeldestand günstig und mit Frist (B5)

- `GET /auth/status` (eine Anfrage, nicht am MCP-Budget, am Abuse-Limiter wie `/mcp`): `{mode, authenticated,
  authority, expiresAt?}` — derselbe Inhalt wie `wlo_auth_status`.
- `expiresAt`, sobald ein Block/Ticket eine Frist hat (heute: Ticket-Blöcke enden mit dem Ticket — bitte nennen, wenn
  bekannt).

*Abnahme:* 200 mit Block, 401 mit widerrufenem Block (wie `/mcp`), ohne Kopf `mode: anonymous`.

### S5 — Bereitschaft statt nur Lebenszeichen (B6)

- `GET /ready`: 200, wenn edu-sharing in den letzten 30 s erreichbar war (eigener, gecachter Probe-Aufruf), sonst 503
  mit `{upstream: "unreachable"|"slow"}`. Nicht am Budget.

### S6 — Kalter Pfad (B7)

- Prüfen, woher die 22 s kommen (TLS/Keep-Alive zu edu-sharing, Index-Warmup?). Vorschlag: Keep-Alive-Agent zum
  Upstream und ein Aufwärmaufruf beim Start.

### S7 — Anmeldung, zweite Stufe (B8): Entscheidungsvorlage mit Empfehlung

Ausgangslage aus Sicht des Chatbots (Stand 07.11.): Das Widget meldet sich per OAuth 2.1 **direkt aus dem Browser**
an (`/oauth/register`, `/oauth/authorize`, `/oauth/token`) bzw. tauscht auf edu-sharing-Seiten das Ticket **direkt
aus dem Browser** (`/auth/ticket`). Der Block liegt im `sessionStorage` **der einbettenden Seite**; jedes Skript dort
kann ihn lesen. Abmelden im Widget löscht ihn nur lokal. Euer `AUTH.md` §10 Regel 6 sagt: „Das Access-Token IST der
Block. Kein Wrapper, kein Refresh-Token, kein Ablauf.“

**Empfohlene Reihenfolge:** R4 → R2 → R1 (klein → mittel), jeweils nach S1–S4.

#### R1 — Frist für Blöcke

| | Option | Für | Gegen |
|---|---|---|---|
| **A (empfohlen)** | **Frist in der Allow-Liste, nicht im Token.** Der Eintrag bekommt beim Ausstellen ein `expiresAt`, je nach Weg: OAuth-Clients, deren `redirect_uri` auf einer konfigurierten Widget-Herkunft liegt (`SHORT_LIVED_CLIENT_ORIGINS`), und Ticket-Blöcke → `WIDGET_BLOCK_TTL` (Vorschlag **12 h absolut**); eingefügte Blöcke und KI-Host-Konnektoren wie heute ohne Frist. Abgelaufen = wie widerrufen → 401 mit dem Discovery-Hinweis. | Der gestohlene Block aus einer Gastseite verfällt. Das Token bleibt der Block — kein Wrapper, kein Refresh-Token, eine Allow-Liste für beide Wege. Geschrieben wird nur beim Ausstellen (wie heute), geprüft im Speicher. Abgelaufene Einträge lassen sich wegräumen. | Regel 6 ändert sich im Wortlaut („kein Ablauf **im Token**; die Gültigkeit samt Frist steht in der Allow-Liste“). Wer sich im Widget mit Passwort anmeldet, tut das alle 12 h neu (auf edu-sharing-Seiten automatisch über das Ticket). |
| B | Kurzlebige Access-Tokens mit Refresh-Token (OAuth-üblich) | Standard | Hebt Regel 6 auf (zweite Token-Art), Erneuerung in jedem Client inkl. KI-Hosts, Wettläufe zwischen mehreren Tabs. Der Nutzen gegenüber A ist klein: edu-sharing kennt kein Token, der Block trägt das Passwort so oder so. |
| C | Wie heute; Widget mit Anmeldung nur auf vertrauenswürdigen Seiten | kein Aufwand | Ein gestohlener Block gilt bis zum Widerruf. |

Der Chatbot liefert dazu: `expiresAt` aus `/auth/status` (S4) → Hinweis „Anmeldung läuft gleich ab“ und neue Anmeldung
**vor** dem Ablauf; ein abgelaufener Block wird wie ein abgewiesener behandelt (gibt es schon).

Ergänzend auf Chatbot-Seite (später, unabhängig von euch): den Block nicht mehr im Speicher der Gastseite halten,
sondern im Chatbot-Backend an die Sitzung binden — dann sieht ihn kein Skript der Gastseite mehr.

#### R2 — Abmelden widerruft

| | Option | Für | Gegen |
|---|---|---|---|
| **A (empfohlen)** | **Selbst-Widerruf durch Besitz:** `POST /auth/revoke` nimmt den Block auch als `Authorization: Bearer` (ohne Rumpf) und widerruft genau dessen `jti`. Weiter **ohne CORS** (Regel 4 bleibt); aufgerufen wird server-zu-server vom Chatbot-Backend beim „Abmelden“. Gleicher Abuse-Bucket wie `/mcp`. | Kein Passwort nötig, weil der Besitz des Blocks der Nachweis ist (stärker als heute: Kenntnis der Kennung reicht schon). Kein neues CORS-Loch. Ein Endpunkt, den es fast schon gibt. | — |
| B | CORS für `/auth/revoke` öffnen, das Widget widerruft selbst | kein Backend-Schritt | Bricht Regel 4 (`/auth*` ohne CORS). |
| C | Wie heute (nur `/auth/revoke-all` mit Passwort) | — | Abmelden im Chat beendet den Zugang nicht. |

Hinweis zum Ticket-Weg: der `jti` ist der Hash des Tickets. Nach einem Widerruf legt der nächste Tausch mit demselben
Ticket den Eintrag neu an. Das ist gewollt (die Person ist in edu-sharing ja noch angemeldet); das Widget tauscht
nach einem ausdrücklichen „Abmelden“ im selben Tab aber nicht von selbst neu.

#### R4 — Herkunftsliste für `/auth/ticket`

| | Option | Für | Gegen |
|---|---|---|---|
| **A (empfohlen)** | **`TICKET_ALLOWED_ORIGINS`** (exakte Herkünfte, Schema+Host+Port). Nur diese bekommen den CORS-Kopf; ein Browser-Aufruf von anderswo → 403 ohne CORS. Anfragen **ohne** `Origin` (server-zu-server) wie heute. Leer = heutiges Verhalten (`*`), damit nichts bricht; im Betrieb gesetzt auf die edu-sharing-/WLO-Domänen, auf denen das Widget mit Ticket läuft. | Klein, rückwärtsverträglich, schließt das „jede Seite darf tauschen“. | Die Liste muss mit den Einbettungen gepflegt werden (der Chatbot führt dieselbe Liste als `CORS_ORIGINS`). |
| B | Tausch nur noch über das Chatbot-Backend (server-zu-server, Client-Schlüssel aus S1), CORS ganz zu | am strengsten | Alle Tickets zählen dann auf die Adresse des Chatbots (`TICKET_CREDENTIAL_LIMIT` 200/10 min) — bräuchte einen Bucket je Client-Schlüssel; das Ticket läuft durch ein weiteres System. Später möglich. |

#### Unsere Empfehlung in einem Satz

R1-A (Frist in der Allow-Liste, 12 h für Widget- und Ticket-Blöcke), R2-A (Selbst-Widerruf per Bearer, server-zu-server),
R4-A (Herkunftsliste, leer = wie heute) — keine davon braucht einen Wrapper oder Refresh-Token, und Regel 6 ändert sich
nur in einem Satz.

## 3. Gemeinsamer Vertrag (bitte so oder mit Gegenvorschlag)

| Sache | MCP liefert | Chatbot macht daraus |
|---|---|---|
| Kopf `X-WLO-Client-Key` | eigenes Budget je Schlüssel, für den Chatbot ≥ 360/min (S1) | schickt ihn an jeden POST `/mcp` und `/auth/status`, nie an fremde Server; hält sich selbst an 300/min |
| HTTP 429 + `Retry-After: <s>` | Rest des Fensters (S2) | kein Sofort-Wiederholen; wartet höchstens bis zur Zugfrist, sonst Satz „ausgelastet“ |
| `error.code = "upstream_busy"`, `retryAfter` | Überlast im Werkzeug (S2) | wie 429, ein Versuch nach `retryAfter` wenn er in die Frist passt |
| derselbe `confirmToken` erneut | gleiches Ergebnis, `replayed: true` (S3) | genau eine Wiederholung nach Netzfehler/Frist; „bitte in WLO nachsehen“ entfällt |
| `GET /auth/status` | Anmeldestand + `expiresAt` (S4) | ersetzt `wlo_auth_status`; bietet vor Ablauf die Anmeldung neu an |
| `GET /ready` | 200 / 503 (S5) | Probe des Ausfall-Schalters |

## 4. Reihenfolge und Abhängigkeiten

- **Sofort, unabhängig voneinander:** S1 (MCP) und die Chatbot-Pakete CB-1…CB-5 (eine Sitzung je Zug, 429 sauber,
  Ausfall-Schalter, Anmeldung bei Störung, Budget-Wächter) — CB-1 senkt die Last schon ohne S1 auf etwa ein Drittel.
- **Danach:** S2/S3 (MCP) ↔ CB-6 (Codes und sichere Wiederholung im Chatbot).
- **Dann:** S1-Schlüssel, S4/S5 ↔ CB-7 (`X-WLO-Client-Key`, `/auth/status`, `/ready`).
- S6, S7 unabhängig.

## 5. Fragen an euch

- **F1** Welche Werte haben `RATE_LIMIT_RPM` und `TRUST_PROXY` live, und steht vor dem MCP ein weiterer Limiter
  (WAF, Proxy)?
- **F2** Beantwortet der zustandslose Server ein `tools/call` auch **ohne** vorheriges `initialize`? (Dann könnte der
  Chatbot je Aufruf mit einem POST auskommen; sonst nutzen wir eine Sitzung je Zug.)
- **F3** Hat edu-sharing selbst ein Limit, an das S1 stoßen würde (dann lieber Warteschlange im MCP als 429 am
  Upstream)?
- **F4** S3: lieber Ergebnis-Speicher im Prozess (wie Pläne, verloren beim Neustart) oder geteilt? Für uns genügt
  „im Prozess“, wenn ein Neustart `confirm_unknown` liefert wie heute.
