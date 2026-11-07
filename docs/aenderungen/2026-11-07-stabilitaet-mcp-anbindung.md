# Stabilität der MCP-Anbindung — Chatbot passend zum MCP-Stand S1–S7 (2026-11-07)

Auftrag des Nutzers: „Der MCP Entwickler ist fertig und hat den Code ausgerollt. Prüfe es bitte und passe den
Chatbot passend dazu an.“ Dazu: Fehler im MCP als Info für die Entwickler melden.

- Plan: [`../plans/2026-11-07-stabilitaet-mcp-anbindung.md`](../plans/2026-11-07-stabilitaet-mcp-anbindung.md),
  Abschnitt „Umsetzung“.
- Rückmeldung an das MCP-Team: [`../mcp-rueckmeldung-2026-11-07.md`](../mcp-rueckmeldung-2026-11-07.md)
  (vier kleine Befunde, zwei Anregungen, die Werte, die wir liefern).

## Backend

- **`services/mcp/schutz.py` (neu)**
  - Ausfall-Schalter je Server: 3 Fehler ohne Antwort in 60 s öffnen ihn für 30 s, dann eine Probe über
    `GET /ready`.
  - Budget-Wächter am primären Server: `MCP_BUDGET_RPM` 300, gleitendes Fenster, höchstens
    `MCP_BUDGET_WAIT_S` Warten.
  - `wurzel()` als eine Server-Wurzel für `/ready`, `/auth/*` und `/api/uploads`.
- **`services/mcp/transport.py`**
  - Neue Art `busy`: 429/503 mit `Retry-After`, Budget oder offener Schalter. Gemeinsam ist allen, dass nichts
    lief.
  - Schalter und Budget greifen vor dem Senden. `nachholen=True` geht am Schalter vorbei.
- **`services/mcp/http_fabrik.py`**: Kopf `X-WLO-Client-Key` (`MCP_CLIENT_KEY`) nur an den primären Server;
  Verbindungsfrist `MCP_CONNECT_TIMEOUT_S` 5 s für alle.
- **`services/mcp/wiederholung.py` (neu)**
  - Eine kurze Wartezeit des Servers (bis `MCP_BUSY_RETRY_MAX_S` 5 s) wird einmal abgewartet.
  - Ein bestätigter Schreibaufruf ohne Antwort holt seine Antwort mit demselben Schlüssel nach (`replayed`,
    `inProgress`).
  - `confirm_*`, `login_*` oder ein Fehler ohne Code lassen den Ausgang offen.
- **`services/mcp/client.py`**
  - `upstream_busy` → `busy`. `outcomeOpen: true` bei jedem Code → `timeout` (offen).
  - `upstream_busy` nach der Einlösung → `timeout`.
  - Der Text für das Modell bei „ausgelastet“ ist ein Satz statt eines Codes.
- **`services/mcp/anmelde_endpunkte.py` (neu)**: `GET /auth/status`, `POST /auth/revoke` per Bearer.
- **`services/mcp/anmeldung.py`**
  - Prüfung über `/auth/status`; ohne den Endpunkt (404) wie bisher `wlo_auth_status`.
  - Drei Ausgänge. *Nicht prüfbar* gilt mit Gnadenfrist `AUTH_GRACE_S` 1800 s weiter als Person, ohne sie
    anonym und nicht gemerkt. `authority: null` gilt als nicht prüfbar.
  - Eine Bestätigung gilt nie über `expiresAt` hinaus. `abgemeldet()` vermerkt den Block sofort als
    abgewiesen.
- **`services/write_approval.py`**
  - `busy` → die Abnahme bleibt liegen (`write.busy` + Chip).
  - Ungeprüfte Anmeldung ohne jede Bestätigung → die Abnahme bleibt liegen (`write.authUnclear`).
  - Neu vorgelegt wird nur bei `confirm_*`/`plan_*` oder `outcomeOpen: false`.
- **`services/plan_fortsetzen.py`**: `busy` → `write.planBusy`, der Plan bleibt.
- **`api/abmelden.py` (neu)**: `POST /api/auth/abmelden` widerruft den Block am MCP-Server.
  - Das Feld `ChatResponse.auth_expires_at` ist neu.
  - Beides steht in `docs/api/bewusste-vertragszusaetze.md`; OpenAPI ist neu erzeugt.
- **`main.py`**: Startzeile „MCP-Budget: … Client-Schlüssel gesetzt/nicht gesetzt“.
- **Metrik**: `boerdi_mcp_breaker_open`, dazu der Ausgang `busy` in `boerdi_mcp_calls_total`.
- **Einstellungen** in `settings.py`, `.env.example`, Helm (`MCP_CLIENT_KEY` als Secret) und Compose.

