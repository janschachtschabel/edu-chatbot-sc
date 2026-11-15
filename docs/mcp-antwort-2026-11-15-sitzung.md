# Antwort an den MCP-Entwickler: Anmeldung aus der WLO-Sitzung (2026-11-15)

Zu deiner Nachricht „Für das Chatbot-Team: die Anmeldung aus der WLO-Sitzung übernehmen“.
Danke, der Weg B ist bei uns eingebaut. Er ist aus, bis der Betrieb die Adresse einträgt.

## Kurzfassung

- Das Widget geht Weg B von selbst, wenn es in einer Seite des Repositorys sitzt. Mit `ticket`
  im Attribut gilt Weg A, wie du empfiehlst.
- Der Block aus der Sitzung liegt bei uns nur im Arbeitsspeicher und reist je Anfrage mit.
- Wir geben ihn in einer eigenen Kopfzeile ans Backend, nicht im JSON-Körper (Grund unten).
- **Ein Wunsch mit Gewicht:** Ein Block aus einer Sitzung gilt nach jedem neuen Tausch
  derselben Sitzung wieder, auch ein widerrufener oder abgelaufener (nächster Abschnitt).
- Deine Tauschstelle haben wir ohne Anmeldung nachgemessen; mit angemeldeter Sitzung noch nicht.

## Der Wunsch: ein alter Block soll nach einem neuen Tausch nicht wieder gelten

So lesen wir deinen Quelltext:

- Die Kennung eines Sitzungs-Blocks ist `sha256("wlo-session:" + sessionId)`
  (`auth/session-exchange.ts`).
- Geprüft wird an einem Block nur, ob die Kennung gelistet ist und der Name passt
  (`auth/credential.ts`, `credentialFromAccessBlock`). Der Ausstellzeitpunkt zählt nicht.
- Ist die Kennung nicht mehr gelistet (widerrufen, oder der Eintrag ist abgelaufen), trägt
  der nächste Tausch derselben Sitzung sie wieder ein.

Die Folge: „12 Stunden“ und „Abmelden widerruft“ gelten nur bis zum nächsten Tausch. Zwei
Fälle, die bei uns von selbst eintreten:

1. Unser Widget tauscht nach 12 Stunden still neu. Ein Block, den jemand in der ersten Stunde
   mitgenommen hat, gilt danach wieder, solange die Sitzung lebt.
2. Die Person meldet sich im Chat in Tab 1 ab (`/auth/revoke`). Tab 2 derselben Sitzung
   bekommt die Ablehnung, tauscht still neu, und der widerrufene Block aus Tab 1 gilt wieder.

Das wiegt, weil der Block anders als das Cookie für Skripte der Seite erreichbar ist: Ein
Skript der Seite kann `fetch` oder `XMLHttpRequest` umbiegen und den Block aus unserer Kopfzeile lesen, und es kann
deine Tauschstelle auch selbst rufen.

Bitte eins von beiden:

- den Ausstellzeitpunkt des Blocks gegen den Eintrag prüfen (ein Block, der älter ist als der
  letzte Widerruf oder der letzte Ablauf, gilt nicht), oder
- die Kennung je Tausch wechseln (etwa mit einem Zähler oder Zufallswert im Eintrag).

Weiter gedacht, kein Muss für den Start: den Block aus einer Sitzung an etwas binden, das ein
fremder Rechner nicht hat, etwa an unseren Client-Schlüssel (`X-WLO-Client-Key`). Ein
mitgenommener Block wäre dann außerhalb unseres Backends wertlos.

## Was das Widget tut

1. **Wo der Weg gilt:** Unser Backend nennt dem Widget die Adresse des Tauschs (bei uns
   `MCP_SESSION_URL`, etwa `https://<Repository-Host>/edu-sharing/services/wlo-mcp/auth/session`).
   Das Widget versucht ihn nur auf Seiten dieser Herkunft. Der Pfad muss auf `/auth/session`
   enden und unterhalb einer Wurzel liegen (`/edu-sharing/…`).
2. **Wer ist da:** `GET /edu-sharing/rest/iam/v1/people/-home-/-me-` mit der Sitzung der Seite.
   Für `esguest` rufen wir dich nicht auf.
3. **Tausch:** `POST` mit `credentials: 'same-origin'`, `Content-Type: application/json`,
   Körper `{}`. Kein `Authorization`. Frist 10 s.
4. **Vergleich:** `authority` aus deiner Antwort muss gleich `person.authorityName` der Seite
   sein, Zeichen für Zeichen. Sonst verwerfen wir den Block. Du lieferst den Namen bereinigt
   (`sanitizeText`); ein Konto mit doppeltem Leerraum, Steuerzeichen oder mehr als 120 Zeichen
   im Namen bleibt bei uns deshalb ohne Anmeldung. Das nehmen wir hin.
5. **Antworten:**

   | Von dir | Bei uns |
   |---|---|
   | 200 | Block im Arbeitsspeicher, Name am Abmelde-Knopf (`displayName`) |
   | 400 | ohne Anmeldung weiter, still |
   | 403 | ohne Anmeldung weiter, Zeile in der Konsole für den Betrieb |
   | 404, oder 200 ohne JSON (Pfad nicht eingehängt) | ebenso |
   | 503, 429 | nach `retryAfter` (höchstens 15 s) einmal erneut |
   | 415, sonstiges | ohne Anmeldung weiter, Zeile in der Konsole |

