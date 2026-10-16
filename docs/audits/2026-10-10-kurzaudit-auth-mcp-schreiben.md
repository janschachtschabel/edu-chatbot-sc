# Kurzaudit — Weitergabe der Anmeldung und Schreibwege zum MCP-Server

**Datum:** 2026-10-10 · **Modus:** nur lesend, kein Code geändert, keine Tests ausgeführt.
Ergänzt [`2026-10-10-fehlerprotokoll.md`](2026-10-10-fehlerprotokoll.md) und
[`2026-10-10-verbesserungsprotokoll.md`](2026-10-10-verbesserungsprotokoll.md).

**Umfang:** der Weg der Anmeldung (Zugangsblock) vom Browser über das Backend zum WLO-MCP-Server, und
die Wege, auf denen Nutzeranfragen schreibende MCP-Werkzeuge auslösen: Muster-Weg (Tool-Loop),
Abnahme-Einlösung, Agent-Modus im Chat, `/api/agent` sowie die im Browser ausgeführte „vorbereitete
Änderung“ (E3/E4). Der MCP-Server selbst (`../wlo-mcp-server-sc/`) war **nicht** Gegenstand.

**Legende:** *Hoch / Mittel / Niedrig* · **[verifiziert]** im Quelltext nachgelesen ·
**[zu verifizieren]** braucht einen Laufzeit-Test.

---

## 1. So läuft es heute

```
Browser (Widget)                    Backend (boerdi)                          WLO-MCP-Server
─────────────────                   ────────────────                          ──────────────
Anmeldung: OAuth-PKCE-Popup oder    Kopfzeile WLO-Access-Block
Seiten-Ticket → Block "wlo2.…"      → adopt_turn_auth_block()  (immer, löscht auch)
in sessionStorage                   → ContextVar _turn_block (je Task, nie gespeichert)
                                    → Formprüfung ^wlo[...]{≤4096}
jede Chat-Anfrage:                  → httpx-Fabrik: Authorization: Bearer <Block>    → prüft Echtheit
  + WLO-Access-Block                   nur für den PRIMÄREN MCP-Server                  und Rechte
                                    Rangfolge: Zug-Block > MCP_AUTH_TOKEN (Dienstkonto)

Schreiben (2 Stufen, E1-Wall):
 Zug n:   Modell ruft Kurations-Werkzeug → confirmToken entfernt → Server liefert Vorschau + Schlüssel
          → Schlüssel aus dem Text geschnitten, Merkposten {tool,args,token,caller,Frist} in entities
          → Abnahme-Box + Knopf „Ja, so ausführen“
 Zug n+1: glatte Zustimmung (is_affirmation) + gleicher Aufrufer + Schreibrecht + Frist offen
          → Merkposten in der DB verbraucht → Aufruf mit gemerkten Argumenten + Schlüssel
          → Server schreibt  ODER  beschreibt die Änderung (preparedRequest)
          → Widget setzt sie auf der Repository-Seite selbst ab (Erlaubnisliste, Identitätsprüfung)
```

## 2. Was gut gelöst ist (geprüft, ohne Befund)