## Widget

- **`session/anmelde-frist.ts` (neu)**: Ein Ticket wird nach dem Ablauf neu getauscht. Ohne Ticket kommt zehn
  Minuten vorher ein Hinweis mit Anmelde-Chip.
- **`shell/chat-shell.component.ts`**
  - Abmelden widerruft über das Backend; der Text sagt ehrlich, ob es bestätigt ist.
  - Nach dem Abmelden tauscht das Widget im selben Tab kein Ticket mehr (`boerdi.mcp-signed-out`), auch nicht
    aus einem laufenden Tausch.
  - Nach einer Abweisung tauscht es das Ticket einmal still neu.
- **`stream/chat-api.ts`**: `abmelden(block)`.

## Studio und Doku

- Infotafel „Wissensquellen“: „Überlast und Ausfall“, „Anmeldung“.
- `uebergabe-betrieb.md` §11 (Einstellungen, Herkunftslisten am MCP-Server), `deploy/README.md`,
  `mcp-und-anmeldung.md` (R1, R2, R4, §5), `architektur.md`, `offene-befunde-und-todo.md` §1/§4,
  `mcp-auftrag-stabilitaet.md` (Status).

## Review (unabhängiger Prüfer, nur lesend) — 1 kritisch, 5 MINOR, 4 NIT

Alle am Quelltext nachgeprüft.

**Behoben:**

1. **KRITISCH.** Der Server setzt nach der Einlösung `requiresNewPreview` auch an `not_visible`/`unverified`.
   Der erste Stand legte dann neu vor und sagte „nichts geändert“; eine Dublette war möglich.
   - Jetzt wird nur bei `confirm_*`/`plan_*` oder `outcomeOpen: false` neu vorgelegt.
   - `upstream_busy` nach der Einlösung gilt als offen.
   - An das MCP-Team als Befund 4 gemeldet.
2. Eine ungeprüfte Anmeldung mit unklarer Zustimmung ließ den Zug weiterlaufen. Der Fingerabdruck-Weg hätte den
   Schlüssel ohne Ja finden können. Jetzt endet der Zug mit „liegen lassen“, und das nur, wenn wirklich keine
   Bestätigung vorliegt (nicht in der Gnadenfrist).
3. Der Schalter blockierte das Nachholen der Antwort. Jetzt geht es an ihm vorbei.
4. Nach dem Abmelden hielt der Speicher den Block bis zu 5 min für eine Person. Jetzt gilt er sofort als
   abgewiesen.
5. `/auth/*` und `/ready` hingen an der Herkunft statt an der Server-Wurzel. Ein Pfadpräfix ging verloren, und
   Block wie Schlüssel wären an einen anderen Dienst gegangen. Jetzt gilt eine Wurzel wie beim Upload.
6. Wer während eines Ticket-Tauschs abmeldete, war danach wieder angemeldet. Jetzt wird der Block verworfen.
7. Der Eintrag der Gnadenfrist konnte `expiresAt` um bis zu 30 s überleben. Jetzt ist er gedeckelt.
8. Nach einem Abmelden zeigte eine späte Abweisung „abgelaufen“. Ein gelungener Tausch nach Ablauf gibt die
   Erneuerung nach einer Abweisung wieder frei.

**Bewusst gelassen:**

- Die anonyme Weiterleitung beliebiger `wlo…`-Blöcke an `/auth/revoke` kostet nur das Adress-Budget von `/auth*`
  und ist gedrosselt.
- Ein 429 auf `notifications/initialized` verschluckt das SDK und meldet es als `transport`: sicher, aber er
  zählt für den Schalter.
- Die Sofort-Wiederholung lesender Aufrufe zählt zwei Fehler für den Schalter.

**Dazu aus der vollen Suite:** Der Log-Wächter fand `antwort.status_code` in zwei Log-Aufrufen. Es war nur der
Status, ist aber umgeformt.

## Nachtrag: Antwort des MCP-Teams (2026-11-07, abends)

- Befunde 1 und 2 sind im Klon des MCP-Teams behoben, Befund 3 steht in `AUTH.md`. Befund 4 ist noch offen.
  Die Anregungen sind beantwortet. Einzelheiten in der Rückmeldung, Abschnitt „Eure Antwort“.
