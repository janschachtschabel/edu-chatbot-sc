# MCP-Server und Anmeldung — Stand, Risiken, Wünsche an den Umbau

Stand 2026-10-15. Teil 1 des MCP-Feedbacks; Teil 2 (Werkzeuge, Ausgabeformat, Nutzung):
[`mcp-feedback-werkzeuge.md`](mcp-feedback-werkzeuge.md). Für das MCP-Team und für uns: Was der Chatbot (boerdi-chat) vom WLO-MCP-Server
(`wlo-mcp-server-sc`) für die Anmeldung nutzt, wo die Schwachstellen der heutigen Kette liegen und was
wir uns für den laufenden Umbau des MCP-Servers wünschen. Quellen: Kurzaudit
[`audits/2026-10-10-kurzaudit-auth-mcp-schreiben.md`](audits/2026-10-10-kurzaudit-auth-mcp-schreiben.md),
Paket 10 und 11 (`plans/`), `docs/AUTH.md` des MCP-Servers (gelesen am 2026-10-15).

**Einordnung (Nutzer 2026-10-15):** kurzfristig unkritisch, weil der MCP-Server umgebaut wird; langfristig
zu lösen. Dieses Dokument ist die Liste dafür.

## 1. Wie die Anmeldung heute läuft

| Schritt | Wo | Was passiert |
|---|---|---|
| Anmelden per Knopf | Widget → MCP-Server (OAuth 2.1, PKCE, öffentlicher Client) | Die Person meldet sich auf der Seite des MCP-Servers bei WLO an und bekommt einen **Zugangsblock** `wlo2.…` als `access_token`. |
| Anmelden per Ticket | Gastseite rendert `ticket` ins Widget → `POST /auth/ticket` | Das edu-sharing-Ticket wird gegen einen Block getauscht (`k:'ticket'`). |
| Aufbewahren | Widget, `sessionStorage` (`boerdi.mcp-access`) | Je Tab, stirbt mit dem Tab. Kein Cookie, kein `localStorage`. |
| Je Chat-Anfrage | Widget → Backend (Kopfzeile `WLO-Access-Block`) → MCP-Server (`Authorization: Bearer`) | Das Backend speichert den Block nirgends und reicht ihn **nur an den WLO-Server** weiter, nie an andere MCP-Server. |
| Echtheitsprüfung | Backend → `wlo_auth_status` (seit Paket 10) | Erst ein bestätigter Block gilt als Person (Cache 5 min je Block, abgewiesen 30 s). Abgewiesener Block → `auth_invalid` an das Widget. |
| Abmelden | Widget | Entfernt den Block aus dem Tab. **Am Server gilt er weiter** (A-4). |

## 2. Was ein Block ist

- Inhalt (verschlüsselt mit dem öffentlichen Schlüssel des Servers, RSA-OAEP + AES-GCM): WLO-Benutzername
  und **Passwort** — oder das edu-sharing-Ticket —, dazu eine Kennung `jti`.
- **Kein Ablauf.** Er gilt, bis sein `jti` aus der Erlaubnisliste des Servers fällt (Widerruf,
  Passwortwechsel, Verdrängung nach 10 Einträgen je Konto). Ein Ticket-Block endet faktisch mit dem Ticket.
- **Bearer:** Wer den Block besitzt, handelt am MCP-Server als die Person — lesen **und schreiben** mit
  ihren WLO-Rechten. Das Passwort selbst kann er nicht lesen (nur der Server entschlüsselt).
- **Keine Bindung:** kein Scope (nur `wlo`), keine Bindung an Herkunft, Client oder Werkzeuge.

## 3. Risiken

### R1 (A-2) Block auf einer fremden Gastseite — Missbrauch möglich

Das Widget ist eine Web-Komponente und läuft **im Fenster der Gastseite**. Sein `sessionStorage` gehört
damit der Gastseite: Jedes Skript dort — eigene, eingebundene (Werbung, Statistik, Chat-Plugins) oder ein
eingeschleustes (XSS) — kann den Block lesen. Weil er nicht abläuft und nicht gebunden ist, kann ein
Angreifer damit **bis zum Widerruf** als die Person in WLO lesen und schreiben, von jedem Rechner aus.

- Auf WLO-eigenen Seiten ist das Risiko das übliche (die Skripte sind bekannt).
- Auf **Drittseiten** hängt die Sicherheit der WLO-Konten an der Sorgfalt des Seitenbetreibers.
- Ein Ticket-Block ist weniger schlimm (endet mit dem Ticket), ein Passwort-Block lebt beliebig lange.

**Bis zum Umbau:** Widget mit Anmeldung nur auf vertrauenswürdigen Seiten einbetten; im Backend
`CORS_ALLOW_ALL=false` und `CORS_ORIGINS` mit den einbettenden Domänen setzen (`deploy/README.md`).
Seit 2026-10-15 bietet eine so geschlossene Anlage die Anmeldung (Knopf, Ticket-Tausch) auch nur
diesen Seiten an (`domain/anmelde_herkunft`); offen (Vorgabe) bleibt alles wie bisher.

### R2 (A-4) Abmelden widerruft nicht