6. **Vor jedem Abruf, der den Block trägt,** fragen wir das Repository noch einmal, wer auf der
   Seite angemeldet ist (höchstens 3 s; eine Antwort gilt 2 s). Ist es ein Gast, verwerfen wir
   den Block. Ist es jemand anderes, verwerfen wir ihn und tauschen neu. War vorher niemand
   angemeldet und jetzt jemand, tauschen wir ebenfalls. Antwortet das Repository nicht, bleibt
   der Block. Ein 401 des Repositorys lesen wir wie einen Gast. Du
   schreibst im Quelltext, ob die Sitzungs-Kennung einen Wechsel der Anmeldung überlebt, sei
   nicht gemessen; für uns hängt daran damit wenig.
   - Für dein Budget: Ein Wechsel der Person kostet dich einen Tausch, ebenso jeder Neubau
     unseres Widgets auf der Seite. Scheitert ein Tausch, versuchen wir es fünf Minuten nicht
     von selbst wieder; bei 403, 404 und einer abweichenden `authority` erst nach dem Neuladen
     oder einem Klick der Person auf „Anmelden“.
7. **Ende:** Nach 12 Stunden tauschen wir still neu. Meldest du an einem Werkzeug
   `login_rejected` oder an `/auth/status` `authenticated: false`, verwirft das Backend den
   Block für den Zug und meldet es dem Widget; das tauscht einmal neu und arbeitet bei 400 ohne
   Anmeldung weiter.
8. **Abmelden im Chat:** `POST /auth/revoke` über unser Backend. Danach tauscht das Widget in
   diesem Tab nicht mehr von selbst, auch nach dem Neuladen. Erst ein Klick auf „Anmelden“
   tauscht wieder. Kommt ein Block noch aus einem laufenden Tausch zurück, widerrufen wir auch
   ihn.

## Warum Kopfzeile statt JSON-Körper

Du empfiehlst ein Feld im Körper der Chat-Anfrage. Wir bleiben bei unserer Kopfzeile
`WLO-Access-Block`: Nicht jeder Abruf mit Block hat bei uns einen JSON-Körper. Der Verlauf
ist ein GET, der Upload geht als Formular (`multipart`). Hinter dem Proxy der B-API braucht das die
Freigabe der Kopfzeile am Proxy-Eintrag (`allowedRequestHeaders`); das steht in unserer
Betriebsübergabe.

Deine drei Regeln für den Block gelten bei uns: nur im Arbeitsspeicher, nur an den MCP, je
Anfrage. Das Backend hält prozessweit nur einen Fingerabdruck für das Ergebnis der Prüfung.

Zwei Einschränkungen, damit es nicht falsch ankommt:

- Blöcke aus Weg A und aus der Anmeldung von Hand liegen bei uns weiter im `sessionStorage`
  des Tabs (nicht `localStorage`). Die Anmeldung von Hand ließe sich sonst nicht über ein
  Neuladen halten.
- „Im Arbeitsspeicher“ ist kein Versteck vor Skripten der Seite. Unser Bündel steht seit dem
  15.11. in einer Hülle, seine Variablen hängen nicht mehr an `window` (vorher taten sie es).
  Ein Skript der Seite kann aber weiter `fetch` oder `XMLHttpRequest` umbiegen und den Block aus der Kopfzeile lesen.

## Nachgemessen an deinem Stand

Lokal gestartet, `WLO_SESSION_EXCHANGE=1`, eigener Wegwerf-Schlüssel, gegen Staging, ohne
Anmeldung:

| Anfrage | Antwort |
|---|---|
| ohne Cookie | 400 „Es kam keine WLO-Sitzung mit“ |
| Gast-Sitzung (anonymer Abruf am Repository) | 400 „nicht (mehr) angemeldet“ |
| ohne `Origin` | 403 `origin_not_allowed` |
| fremde Herkunft | 403 `origin_not_allowed` |
| `Content-Type: text/plain` | 415 |
| `GET` | 405 |

Das passt zu deiner Tabelle. Den Tausch einer angemeldeten Sitzung prüfen wir, sobald der Pfad
auf Staging eingehängt ist.

## Zwei Fragen

1. **Ende der Sitzung an `/auth/status`:** Kommt nach dem Abmelden im Repository
   `authenticated: false` mit `upstream: "ok"`? Ohne `upstream: "ok"` und ohne `authority`
   lesen wir „nicht prüfbar“ und lassen die letzte Bestätigung bis zu 30 Minuten gelten. Am
   Werkzeug reicht uns `login_rejected`; so lesen wir deinen Quelltext
   (`apps/tool-defaults.ts`). Und: Nennt `/auth/status` für einen Sitzungs-Block `expiresAt`?
   Daran hängt unser stilles Erneuern nach 12 Stunden.
2. **`Origin` am Ingress:** Ohne `Origin` antwortest du 403. Browser schicken ihn bei einem
   `POST` mit; der Ingress des Repositorys muss ihn durchlassen. Bitte in die Anleitung für
   den Betrieb als eigenen Prüfpunkt. Und: Was antwortet das Repository unter dem Beispielpfad
   `/edu-sharing/services/…`, solange die Regel am Ingress fehlt? Wir rechnen mit 404, einer
   HTML-Seite oder einem 500 seines eigenen Servlets.

## Offen bei dir und beim Betrieb

- Der Pfad am Ingress des Staging-Repositorys und `WLO_SESSION_EXCHANGE=1` am Staging-MCP.
- Die Adresse, die wir als `MCP_SESSION_URL` eintragen.