- **`services/mcp/anmeldung.py`**: liest `upstream` von `/auth/status`. `ok` + `authenticated: false` ist eine
  Ablehnung, `unreachable` heißt nicht prüfbar; ohne das Feld gilt die bisherige Regel.
- **`services/mcp/anmeldung.py`, `anmelde_endpunkte.py`**: Nach einer 429 auf `/auth/status` hält der Chatbot je
  Block die `Retry-After` ein (höchstens 600 s, ohne Angabe 60 s) statt im nächsten Zug wieder zu fragen.
- Tests: `test_anmeldung_status.py` (`upstream`, Wartezeit, Gnadenfrist in der Pause).
- Review dieses Nachtrags, drei Befunde behoben:
  - `rate_limited` (Budget des Chatbots) pausiert die Prüfung jetzt für alle Blöcke, nicht nur für den einen;
    sonst holte sich jede weitere Person noch eine 429. `too_many_logins` bleibt je Block.
  - Ein eindeutig positiver Stand gilt vor `upstream: "unreachable"`.
  - Die Modul-Beschreibung von `anmeldung.py` nennt das neue Feld und die Pause.

## Nachtrag 2: zweite Antwort des MCP-Teams (Commit `9093a5d`)

- **`services/write_approval.py`**: `exists` mit `outcomeOpen: false` wird nicht neu vorgelegt (dieselbe
  Dublette); die Ablehnung nennt den vorhandenen Datensatz.
- **`services/mcp/client.py`**: `upstream_busy` nach der Einlösung mit `outcomeOpen: false` → `tool` (neu
  vorlegen), sonst weiter „offen“.
- **`services/ablage/mcp_ablage.py`**: Upload-Platz 503 → `nicht_erreichbar`; der Code einer Ablehnung kommt aus
  `code` oder `error`.
- **Widget `session/ticket-login.ts`**: 503 `upstream_unreachable` → nach `retryAfter` (höchstens 15 s) ein zweiter
  Versuch, sonst `unreachable`; das Ticket und ein vorhandener Block bleiben.
- Tests: `test_mcp_wiederholung_s3.py` (`upstream_busy`/`exists`/`not_stored` mit `outcomeOpen: false`),
  `test_ablage_mcp.py` (503, `code`), `ticket-login.spec.ts` (zweiter Versuch, Deckel).

## Nachtrag 3: Studio zeigt die einbettenden Seiten

- **`api/health.py`**: `/api/health` (hinter dem Studio-Schlüssel) trägt `einbettung`: `offen` (`CORS_ALLOW_ALL`),
  `herkuenfte` (die gepflegte `CORS_ORIGINS`) und `muster` (die Regel für Browser-Erweiterungen). Die Antwort ist
  untypisiert, der OpenAPI-Vertrag bleibt unverändert.
- **Studio, Seite „Vorschau“** (`views/einbettung-herkuenfte.component.*`): Abschnitt „Einbettende Seiten“.
  - Er zeigt die Liste, eine Warnung bei offener Einbettung und die kopierbaren Zeilen
    `TICKET_ALLOWED_ORIGINS=…` und `WIDGET_OAUTH_ORIGINS=<Herkunft des Backends>`.
  - Texte gibt es auf Deutsch und Englisch.
- **Review, behoben:**
  - Die kopierbare Zeile übernimmt nur, was der MCP-Server als Herkunft annimmt: `http(s)`, auf die Herkunft
    gekürzt, ohne Doppelte. Sonst hätte ein `*` oder ein Eintrag ohne `https://` dort gestanden, und steht am
    MCP-Server nur Unbrauchbares, darf keine Seite mehr tauschen. Was wegfällt, nennt ein Hinweis.
  - Doppelte Einträge brachen die Liste (`track` nach Wert); jetzt wird nach Position gezählt.
  - Neu ist der Stil `op-msg--warn`.
- Tests: `test_api_health.py`, `einbettung-herkuenfte.component.spec.ts` (7), `widget-preview.component.spec.ts`
  (Attrappe für `/api/health`).

## Tests

- Neu: `tests/test_mcp_schutz.py`, `tests/test_mcp_wiederholung_s3.py`, `tests/test_anmeldung_status.py`.
- Angepasst: `test_mcp_client` (bestätigter Aufruf holt nach), `test_mcp_anmeldung` (Rückfall,
  `authority: null`), `test_schemas`, `test_openapi_contract`.
- Widget: `session/anmelde-frist.spec.ts`, `stream/chat-api-abmelden.spec.ts`, Shell-Specs (Abmelden, Ticket nach
  Abweisung, Tausch während des Abmeldens).
- Studio: Infotafel.
