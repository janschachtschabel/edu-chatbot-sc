# Anmeldung aus der WLO-Sitzung übernehmen (2026-11-15)

Plan mit den Entscheiden SA-1 bis SA-15:
[`2026-11-15-anmeldung-aus-der-sitzung.md`](../plans/2026-11-15-anmeldung-aus-der-sitzung.md).
Anlass: Der MCP-Server tauscht neu eine Sitzung des Repositorys gegen einen Zugangsblock
(`POST /auth/session`, am MCP ohne Vorgabe aus).

## Was sich ändert

Sitzt das Widget in einer Seite des Repositorys und ist dort jemand angemeldet, arbeitet der
Chatbot mit dessen Rechten. Niemand meldet sich im Widget an, die Seite braucht kein Ticket.

- **Erkennen:** Das Backend nennt im Config-Bündel die Adresse des Tauschs (neue Einstellung
  `MCP_SESSION_URL`, Feld `mcp_session_url`). Das Widget geht den Weg nur, wenn die Adresse
  dieselbe Herkunft hat wie die Seite. Auf anderen Seiten stellt es dazu keine Anfrage.
- **Tauschen:** Erst fragt das Widget das Repository, wer angemeldet ist. Ein Gast wird nicht
  getauscht. Dann `POST` an die Tauschstelle; nennt sie eine andere Person als die Seite, wird
  der Block verworfen.
- **Halten:** Der Block liegt nur im Arbeitsspeicher. Nach dem Neuladen tauscht das Widget
  neu, ebenso wenn die Gastseite das Widget neu baut.
- **Weitergeben:** Wie bisher je Anfrage in der Kopfzeile `WLO-Access-Block` ans Backend, von
  dort als `Bearer` an den MCP. Am Backend ändert sich am Zugangsweg nichts.
- **Vor jedem Abruf mit Block** fragt das Widget noch einmal, wer auf der Seite angemeldet ist
  (Züge, Verlauf, „Meine Vorgänge“, Ablage, Dokumente). Zeigt sie einen Gast, fällt der Block
  weg; zeigt sie eine andere Person, tauscht das Widget neu. War vorher niemand angemeldet und
  jetzt jemand, tauscht es ebenfalls: Wer sich nach dem Laden im Repository anmeldet, ist beim
  nächsten Zug auch im Chat angemeldet. Kosten: auf Seiten des Repositorys ein kleiner Abruf
  je Zug, auch für Gäste.
- **Zeigen:** Der Knopf heißt „Abmelden — angemeldet als …“. Im Chat steht dazu kein Satz.
- **Erneuern:** Nach 12 Stunden still neu. Lehnt der MCP den Block ab, tauscht das Widget
  einmal neu; ohne Sitzung geht es mit einem Satz ohne Anmeldung weiter.
- **Abmelden:** Widerruft den Block und gilt für den Tab, auch nach dem Neuladen. Der Satz
  sagt, dass die Person in WLO angemeldet bleibt. „Anmelden“ nimmt danach wieder die Sitzung.
  Ist dort niemand angemeldet, sagt ein Satz das und bietet die Anmeldung von Hand an.
- **Reihenfolge:** Ein Ticket der Seite geht vor (Weg A). Die Anmeldung von Hand bleibt.

Schreiben bleibt hinter Vorschau und Zustimmung.

Am Ticket-Weg neu: Meldet sich jemand während eines laufenden Tauschs ab, widerruft das Widget
auch den Block, der danach noch zurückkommt. Bisher warf es ihn nur lokal weg.

## Sicherheit

- Der Pfad muss auf `/auth/session` enden und aus schlichten Stufen bestehen. Die Anfrage
  entsteht aus Herkunft der Seite plus Pfad. Geprüft im Backend (der Start scheitert an einer
  unbrauchbaren Adresse) und noch einmal im Widget, nach derselben Regel.
- Im Klartext sehen das Sitzungs-Cookie weder das Widget noch das Backend. Der Block enthält
  es verschlüsselt; lesen kann es nur der MCP-Server.
- Bekannte Restrisiken (R6 in [`mcp-und-anmeldung.md`](../mcp-und-anmeldung.md)):
  - Ein Skript der Seite kann den Block abgreifen, das Cookie nicht. Der Weg gehört nur auf
    Seiten, deren Skripte der Betreiber verantwortet.
  - Das Widget-Bündel läuft ohne Hülle; seine Variablen sind über `window` erreichbar. Eine
    Hülle ist ein eigener Schritt (offene-befunde §4). Nachtrag: am selben Tag umgesetzt,
    [`2026-11-15-widget-buendel-in-huelle.md`](2026-11-15-widget-buendel-in-huelle.md).
  - Beim MCP gilt ein widerrufener oder abgelaufener Block aus einer Sitzung nach dem nächsten
    Tausch derselben Sitzung wieder. Der Wunsch dazu steht in der Antwort an den Entwickler.
  - Beim Wechsel der Person bleibt das Gespräch stehen; die neue Person sieht den Verlauf der
    alten. Offene Entscheidung (offene-befunde §2).

## Gemessen