- **Block nie gespeichert, nie geloggt:** Er lebt nur im `ContextVar` und wird in jedem Zug neu
  gesetzt bzw. gelöscht ([`turn_auth.py:32-46`](../../backend/src/boerdi/api/turn_auth.py#L32-L46),
  [`auth.py:88-106`](../../backend/src/boerdi/services/mcp/auth.py#L88-L106)). Kein Übersprechen
  zwischen Zügen.
- **Formprüfung gegen Header-Injection:** `\Z`-Anker, kein Leer- oder Steuerzeichen, Präfix `wlo`,
  höchstens 4096 Zeichen ([`auth.py:59-70`](../../backend/src/boerdi/services/mcp/auth.py#L59-L70)).
  Das Backend reicht also keine beliebigen `Authorization`-Werte weiter.
- **Nur an den primären Server:** Registry- und Discover-Server bekommen weder Dienst-Token noch
  persönlichen Block ([`transport.py:89-98`](../../backend/src/boerdi/services/mcp/transport.py#L89-L98)).
- **Cache je Aufrufer:** Der Cache-Schlüssel trägt einen SHA-256-Fingerabdruck des Blocks; Kurations-
  Werkzeuge und `wlo_auth_status` werden nie gecacht
  ([`tool_cache.py:250-254`](../../backend/src/boerdi/services/mcp/tool_cache.py#L250-L254)).
- **Bestätigungs-Wall (E1):** Das Modell kann keinen `confirmToken` setzen (auf dem Hinweg entfernt)
  und sieht keinen (auf dem Rückweg geschwärzt). Im selben Zug lässt sich nichts bestätigen: Der
  Tool-Loop arbeitet mit einem Schnappschuss vom Zugbeginn, die Einlösung liest den Zustand aus der
  Datenbank ([`tool_loop.py:774-806`](../../backend/src/boerdi/services/tool_loop.py#L774-L806),
  [`write_confirm.py`](../../backend/src/boerdi/domain/write_confirm.py)).
- **Aufrufer-Bindung:** Ein Merkposten gilt nur für den Aufrufer, unter dem die Vorschau entstand.
  Fremde und alte Merkposten ohne Kennzeichen verfallen
  ([`write_approval.py:95-170`](../../backend/src/boerdi/services/write_approval.py#L95-L170)).
  Wer die Sitzung kennt (vgl. H-1 im Fehlerprotokoll), kann eine fremde Vorschau deshalb **nicht**
  einlösen.
- **Verbrauch vor dem Aufruf**, kein Wiederholungsversuch bei bestätigten Schreibaufrufen. So entsteht
  auch bei Netzfehlern keine Doppelbuchung
  ([`write_approval.py:240-251`](../../backend/src/boerdi/services/write_approval.py#L240-L251),
  [`client.py:353-379`](../../backend/src/boerdi/services/mcp/client.py#L353-L379)).
- **Ehrliche Fehlerarten:** `tool` (Server hat abgelehnt, also nichts geändert) wird getrennt von
  `transport`/`timeout` (ungewiss, bitte nachsehen)
  ([`transport.py:174-239`](../../backend/src/boerdi/services/mcp/transport.py#L174-L239)).
- **Zustimmungserkennung bewusst eng:** höchstens 6 Wörter, keine Frage, keine Vorbehalte oder
  Ablehnungsstämme ([`zustimmung.py:76-90`](../../backend/src/boerdi/domain/zustimmung.py#L76-L90)).
  Hintergrund-Züge (Ping/Tour) verwerfen nur im Speicher.
- **Schreibrecht als Produktregel:** Schreiben nur mit persönlicher Anmeldung, das Dienstkonto nur
  per Studio-Schalter ([`schreibrecht.py`](../../backend/src/boerdi/services/schreibrecht.py)). Dieselbe
  Regel gilt im Werkzeugangebot, bei der Einlösung und im Agent-Modus. `execute` gibt es nur mit
  Person ([`agent_write.py:56-80`](../../backend/src/boerdi/services/agent_write.py#L56-L80)).
- **Vorbereitete Änderung im Browser (E4):** Die feste Erlaubnisliste steht im Bündel und kommt nicht
  vom Server (Sammlung PUT/DELETE, KI-Metadatenvorschlag POST). Der Ursprung kommt aus
  `window.location`, und vor dem Schreiben wird geprüft, ob eine Person angemeldet ist (`esguest`).
  Das Backend prüft zusätzlich, dass der Pfad die Herkunft nicht verlassen kann
  ([`prepared-write.ts:94-233`](../../frontend/projects/ui/src/session/prepared-write.ts#L94-L233),
  [`prepared_write.py:82-124`](../../backend/src/boerdi/domain/prepared_write.py#L82-L124)).
  Ausgeliefert wird höchstens eine Änderung je Zug.
- **OAuth:** PKCE, die Rückmeldung muss von `e.source` des eigenen Fensters kommen und `state`
  wird geprüft ([`mcp-oauth.ts:153-181`](../../frontend/projects/ui/src/session/mcp-oauth.ts#L153-L181)).
- **Protokoll:** `confirmToken` wird geschwärzt, lange Nutzlasten werden gekürzt
  ([`client.py:96-108`](../../backend/src/boerdi/services/mcp/client.py#L96-L108)).

---

## 3. Befunde

| # | Schwere | Titel |
|---|---|---|
| A-1 | **Hoch** | Ein erfundener Block hebt die anonymen Kostendeckel im Agent-Modus auf |
| A-2 | Mittel | Block (verschlüsseltes WLO-Passwort, ohne Ablauf) liegt im `sessionStorage` der Gastseite |
| A-3 | Mittel | Ungültiger oder widerrufener Block: kein Signal ans Widget, doppelte Fehlaufrufe, Schreibangebot bleibt |
| A-4 | Mittel | Abmelden im Widget beendet den Zugang nicht |
| A-5 | Mittel | OAuth-Fenster nach drei `await` (= H-3 im Fehlerprotokoll) |
| A-6 | Niedrig | Freitext-Zustimmung führt aus, auch beiläufig („ok danke“) |
| A-7 | Niedrig | Vorschau und Schreibinhalte sind über den öffentlichen Verlauf lesbar (Folge von H-1) |
| A-8 | Niedrig | Schreib-Argumente (Titel, Beschreibungen) im INFO-Log |
| A-9 | Niedrig | `/api/agent`: `allow_curation` ist standardmäßig `true` |
| A-10 | Niedrig | Persistenz-Fehler nach erfolgreichem Schreiben ohne Rollback (M-1-Klasse) |

### A-1 Erfundener Block hebt die anonymen Agent-Deckel auf — Hoch [verifiziert, Wirkung zu verifizieren]
- **Ort:** [`agent_deckel.py:23-39`](../../backend/src/boerdi/services/agent_deckel.py#L23-L39) →
  `has_personal_auth()` → [`auth.py:109-159`](../../backend/src/boerdi/services/mcp/auth.py#L109-L159)
  (nur Formprüfung). Aufruf in [`respond_agent.py:329`](../../backend/src/boerdi/graph/nodes/respond_agent.py#L329).
- **Problem:** `has_personal_auth()` prüft nur die **Form**: Präfix `wlo`, nicht `wlo-anon.`. Wer im
  öffentlichen Chat `WLO-Access-Block: wlo2.x` mitschickt und per `X-Boerdi-Engine` den Agent-Modus
  wählt, bekommt die vollen Deckel. Laut Modulkopf von `agent_deckel.py` sind das bis 30 Runden,
  900 s und 900 000 Token je Zug statt der engen anonymen Werte. Für `/api/agent` ist das bekannt und
  durch die Drosselung abgefedert ([`turn_auth.py:68-73`](../../backend/src/boerdi/api/turn_auth.py#L68-L73)).
  Für die Deckel im Chat-Agent-Modus gibt es keinen zweiten Schutz.
- **Auswirkung:** Die Kostenbremse AG-6 ist mit einer Kopfzeile umgehbar. Der MCP-Server lehnt den Block
  ab (401). Die LLM-Runden laufen aber weiter, mit fehlschlagenden Werkzeugen, bis Runden-, Zeit- oder
  Token-Deckel greifen. Pro Anfrage bremst nur das Chat-Ratenlimit.
- **Fix (eine Variante):**
  1. Den Block **einmal je Zug echt prüfen**: Ein `wlo_auth_status`-Aufruf liefert `mode: user`.
     Das Ergebnis je Fingerabdruck einige Minuten cachen. Erst dann gilt der Block als „persönlich“
     (für Deckel, `execute` und Schreibangebot).
  2. Alternativ die Deckel an etwas Belegtes binden (Studio-Schlüssel, signierte Einbettung) und
     den Block nur noch für Rechte beim MCP nutzen.
  3. Mindestens: eigenes, engeres Ratenlimit für Agent-Züge im Chat und eine Metrik
     „Agent-Zug mit Block, MCP-401“.

### A-2 Block im `sessionStorage` der Gastseite — Mittel [verifiziert, dokumentierte Abwägung]
- **Ort:** [`mcp-access.ts:13-29, 54-74`](../../frontend/projects/ui/src/session/mcp-access.ts#L13-L74).
- **Problem:** Das Widget ist eine Webkomponente im DOM der Gastseite. Sein `sessionStorage` gehört
  also dem **Ursprung der Gastseite**. Jedes Skript dort kann den Block lesen: Analytics,
  Tag-Manager, eine XSS-Lücke der Gastseite. Der Kommentar nennt das selbst. Der Block verschlüsselt
  laut Kommentar ein WLO-Passwort und **läuft nie ab**.
- **Auswirkung:** Ein einmal abgegriffener Block erlaubt dauerhaft, unter der Person zu handeln, bis
  `/auth/revoke-all` aufgerufen wird.
- **Fix:**
  - **Kurzfristig:** den Block nur im Arbeitsspeicher der Komponente halten. Ein Reload kostet dann
    eine neue Anmeldung; mit dem Ticket-Weg bleibt das unsichtbar.
  - **Richtig (mit dem MCP-Team):** kurzlebige, eingeschränkte Zugangsblöcke (`exp`, Scope nur
    Chat-Werkzeuge) oder ein Backend-for-Frontend. Dann liegt der Block verschlüsselt im Backend an
    der Sitzung, das Widget hält nur ein HttpOnly-Cookie bzw. ein kurzes, eigenes Token.

### A-3 Ungültiger Block: kein Signal, doppelte Aufrufe, Schreibangebot bleibt — Mittel [verifiziert]
- **Ort:** [`transport.py:206-225`](../../backend/src/boerdi/services/mcp/transport.py#L206-L225),
  [`client.py:365-379`](../../backend/src/boerdi/services/mcp/client.py#L365-L379).
- **Problem:** Lehnt der MCP-Server einen Block mit 401 ab, sieht das Backend nur einen
  `transport`-Fehler. Ein erneuter Versuch läuft mit demselben Block: doppelte Wartezeit, doppelte
  Last. Das Widget erfährt nichts. Der Block bleibt gespeichert, der Knopf zeigt weiter
  „Abmelden“, und `schreiben_erlaubt()` bleibt wahr, weil es nur die Form prüft. Die Person bekommt
  Schreib-Vorschläge, die nie gelingen können.
- **Fix:**
  - Im Transport 401/403 als eigene Art `auth` erkennen und nicht wiederholen.
  - Im Zug einmal festhalten und als SSE-Event bzw. Antwortfeld `auth_invalid: true` melden.
  - Das Widget löscht daraufhin den Block und zeigt „Anmeldung abgelaufen – neu anmelden“.
  - Kurations-Werkzeuge für den Rest des Zugs aus dem Angebot nehmen.

### A-4 Abmelden beendet den Zugang nicht — Mittel [verifiziert, dokumentiert]
- **Ort:** [`mcp-access.ts:76-83`](../../frontend/projects/ui/src/session/mcp-access.ts#L76-L83),
  [`chat-shell.component.ts:633-638`](../../frontend/projects/ui/src/shell/chat-shell.component.ts#L633-L638).
- **Problem:** Abmelden löscht nur den lokalen Speicher. Ein vorher kopierter Block (siehe A-2) bleibt
  unbegrenzt gültig.
- **Fix:** Beim Abmelden zusätzlich den Widerruf am MCP-Server aufrufen, sofern er aus dem Browser
  erreichbar ist (CORS mit dem MCP-Team klären). Sonst über einen Backend-Endpunkt, der mit dem Block
  widerruft. Den Text der Bot-Blase ehrlich formulieren: „In diesem Fenster abgemeldet.“

### A-5 OAuth-Fenster nach mehreren `await` — Mittel
Siehe H-3 im [Fehlerprotokoll](2026-10-10-fehlerprotokoll.md):
[`mcp-oauth.ts:196-216`](../../frontend/projects/ui/src/session/mcp-oauth.ts#L196-L216). Fix: Das Fenster
synchron mit `about:blank` öffnen und die Adresse nachträglich setzen.

### A-6 Freitext-Zustimmung führt aus — Niedrig [verifiziert, Designfrage]
- **Ort:** [`zustimmung.py:20-90`](../../backend/src/boerdi/domain/zustimmung.py#L20-L90).
- **Problem:** „ok danke“, „passt“ oder „yes“ als nächste Nachricht nach einer Vorschau lösen das
  Schreiben aus. Das ist eng gefasst und gilt nur direkt nach der Vorschau, beim selben Aufrufer und
  innerhalb von 10 Minuten. Die Person kann aber eine beiläufige Antwort geben, ohne die Box gelesen
  zu haben.
- **Vorschlag:** Für Schreibvorgänge nur den **Knopf** gelten lassen, also eine eigene `action` statt
  Freitext. Freitext höchstens für nicht-destruktive Werkzeuge wie Vorschläge und Aufnahme in eine
  Sammlung, nicht für Löschen oder Ändern. Eine Studio-Einstellung wäre denkbar.

### A-7 Vorschau und Schreibinhalte im öffentlichen Verlauf — Niedrig [verifiziert]
- **Ort:** Die Abnahme-Box wird als Inline-Dokument persistiert
  ([`turn_persist.py:637-647`](../../backend/src/boerdi/services/turn_persist.py#L637-L647)),
  `debug._prepared_write` ebenso ([`turn_persist.py:341-343`](../../backend/src/boerdi/services/turn_persist.py#L341-L343)).
  Abrufbar ist beides ohne Anmeldung über `GET /api/sessions/{id}/messages`.
- **Auswirkung:** Wer die `bsid` kennt (siehe H-1), liest Titel, Beschreibungen und Sammlungs-IDs aus
  angemeldeten Schreibvorgängen mit, auch nicht-öffentliche. Einlösen kann er sie nicht (Aufrufer-Bindung).
- **Fix:** zusammen mit H-1 lösen. Bis dahin `_prepared_write` aus der öffentlichen Antwort von
  `get_messages` entfernen und nur für die Nachfrage nach einem Stream-Abbruch liefern, z. B. mit
  einem einmaligen Schlüssel aus dem `connected`-Event.

### A-8 Schreib-Argumente im INFO-Log — Niedrig [verifiziert]
- **Ort:** [`client.py:276`](../../backend/src/boerdi/services/mcp/client.py#L276) mit `_args_for_log`.
- **Problem:** Titel, Beschreibungen und Schlagwörter von Schreibvorgängen landen bis 500 Zeichen
  im Klartext im Log. Das sind personenbezogene bzw. unveröffentlichte Inhalte.
- **Fix:** Bei Kurations-Werkzeugen nur die Schlüssel und Längen protokollieren, die Werte erst auf
  DEBUG.

### A-9 `/api/agent`: `allow_curation` standardmäßig `true` — Niedrig [verifiziert]
- **Ort:** [`schemas_agent.py:46-47`](../../backend/src/boerdi/api/schemas_agent.py#L46-L47),
  [`agent_run.py:106-110`](../../backend/src/boerdi/services/agent_run.py#L106-L110),
  [`agent_tools.py:108`](../../backend/src/boerdi/services/agent_tools.py#L108)
  (`has_auth_token()`, also auch mit dem Dienstkonto).
- **Problem:** Ohne ausdrückliches `false` bekommt der Agent die Kurations-Werkzeuge, auch unter
  dem Dienstkonto der Anlage. In `propose` endet das bei der Vorschau. Geschrieben wird so nichts,
  aber Vorschauen unter dem Dienstkonto sind möglich, und der Vertrag ist „offen per Vorgabe“.
- **Fix:** Vorgabe auf `false` setzen oder mit `schreiben_erlaubt()` verknüpfen, wie im Chat.

### A-10 Persistenz nach erfolgreichem Schreiben ohne Rollback — Niedrig [verifiziert]
- **Ort:** [`write_approval.py:402-409`](../../backend/src/boerdi/services/write_approval.py#L402-L409).
- **Problem:** `save_message` scheitert, der Fehler wird nur auf DEBUG geloggt, und die Sitzung bleibt
  im Fehlerzustand. Das ist dieselbe Klasse wie M-1. Die nachfolgende Kostenbuchung geht verloren, und
  die Antwort „ausgeführt“ fehlt im Verlauf. Nach einem Stream-Abbruch findet die Nachfrage aus dem
  Verlauf dann die `_prepared_write` nicht, und die Änderung wird nie im Browser abgesetzt.
- **Fix:** `rollback()` aufrufen und auf WARNING loggen. Für E3 die vorbereitete Änderung zusätzlich
  im SSE-`result` sicherstellen (ist heute schon so) und den Fehlerpfad testen.

---

## 4. Verbesserungsvorschläge für die Zusammenarbeit mit dem MCP

| # | Vorschlag | Nutzen | Aufwand |
|---|---|---|---|
| V-1 | **Echtheitsprüfung des Blocks** einmal je Zug über `wlo_auth_status`, Ergebnis je Fingerabdruck cachen (TTL ~5 min). Die Rolle (`anonymous/service/user`) steuert Deckel, Schreibangebot und Anzeige | schließt A-1, korrektes Schreibangebot (A-3) | S–M |
| V-2 | **Kurzlebige, eingeschränkte Blöcke** beim MCP-Server anregen: `exp`, Scope „chat“, Refresh über Ticket | entschärft A-2/A-4 grundsätzlich | M (MCP-Team) |
| V-3 | **Fehlerart `auth`** im Transport plus SSE-Hinweis an das Widget: Block löschen, neu anmelden | klare UX, keine Doppelaufrufe | S |
| V-4 | **Schreiben nur per Knopf** (`action=confirm_write` mit Merkposten-ID) statt Freitext | keine versehentliche Ausführung | S |
| V-5 | **Merkposten-ID in der Box**: Der Knopf schickt die ID mit, das Backend prüft ID, Aufrufer und Frist | eindeutige Zuordnung bei mehreren Vorschauen hintereinander | S |
| V-6 | **Audit-Trail für Schreibvorgänge** in einer eigenen Tabelle: Zeit, Sitzung, Aufrufer-Fingerabdruck, Werkzeug, Knoten-IDs, Ergebnisart. Keine Inhalte. Studio-Ansicht dazu | Nachvollziehbarkeit, Support bei „ungewiss“ | M |
| V-7 | **Rechte-bewusstes Angebot:** Der MCP liefert je Block die erlaubten Werkzeuge (`tools/list` mit Auth), das Backend bietet nur diese an | weniger Vorschauen, die am Recht scheitern | M |
| V-8 | **Ergebnis nach „ungewiss“ selbst prüfen:** Nach `transport`/`timeout` lesend nachsehen, z. B. ob das Material in der Sammlung liegt, statt die Person zu bitten | weniger Dubletten und Nachfragen | M |
| V-9 | **Ende-zu-Ende-Test** gegen einen MCP-Testmandanten: Vorschau → Ja → Schreiben, fremder Aufrufer, Ablauf, 401, Stream-Abbruch mit E3 | sichert die Kette als Ganzes | M |
| V-10 | **Verbindungs-Pool je Aufrufer-Fingerabdruck** (siehe A-3 im Verbesserungsprotokoll); der Block bleibt pro Verbindung korrekt | Latenz | M |

## 5. Empfohlene Reihenfolge
1. **A-1** über V-1 (Echtheitsprüfung): schließt die Kostenlücke und korrigiert das Schreibangebot.
2. **A-3** über V-3: kleiner Eingriff, deutlich bessere UX bei abgelaufener Anmeldung.
3. **A-5/H-3** (Popup) und **A-6** über V-4/V-5 (Knopf statt Freitext).
4. **A-2/A-4** mit dem MCP-Team (V-2); kurzfristig den Block nur im Speicher halten.
5. **A-7** zusammen mit H-1, dazu **A-8**, **A-9** und **A-10** als kleine Aufräumarbeiten.

## 6. Spekulative Analyse: Schreiben trotz Anmeldung abgelehnt

> **Status: Hypothesen, nicht verifiziert.** Gemeldet ist: Die Anmeldung funktioniert grundsätzlich
> (getestet), in bestimmten Situationen werden schreibende Aktionen aber so abgelehnt, als wäre
> niemand angemeldet. Einen Code-Fehler, der den Block zufällig verliert, habe ich **nicht** gefunden:
> Die Kopfzeile geht bei Stream und Ersatzweg mit
> ([`stream-client.ts:166, 262`](../../frontend/projects/ui/src/stream/stream-client.ts#L166)), und das
> Backend übernimmt sie in jedem Zug neu. Die folgenden Wege führen alle zu einer Ablehnung, die nach
> außen wie „Anmeldung nicht erkannt“ aussieht. Sortiert nach meiner Einschätzung der Wahrscheinlichkeit.

### S-1 Neuer Zugangsblock zwischen Vorschau und „Ja“ (Hauptverdacht)
- **Mechanik:** Eine offene Abnahme ist an den Fingerabdruck des Blocks gebunden (SHA-256 über den
  Block, [`write_approval.py:95-101`](../../backend/src/boerdi/services/write_approval.py#L95-L101),
  [`auth.py:162-195`](../../backend/src/boerdi/services/mcp/auth.py#L162-L195)). Beim Ticket-Weg tauscht
  das Widget bei **jedem Laden der Seite** das Ticket gegen einen neuen Block, auch wenn schon einer da
  ist ([`ticket-login.ts:26-30`](../../frontend/projects/ui/src/session/ticket-login.ts#L26-L30),
  [`chat-shell.component.ts:610-623`](../../frontend/projects/ui/src/shell/chat-shell.component.ts#L610-L623)).
- **Annahme (zu verifizieren am MCP-Server):** Der Block ist mit AES-GCM verschlüsselt (Kommentar in
  [`mcp-access.ts:38`](../../frontend/projects/ui/src/session/mcp-access.ts#L38)). Bei jedem Tausch
  entsteht also vermutlich ein neuer Text und damit ein neuer Fingerabdruck, obwohl die Person dieselbe ist.
- **Folge:** Vorschau, dann Reload oder Seitenwechsel, dann „Ja“. Das Backend wertet das als „anderer
  Aufrufer“ und verwirft. Dasselbe passiert nach einer erneuten OAuth-Anmeldung oder wenn die Gastseite
  das `ticket` neu setzt.
- **Log:** `offener Vorgang für … verworfen — anderer Aufrufer als bei der Vorschau`
- **Abhilfe:** Die Bindung an die **Identität** hängen, die `wlo_auth_status` liefert, nicht an den
  Text des Blocks (siehe V-1). Oder den Ticket-Tausch überspringen, wenn schon ein Block vorliegt und
  das Ticket dieselbe Person meint.

### S-2 Repository-Sitzung abgelaufen, nicht die MCP-Anmeldung
- **Mechanik:** Im eingebetteten Betrieb (E3/E4) schreibt nicht der MCP-Server, sondern der Browser mit
  der edu-sharing-Sitzung der Seite. Vorher prüft er die Identität und bricht bei `esguest` ab
  ([`prepared-write.ts:199-214`](../../frontend/projects/ui/src/session/prepared-write.ts#L199-L214)).
- **Folge:** Der MCP-Block läuft nie ab, die Repository-Sitzung schon. In langen Gesprächen gelingt die
  Vorschau, die Ausführung aber nicht.
- **Erkennbar an:** Chat-Meldung `prepared.signedOut` („Im Repositorium bist du gerade nicht
  angemeldet …“). `prepared.unreachable` deutet dagegen auf eine Einbettung außerhalb der
  Repository-Domain oder auf CORS hin.
- **Abhilfe:** Die Meldung um einen Knopf „im Repositorium neu anmelden“ ergänzen. Optional die
  Identität schon bei der Vorschau prüfen, damit der Fehler früher sichtbar wird.

### S-3 Neuer Tab oder neues Fenster
- **Mechanik:** Der Verlauf hängt an der `bsid` in `localStorage` bzw. im Cookie, ist also in allen Tabs
  gleich. Der Block liegt im `sessionStorage` und gilt nur für einen Tab.
- **Folge:** Im neuen Tab sieht die Person ihr Gespräch, ist aber anonym, sofern kein Ticket übergeben
  wird. Ein „Ja“ zu einer Vorschau aus dem alten Tab führt zu S-1, eine neue Schreibanfrage bekommt keine
  Werkzeuge.
- **Log:** `Muster … verlangt kuratierende Werkzeuge …, aber in diesem Zug ist niemand persönlich angemeldet`
- **Abhilfe:** Beim Wiederherstellen eines Verlaufs mit offener Abnahme ohne Block einen Hinweis „Bitte
  erneut anmelden“ zeigen.

### S-4 Ticket-Tausch noch nicht fertig
- **Mechanik:** Der Tausch startet erst, wenn die Konfiguration geladen ist (`mcpAuthBase`), und läuft
  asynchron. Nachrichten davor (Startauftrag, Kontext-Ping, schneller Klick) gehen anonym hinaus.
- **Erkennbar an:** In der Browser-Konsole bei einem Fehlschlag `WLO-Anmeldung über das Seiten-Ticket
  nicht gelungen: …`. Bei Erfolg zeigt nur das Timing den Fall.
- **Abhilfe:** Das Senden von Nachrichten zurückhalten, bis der Ticket-Tausch beendet ist (nur wenn
  `ticket` gesetzt ist).

### S-5 Das „Ja“ wird nicht als Zustimmung erkannt
- **Mechanik:** Die Zustimmung ist bewusst eng gefasst
  ([`zustimmung.py:20-90`](../../backend/src/boerdi/domain/zustimmung.py#L20-L90)): höchstens 6 Wörter,
  kein Fragezeichen, keine Vorbehalts- oder Ablehnungswörter.
- **Beispiele, die nicht zählen:**
  - „Ja, das kann **noch** rein“ (enthält „noch“)
  - „ok, **aber** schnell“ (enthält „aber“)
  - „Ja bitte füge das Material jetzt hinzu“ (7 Wörter)
  - „Ja?“ (Fragezeichen)
- **Folge:** Die Abnahme wird verworfen und es kommt eine neue Vorschau. Das wirkt wie „er lehnt ab“.
- **Log:** `… verworfen — dieser Zug ist keine Antwort auf die Vorschau`
- **Abhilfe:** Ausführen nur per Knopf mit Merkposten-ID (V-4/V-5). Freitext höchstens als Ergänzung.

### S-6 Zwischenereignis oder Fristablauf
- **Mechanik:** Ein sichtbarer Kontext-Gruß (Wechsel in einer Single-Page-App), eine Direkt-Aktion oder
  ein anderer Zug zwischen Vorschau und „Ja“ verwirft die Abnahme. Nach 10 Minuten ist der Schlüssel
  abgelaufen.
- **Log:** `… verworfen — …` bzw. `offener Vorgang für … ist abgelaufen — es folgt eine neue Vorschau`
- **Abhilfe:** Die Frist in der Abnahme-Box anzeigen. Den Kontext-Gruß unterdrücken, solange eine
  Abnahme offen ist.

### S-7 Falsches Muster, gar kein Anmeldeproblem
- **Mechanik:** Kurations-Werkzeuge werden nur angeboten, wenn das Muster sie nennt (M18, M20). Bei
  M05 oder M08 fehlen sie, und das Modell erklärt dann oft selbst, man müsse sich anmelden.
- **Erkennbar an:** In den Debug-Infos des Zugs `pattern` ≠ M18/M20 und kein Kurations-Werkzeug unter
  `tools_called`.
- **Abhilfe:** `classify-overrides` für die gemeldeten Formulierungen schärfen. Ein Golden-Flow
  „Kuration angemeldet“.

### S-8 Block ungültig (widerrufen, Server-Schlüssel gewechselt)
- **Mechanik:** Der MCP-Server antwortet mit 401. Das Backend wertet das als `transport`, versucht es
  ein zweites Mal und meldet dem Widget nichts (A-3).
- **Log:** `MCP tool … transport error @ …: … 401 Unauthorized`
- **Abhilfe:** V-3 (Fehlerart `auth` plus Signal an das Widget).

### Diagnose-Tabelle

| Log-Zeile (Backend) bzw. Meldung | Wahrscheinliche Ursache |
|---|---|
| `anderer Aufrufer als bei der Vorschau` | S-1 oder S-3 |
| `dieser Zug ist keine Antwort auf die Vorschau` | S-5 oder S-6 |
| `ist abgelaufen — es folgt eine neue Vorschau` | S-6 |
| `niemand persönlich angemeldet` | S-3 oder S-4 |
| `Kopfzeile WLO-Access-Block vorgelegt, aber unbrauchbar` | Block beschädigt (Form oder Länge) |
| `401 Unauthorized` | S-8 |
| Chat: „Im Repositorium bist du gerade nicht angemeldet …“ | S-2 |
| Debug: `pattern` ≠ M18/M20 | S-7 |

### Nächster Schritt zur Klärung
Für jeden gemeldeten Fall brauche ich:
1. den genauen Text der Ablehnung im Chat,
2. die Backend-Logzeilen rund um diesen Zug (über die `session_id` zu finden),
3. die Angabe, ob das Widget mit `ticket` eingebettet war oder per OAuth-Knopf angemeldet wurde.

Damit lässt sich jeder Fall einer der Hypothesen S-1 bis S-8 zuordnen oder sie verwerfen. Für S-1
zusätzlich beim MCP-Team klären, ob zwei Tausche desselben Tickets denselben oder verschiedene Blöcke
ergeben.

## Nicht abgedeckt
Kein Live-Test gegen den MCP-Server: Verhalten bei 401, tatsächliche Kosten von A-1, Ticket-Endpunkt.
Den Code des MCP-Servers (Schlüsselbindung, Fristen, `preparedRequest`) habe ich nicht gelesen; ich
verlasse mich auf die Beschreibungen in den Kommentaren des Backends. `agent_loop.py` ist nur
auszugsweise gelesen (Einsatz von `WriteGate`).