`POST /auth/revoke {token}` gibt es, sendet aber **keine CORS-Kopfzeilen** — aus dem Widget auf einer
fremden Seite ist er nicht aufrufbar. Möglich ohne MCP-Änderung: Das Widget schickt den Block beim Abmelden
an ein Backend-Ende, das Backend ruft `/auth/revoke` serverseitig auf. (Entscheid offen,
`entscheidungen-offen.md`.) `POST /auth/revoke-all` braucht das Passwort und passt nicht in den Chat.

### R3 Widerruf braucht nur die Kennung

`/auth/revoke` entschlüsselt den mitgeschickten Block und streicht dessen `jti`. Da der öffentliche
Schlüssel veröffentlicht ist, kann jeder mit Kenntnis eines `jti` einen passenden Block bauen und damit
widerrufen (laut `AUTH.md` bekannt). Für Ticket-Blöcke ist der `jti` ableitbar (`sha256("wlo-ticket:"+ticket)`).
Folge: Abmelden fremder Personen, kein Zugriff.

### R4 `/auth/ticket` für jede Herkunft offen

`Access-Control-Allow-Origin: *`. Jede Seite, die ein Ticket hat, kann es tauschen. Das Ticket ist selbst
schon die Berechtigung; der Tausch macht daraus aber einen Block ohne eigene Frist.

### R5 `preparedRequest` aus jeder MCP-Antwort (Chatbot-Seite)

Das Backend übernahm `structuredContent.preparedRequest` aus Antworten **jedes** MCP-Servers und gab es an
das Widget, das die Anfrage mit der Repository-Sitzung der Person absetzt. Behoben im Chatbot (Paket 11):
Werkzeuge weiterer Server gehen einen eigenen Weg ohne `structuredContent`, und ihre Namen leiten keinen
WLO-Aufruf mehr um. Für den MCP-Server: Vertrag der vorbereiteten Anfrage dokumentieren
(erlaubte Methoden und Pfade).

## 4. Wünsche an den Umbau des MCP-Servers

Nach Wirkung sortiert:

1. **Kurzlebige Zugangstoken** (Minuten bis Stunden) mit Erneuerung — statt eines unbefristeten Blocks mit
   Passwort. Löst R1 im Kern: ein gestohlenes Token verfällt.
2. **Bindung**: Scope (`read` / `curate`) und Zielgruppe (Client bzw. Herkunft), damit ein Token aus dem
   Chat-Widget nicht überall gilt.
3. **Widerruf aus dem Widget**: `/auth/revoke` für die erlaubten Herkünfte per CORS öffnen — oder
   bestätigen, dass der serverseitige Weg über das Backend (R2) gewollt ist.
4. **Widerruf nur mit Besitz**: der Block (nicht nur sein `jti`) als Nachweis (R3).
5. **`/auth/ticket` mit Herkunftsliste** statt `*` (R4).
6. **`wlo_auth_status` mit Ablaufzeit**, sobald es eine gibt — das Backend kann dann rechtzeitig eine neue
   Anmeldung anbieten.
7. **Werkzeug-Annotationen** (`readOnlyHint`, `destructiveHint`) an allen Werkzeugen: Der Chatbot entscheidet
   für fremde Server danach, ob ein Werkzeug angeboten wird (Paket 11).

## 5. Was der Chatbot schon absichert

- Block nur an den WLO-Server, nie an andere MCP-Server; nicht gespeichert, nicht geloggt. Weitere Server
  (Paket 11): nur lesende Werkzeuge, eigener Namensraum, ohne Umleitungen, ohne Block, Ausgabe als
  Fremdinhalt gerahmt, bei persönlichen Daten in der Nachricht gesperrt.
- Echtheitsprüfung vor jedem Zug mit persönlicher Anmeldung (Paket 10, A-1).
- Schreiben nur zweistufig: Vorschau, dann Zustimmung im nächsten Zug; der Bestätigungsschlüssel erreicht das
  Modell nie; eine Abnahme gilt nur für die Person, unter der die Vorschau entstand (Paket 10, S-1).
- Abgewiesener Block (401/403) → das Widget bietet die Anmeldung neu an (Paket 10, A-3).

## 6. Beobachtungen aus dem Betrieb

- **Ausreißer bei der ersten Suche (Paket 15, 2026-10-17).** Im Lasttest `lt-b97eb9de93a3` brauchte
  `search_wlo_all("Elektrizität", Arbeitsblatt)` 22 103 ms; dieselben Aufrufe danach 2,0–3,2 s. Der Chatbot
  wartet bis zur Zeitgrenze von 60 s (bleibt so, Nutzer-Entscheid) — die Antwort kam, nur spät. Vermutung:
  kalter Pfad am Server (erste Anfrage nach Ruhe, Verbindungsaufbau zum Repositorium). Bitte an das MCP-Team:
  prüfen, ob sich die erste Anfrage nach Ruhezeit am Server so verhält; der Lasttest des Studios hat seit
  Paket 15 eine Aufwärm-Anfrage (zählt nicht mit) und zeigt je Anfrage die Werkzeugzeit, damit sich solche
  Ausreißer ohne die Nachrichten-Tabelle zuordnen lassen.