Am lokal gestarteten MCP-Stand vom 15.11. (`WLO_SESSION_EXCHANGE=1`, eigener Wegwerf-Schlüssel,
gegen Staging, ohne Anmeldung):

| Anfrage an `/auth/session` | Antwort |
|---|---|
| ohne Cookie | 400 |
| Gast-Sitzung des Repositorys | 400 |
| ohne `Origin` oder fremde Herkunft | 403 `origin_not_allowed` |
| `Content-Type: text/plain` | 415 |
| `GET` | 405 |

Der Pfad sendet keine CORS-Kopfzeilen. Das Repository meldet einen Gast als `esguest`; ohne
Gast-Zugang antwortet es auf „wer bin ich“ mit 401 ohne `WWW-Authenticate` (kein
Anmelde-Dialog des Browsers).

**Nicht gemessen:** der Tausch einer angemeldeten Sitzung, im Browser und am Backend. Dafür
muss der Pfad am Ingress des Staging-Repositorys eingehängt sein. Die Tests folgen der Nachricht
des MCP-Entwicklers und seinem Quelltext.

## Review

Drei unabhängige Reviews, jedes nach der Nachbesserung des vorigen. Kein kritischer Befund.

1. **Erstes Review: 1 schwerer, 8 mittlere Punkte.**
   - Schwer: Der Block war im ausgelieferten Bündel über `window` erreichbar, weil das Bündel
     ohne Hülle lief. Behoben in einem eigenen Schritt
     ([`2026-11-15-widget-buendel-in-huelle.md`](2026-11-15-widget-buendel-in-huelle.md)).
   - Behoben: Fristen an beiden Abrufen; 429 wird wie 503 einmal wiederholt; ein Block, der
     nach einem Abmelden noch aus einem laufenden Tausch kommt, wird auch am Server widerrufen;
     Widget und Backend lesen die Adresse nach demselben Muster; drei zu starke Zusagen in der
     Doku.
   - Daraus neu: die Frage vor jedem Abruf, wer auf der Seite angemeldet ist (SA-13).
2. **Zweites Review: kein schwerer, 5 mittlere Punkte.** Behoben:
   - Die Frage galt nur für Züge; jetzt für jeden Abruf mit Block.
   - Für wen der Block gilt, stand in der Instanz; jetzt neben dem Block (SA-15).
   - Die Wache konnte einen Abruf lange aufhalten, und zwei gleichzeitige liefen getrennt.
3. **Drittes Review: kein schwerer, 7 mittlere Punkte.** Behoben:
   - Eine neu gebaute Instanz übernahm den Block und sandte ihn ungeprüft, bis das
     Config-Bündel da war. Sie übernimmt ihn jetzt nicht mehr.
   - Die Pause nach einem gescheiterten Tausch galt nicht für den Tausch beim Laden.
   - Eine Abweisung des Servers konnte den Block einer inzwischen neu getauschten Person
     treffen oder den Satz doppelt sagen.
   - Ein 401 des Repositorys galt als „keine Aussage“; jetzt als „niemand angemeldet“.
   - Lücken in den Tests und vier Stellen in der Doku.

Nicht behoben, festgehalten im Plan: Mehrere Widgets auf einer Seite zeigen einen Wechsel am
Knopf erst beim nächsten eigenen Abruf; beim Wechsel der Person bleibt das Gespräch stehen
(offene Entscheidung).

## Geprüft

- Backend: volle Suite 10 624 Tests bestanden, 5 übersprungen; ruff sauber. Neu
  `tests/test_sitzungs_tausch_adresse.py`.
- Frontend: 4 138 Tests in vier Projekten bestanden (ui 1 504, ui-module 380, widget 98,
  studio 2 156); ESLint sauber. Neu `session/session-login.spec.ts`,
  `session/sitzungs-wache.spec.ts`, `shell/chat-shell-sitzung.spec.ts`.
- E2E: 118 von 118 bestanden, gegen das Bündel in der Hülle.
- Bündel: 670,55 kB von 700 kB roh (95,8 %), 195,38 kB von 210 kB gzip (93,0 %).

## Deploy

- Image neu bauen. Keine Migration, kein `import-config`.
- Der Weg ist ohne `MCP_SESSION_URL` aus; bis dahin ändert sich nichts.
- Einschalten (Reihenfolge egal, wirksam erst mit allen drei):
  1. MCP-Server: `WLO_AUTH_PRIVATE_KEY`, `WLO_SESSION_EXCHANGE=1`, bei abweichender Adresse
     `WLO_SESSION_ALLOWED_ORIGINS`; `TRUST_PROXY` passend zum Ingress.
  2. Ingress des Repository-Hosts: Pfad unterhalb von `/edu-sharing` auf `POST /auth/session`;
     `Cookie` und `Origin` kommen durch.
  3. Chatbot: `MCP_SESSION_URL`; bei `CORS_ALLOW_ALL=false` den Repository-Host in
     `CORS_ORIGINS`.
- Hinter dem Proxy der B-API: `WLO-Access-Block` am Proxy-Eintrag freigeben
  ([`uebergabe-betrieb.md`](../uebergabe-betrieb.md) §5).
