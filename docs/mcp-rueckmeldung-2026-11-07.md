# Rückmeldung an das MCP-Team zum Stand S1–S7 (2026-11-07)

Geprüft am Quelltext (`wlo-mcp-server-sc`, nur gelesen) und am Live-Server
(`wlo-mcp.87.106.195.152.nip.io`, nur anonyme GETs auf `/health`, `/ready` und `/auth/status`, dazu
ein Widerruf mit einem erfundenen Block). Der Chatbot ist angepasst; was er nutzt, steht in
[`plans/2026-11-07-stabilitaet-mcp-anbindung.md`](plans/2026-11-07-stabilitaet-mcp-anbindung.md).

## Ergebnis

Der Bericht stimmt mit dem Quelltext überein. Geprüft wurden:

- S1: Budget nur für `tools/call`, Client-Schlüssel, 3 × Protokoll-Budget.
- S2: 429 als JSON-RPC `-32029` mit Wartezeit, `upstream_busy` mit `retryAfter`.
- S3: Replay mit `replayed`, `inProgress` und `requiresNewPreview`; nach einem Abbruch `outcomeOpen`.
- S4: `/auth/status` mit `expiresAt`, 401 vor dem Zwischenspeicher.
- S5: `/ready`.
- R4: `TICKET_ALLOWED_ORIGINS`.
- R2: `POST /auth/revoke` mit Bearer.
- R1: Frist in der Allow-Liste; Ticket-Erneuerung nach Ablauf, Widget-Frist über `WIDGET_OAUTH_ORIGINS`.

Live:

- `/ready` antwortet 200 mit `upstream: "ok"`.
- `/auth/status` antwortet anonym `esguest`.
- Der Widerruf mit einem unbrauchbaren Block antwortet 200 (`revoked: false`).

**Keine Befunde, die den Betrieb stören.** Vier kleine Punkte und zwei Anregungen, keiner davon dringend:

## Befunde

1. **Die 429 der öffentlichen `/auth*`-Fläche weicht von S2 ab** (niedrig).
   - Stelle: `src/rest/auth-pages.ts`, Adress-Budget vor `/auth/ticket`, `/auth/issue` und `/auth/revoke`.
   - Die Antwort dort sendet fest `Retry-After: 60` und einen Freitext ohne `code`.
   - Die übrigen 429 gehen über `rest/rate-limited.ts`: Rest des Fensters, `{error, code, retryAfter}`.
   - Für den Chatbot unkritisch: Er liest beim Widerruf nur „nicht 200“.
   - Ein Programm, das auf `code` verzweigt, sieht hier aber keinen.
   - Vorschlag: auch hier `refuseRateLimited(…, 'rest')`.
2. **`/auth/status` trennt „abgelehnt“ und „nicht erreicht“ nicht** (niedrig).
   - Bei `authenticated: false` mit `authority: null` lässt sich nicht unterscheiden, ob das Repository die
     Anmeldung abwies oder nicht antwortete. Euer Kommentar in `rest/auth-status.ts` sagt das selbst.
   - Der Chatbot wertet das deshalb als „nicht prüfbar“ (Gnadenfrist) und nicht als „abgelehnt“. Sonst verlöre
     bei jedem Repository-Ausfall jede Person ihre Anmeldung.
   - Folge: Wurde das Passwort einer Person geändert, bietet der Chatbot erst nach dem ersten Werkzeug-Fehler
     (`login_rejected`) die neue Anmeldung an.
   - Vorschlag: ein Feld wie `upstream: "unreachable"` (die Bereitschaftsprobe kennt es), dann ließe sich beides
     trennen.
3. **Ein Abmelden nach Ticket-Tausch hält nur bis zum nächsten Tausch** (Hinweis, kein Fehler; so in R2 gewollt).
   - Die Kennung eines Ticket-Blocks ist der Streuwert des Tickets.
   - Nach `POST /auth/revoke` legt der nächste Tausch desselben, noch gültigen Tickets den Eintrag neu an.
   - Im selben Tab tauscht das Widget nach „Abmelden“ nicht mehr von selbst. Ein neuer Tab auf derselben
     edu-sharing-Seite meldet die Person aber wieder an, weil sie dort ja angemeldet ist.
   - Bitte so in `AUTH.md` festhalten, damit es niemand für eine Lücke hält.

