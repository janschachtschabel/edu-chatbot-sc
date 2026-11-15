# Antwort an den MCP-Entwickler: Anmeldung aus der WLO-Sitzung (2026-11-15)

Zu deiner Nachricht „Für das Chatbot-Team: die Anmeldung aus der WLO-Sitzung übernehmen“.
Danke, der Weg B ist bei uns eingebaut. Er ist aus, bis der Betrieb die Adresse einträgt.

**Was wir von dir brauchen, steht in Abschnitt 1. Alles danach ist zur Information.**

## 1. Was wir von dir brauchen

### 1a. Den Sitzungs-Pfad in deinem Helm-Chart, so wie beim md-editor

Der Weg B braucht einen Pfad auf dem Host des Repositorys unterhalb von `/edu-sharing`; nur
dorthin schickt der Browser das Sitzungs-Cookie (gemessen an Staging: `JSESSIONID` und
`INGRESSCOOKIE` mit `Path=/edu-sharing`, `HttpOnly`). Das ist kein Eingriff in edu-sharing:
Der md-editor macht es genauso und läuft so auf Staging
(`https://repository.staging.openeduhub.net/edu-sharing/services/md-editor/` antwortet mit dem
Editor). Sein Chart legt dafür ein eigenes Ingress-Objekt mit dem Repository-Host an
(`ingress.basePath`, Präfix wird abgeschnitten, `config.auth.cookie.enabled`).

Dein Chart kennt das noch nicht: `templates/ingress.yaml` legt nur `path: /` auf `ingress.host`
an. Bitte:

- eine zweite, eigene Ingress-Regel, abschaltbar, etwa `sessionIngress.host`
  (Repository-Host) und `sessionIngress.path` (Vorgabe `/edu-sharing/services/wlo-mcp`), die
  **nur** `<path>/auth/session` auf `/auth/session` umschreibt (`pathType: Exact`, nicht den
  ganzen Server);
- dazu im Chart prüfen, was der md-editor prüft: Pfad unter `/edu-sharing`, sonst bricht
  `helm template` ab; mit gesetztem `sessionIngress.host` gilt `WLO_SESSION_EXCHANGE=1`;
- in deiner Betriebsanleitung: `Cookie` und `Origin` müssen durchkommen; `TRUST_PROXY` zur
  Proxy-Kette des Repository-Ingress.

**Die eigentliche Frage dahinter:** Der md-editor läuft im Cluster des Repositorys, dein
Staging-Server läuft auf einem eigenen Rechner (`wlo-mcp.87.106.195.152.nip.io`). Eine
Ingress-Regel im Cluster kann nicht ohne Weiteres auf einen Rechner außerhalb zeigen. Für
Weg B muss der MCP (mindestens der Teil, der `/auth/session` beantwortet) im Cluster des
Repositorys laufen, wie der md-editor. Wer entscheidet das, und ist es geplant?

### 1b. Ein alter Sitzungs-Block soll nach einem neuen Tausch nicht wieder gelten

So lesen wir deinen Quelltext:

- Die Kennung eines Sitzungs-Blocks ist `sha256("wlo-session:" + sessionId)`
  (`auth/session-exchange.ts`).
- Geprüft wird an einem Block nur, ob die Kennung gelistet ist und der Name passt
  (`auth/credential.ts`, `credentialFromAccessBlock`). Der Ausstellzeitpunkt zählt nicht.
- Ist die Kennung nicht mehr gelistet (widerrufen, oder der Eintrag ist abgelaufen), trägt der
  nächste Tausch derselben Sitzung sie wieder ein.

Die Folge: „12 Stunden“ und „Abmelden widerruft“ gelten nur bis zum nächsten Tausch. Zwei
Fälle, die bei uns von selbst eintreten:

1. Unser Widget tauscht nach 12 Stunden still neu. Ein Block, den jemand in der ersten Stunde
   mitgenommen hat, gilt danach wieder, solange die Sitzung lebt.
2. Die Person meldet sich im Chat in Tab 1 ab (`/auth/revoke`). Tab 2 derselben Sitzung
   bekommt die Ablehnung, tauscht still neu, und der widerrufene Block aus Tab 1 gilt wieder.

Das wiegt, weil der Block anders als das Cookie für Skripte der Seite erreichbar ist: Ein
Skript der Seite kann `fetch` oder `XMLHttpRequest` umbiegen und den Block aus unserer
Kopfzeile lesen, und es kann deine Tauschstelle auch selbst rufen.

Bitte eins von beiden:

- den Ausstellzeitpunkt des Blocks gegen den Eintrag prüfen (ein Block, der älter ist als der
  letzte Widerruf oder der letzte Ablauf, gilt nicht), oder
- die Kennung je Tausch wechseln (etwa mit einem Zähler oder Zufallswert im Eintrag).

Weiter gedacht, kein Muss für den Start: den Block aus einer Sitzung an etwas binden, das ein
fremder Rechner nicht hat, etwa an unseren Client-Schlüssel (`X-WLO-Client-Key`). Ein
mitgenommener Block wäre dann außerhalb unseres Backends wertlos.

### 1c. Eine Frage

**Ende der Sitzung an `/auth/status`:** Kommt nach dem Abmelden im Repository
`authenticated: false` mit `upstream: "ok"`? Ohne `upstream: "ok"` und ohne `authority` lesen
wir „nicht prüfbar“ und lassen die letzte Bestätigung bis zu 30 Minuten gelten. Am Werkzeug
reicht uns `login_rejected`; so lesen wir deinen Quelltext (`apps/tool-defaults.ts`). Und:
Nennt `/auth/status` für einen Sitzungs-Block `expiresAt`? Daran hängt unser stilles Erneuern
nach 12 Stunden.

---

## 2. Zur Information: was das Widget tut

1. **Wo der Weg gilt:** Unser Backend nennt dem Widget die Adresse des Tauschs (bei uns
   `MCP_SESSION_URL`, etwa `https://<Repository-Host>/edu-sharing/services/wlo-mcp/auth/session`).
   Das Widget versucht ihn nur auf Seiten dieser Herkunft. Der Pfad muss auf `/auth/session`
   enden und unterhalb einer Wurzel liegen (`/edu-sharing/…`).
2. **Wer ist da:** `GET /edu-sharing/rest/iam/v1/people/-home-/-me-` mit der Sitzung der Seite.
   Für `esguest` (und für ein 401) rufen wir dich nicht auf.
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

   Ohne die Regel am Ingress antwortet das Repository selbst mit 404 (gemessen an Staging unter
   `/edu-sharing/services/wlo-mcp/auth/session`); das fällt bei uns unter „nicht eingerichtet“.
6. **Vor jedem Abruf, der den Block trägt,** fragen wir das Repository noch einmal, wer auf der
   Seite angemeldet ist (höchstens 3 s; eine Antwort gilt 2 s). Ist es ein Gast, verwerfen wir
   den Block. Ist es jemand anderes, verwerfen wir ihn und tauschen neu. War vorher niemand
   angemeldet und jetzt jemand, tauschen wir ebenfalls. Antwortet das Repository nicht, bleibt
   der Block. Du schreibst im Quelltext, ob die Sitzungs-Kennung einen Wechsel der Anmeldung
   überlebt, sei nicht gemessen; für uns hängt daran damit wenig.
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

## 3. Zur Information: Kopfzeile statt JSON-Körper

Du empfiehlst ein Feld im Körper der Chat-Anfrage. Wir bleiben bei unserer Kopfzeile
`WLO-Access-Block`: Nicht jeder Abruf mit Block hat bei uns einen JSON-Körper. Der Verlauf ist
ein GET, der Upload geht als Formular (`multipart`). Hinter dem Proxy der B-API braucht das die
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
  Ein Skript der Seite kann aber weiter `fetch` oder `XMLHttpRequest` umbiegen und den Block
  aus der Kopfzeile lesen.

## 4. Zur Information: nachgemessen an deinem Stand

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