4. **Fehler nach der Einlösung sagen nicht, ob schon etwas geschrieben wurde** (mittel, für den Chatbot schon
   abgefangen).
   - `keySpent` (`tools/curation-replay.ts`) setzt `requiresNewPreview: true` an **jeden** Fehler nach der
     Einlösung.
   - Das betrifft auch `not_visible` und `unverified` („angenommen, aber nicht nachweisbar“) sowie
     `upstream_busy` in einem Vorgang aus mehreren Schritten.
   - `outcomeOpen` steht nur am Abbruch (`upstream_error`) und an `timeout`.
   - Ein Client, der `requiresNewPreview` als „nichts geschehen, neu vorlegen“ liest, legt eine Dublette an.
     Genau das hatte unser erster Stand getan; das Review fand es, behoben ist es.
   - Der Chatbot legt jetzt nur bei `confirm_*`/`plan_*` neu vor oder wenn `outcomeOpen: false` dasteht.
     `not_visible`, `unverified` und `upstream_busy` nach der Einlösung behandelt er als „bitte nachsehen“.
   - Vorschlag: An jeden Fehler nach der Einlösung ausdrücklich `outcomeOpen: true|false`, und in der
     Codes-Tabelle von `MCP-REFERENZ.md` sagen, dass `requiresNewPreview` nichts darüber aussagt, ob
     geschrieben wurde.

## Anregungen

- **Widerruf und Ticket-Tausch über den Client-Schlüssel zählen** (euer „eigenes Paket“): Heute gehen alle
  Abmeldungen des Chatbots über das Adress-Budget (30/min). Für 30 Personen reicht das; bei größeren Einbettungen
  nicht mehr.
- **`Retry-After` auch bei `too_many_logins` auf `/auth/status`** ist da (bis 600 s). Der Chatbot wertete das als
  „nicht prüfbar“ und fragte im nächsten Zug wieder (nicht erst nach 30 s, wie hier zuerst stand). Falls ihr einen
  kürzeren Wert für diesen Fall vorseht, gern melden.

## Eure Antwort (2026-11-07) und was wir daraus gemacht haben

Stand eures Klons, noch nicht hochgeladen. Live antwortet `/auth/status` noch ohne `upstream`.

| Punkt | Eure Antwort bzw. euer Stand | Folge im Chatbot |
|---|---|---|
| Befund 1 (429 an `/auth*`) | **behoben**: `refuseRateLimited(…, 'rest')` mit Restzeit und `code` | nichts nötig |
| Befund 2 (`authority: null`) | **behoben**: neues Feld `upstream: "ok" \| "unreachable"` an `/auth/status` und `wlo_auth_status` | eingebaut, siehe unten |
| Befund 3 (Abmelden nach Ticket-Tausch) | **festgehalten** in `AUTH.md` (R2, „by design, not a gap“) | nichts nötig |
| Befund 4 (Fehler nach der Einlösung) | **noch offen**: `keySpent` unverändert; `MCP-REFERENZ.md` empfiehlt nach jedem Fehler mit `requiresNewPreview` eine neue Vorschau | der Chatbot ist abgesichert, siehe unten |
| Anregung 1 (Abmelden über den Client-Schlüssel) | eigenes Paket, nicht umgesetzt; betrifft nur `/auth/revoke`, der Ticket-Tausch zählt je Person im Browser | einverstanden; 30/min reichen heute |
| Anregung 2 (kürzeres `Retry-After` bei `too_many_logins`) | nicht vorgesehen. Die Sperre greift erst bei mehr als 10 Passwörtern je Block-Kennung in 10 min; wer früher fragt, bekommt wieder 429 und verbraucht Budget | **übernommen**, siehe unten |

**Eingebaut im Chatbot:**

- **`upstream` (Befund 2).** `authenticated: false` mit `upstream: "ok"` ist jetzt eine Ablehnung, auch bei
  `authority: null`. Die Person bekommt die Anmeldung gleich angeboten, nicht erst nach dem ersten
  Werkzeug-Fehler. `upstream: "unreachable"` heißt „nicht prüfbar“ (Gnadenfrist). Ohne das Feld (Stand live)
  bleibt die bisherige Regel: `authority: null` = nicht prüfbar.
- **`Retry-After` an `/auth/status` (Anregung 2).** Nach einer 429 fragt der Chatbot erst nach der genannten
  Wartezeit wieder (höchstens 600 s, ohne Angabe 60 s): bei `too_many_logins` für diesen Block, bei
  `rate_limited` für alle. Bis dahin gilt „nicht prüfbar“; eine
  Person mit Bestätigung aus den letzten 30 min bleibt angemeldet.

**Zu Befund 4 bitte noch einmal ansehen.** Euer Text in `MCP-REFERENZ.md` lautet sinngemäß: Nach der Einlösung
trägt jeder Fehler `requiresNewPreview`; „für einen neuen Versuch ohne `confirmToken` aufrufen und die neue
Vorschau bestätigen“.

- Für `not_visible` und `unverified` ist das gefährlich. Der Server hat die Änderung angenommen, sie ist nur
  nicht nachweisbar. Eine neue Vorschau mit Bestätigung kann dann eine Dublette erzeugen, etwa eine zweite
  Aufnahme oder ein zweiter Datensatz.
- Ebenso `upstream_busy` in einem Vorgang aus mehreren Schritten, wenn ein Teil schon geschrieben ist.
- Der Chatbot legt deshalb nur bei `confirm_*`/`plan_*` oder ausdrücklichem `outcomeOpen: false` neu vor.
- Bitte zweierlei:
  - In der Referenz ergänzen: `requiresNewPreview` sagt nichts darüber, ob geschrieben wurde; bei `not_visible`,
    `unverified` und `outcomeOpen: true` erst nachsehen.
  - Am besten an jeden Fehler nach der Einlösung ausdrücklich `outcomeOpen: true|false`.

## Eure zweite Antwort (2026-11-07, Commit `9093a5d`) und was wir daraus gemacht haben

Alle vier Befunde sind bei euch behoben und auf GitHub; live erst nach dem nächsten Ausrollen. Am Klon geprüft:

- `keySpent` setzt an jeden Fehler nach der Einlösung `outcomeOpen`, ohne Angabe `true`.
- Ein Fehler ohne Code heißt `unverified`.
- `not_stored` trägt `outcomeOpen: false` nur, wenn nichts ankam.
- `upstream_unreachable` (503) gibt es an den Anmeldeflächen und an `/api/uploads`.

Damit ist Befund 4 erledigt. Unsere Regel bleibt: neu vorlegen nur bei `confirm_*`/`plan_*` oder `outcomeOpen: false`.

**Angepasst im Chatbot:**

- **`exists` mit `outcomeOpen: false`** wird **nicht** neu vorgelegt. Eine neue Vorschau träfe dieselbe Dublette.
  Die Antwort nennt stattdessen den vorhandenen Datensatz, wie bisher.
- **`upstream_busy` nach der Einlösung mit `outcomeOpen: false`** gilt als Ablehnung ohne Wirkung und wird neu
  vorgelegt. Ohne die Angabe oder mit `true` heißt es weiter „bitte nachsehen“.
- **`not_stored`** folgt der Regel: `false` → neu vorlegen, `true` → nachsehen.
- **`/api/uploads` 503 `upstream_unreachable`** → „nicht erreichbar, gleich noch einmal“, nicht mehr „Fehler“.
  `too_many_logins` liest der Chatbot jetzt aus `code` oder `error`.
- **Ticket-Tausch im Widget, 503 `upstream_unreachable`:** Das Widget behält das Ticket und versucht es nach
  `retryAfter` einmal erneut, höchstens nach 15 s. Ein vorhandener Block bleibt. Danach meldet es „nicht zu fragen“
  statt „abgelehnt“.
- Nichts nötig für: `/auth/status` mit 60 s Zwischenspeicher bei Ablehnung, die 429-Form an `/oauth/*` (das Widget
  meldet dort nur „hat nicht geklappt“), `POST /oauth/authorize` (eure eigene Seite) und `/auth/revoke-all`
  (nutzt der Chatbot nicht).

**Was ihr noch von uns braucht**, unverändert:

- die beiden Herkunftslisten vom Betrieb;
- den Client-Schlüssel, außerhalb jedes Chats;
- den Lasttest mit 30 Personen;
- die Zeiten aus `mcp_aufruf`.

**Zur Frage, ob ihr hochladen sollt:** Das entscheidet der Nutzer. Für den Chatbot spricht nichts dagegen: Er
arbeitet mit dem Stand live und mit eurem neuen Stand. Mit `upstream` wird die Anmeldeprüfung genauer.

## Was wir euch liefern (eure Liste „Was wir von euch brauchen“)

- **`TICKET_ALLOWED_ORIGINS`** = die Herkünfte der edu-sharing-/WLO-Seiten, die das Widget mit `ticket`
  einbetten. Das ist dieselbe Liste wie `CORS_ORIGINS` am Chatbot. Die Werte für Staging und Produktion liefert
  der Betrieb (Hinweis in `docs/uebergabe-betrieb.md` §11).
- **`WIDGET_OAUTH_ORIGINS`** = die **öffentliche Herkunft des Chatbot-Backends**, nicht die der Gastseite. Das
  Widget leitet nach der OAuth-Anmeldung auf `<Backend>/widget/oauth-callback.html` zurück
  (`frontend/projects/ui/src/session/sign-in-flow.ts`, `callbackUrl`). Sitzt das Backend auf derselben Herkunft
  wie die Gastseite, ist es diese.
- **Client-Schlüssel:** Der Nutzer erzeugt ihn (`openssl rand -hex 32`) und tauscht ihn außerhalb jedes Chats
  mit euch aus (`boerdi:360:<schlüssel>`). Am Chatbot steht er in `MCP_CLIENT_KEY`. Bis dahin hält der Wächter
  des Chatbots das Adress-Budget ein (`MCP_BUDGET_RPM` 280).
- **Lasttest 30 Personen (S1)** und **Zeitpunkte langsamer Aufrufe (S6)**: Den Lasttest startet der Nutzer. Die
  Zeitpunkte kommen aus den Zeilen `mcp_aufruf` mit `dauer_ms` im Log des Chatbots.
