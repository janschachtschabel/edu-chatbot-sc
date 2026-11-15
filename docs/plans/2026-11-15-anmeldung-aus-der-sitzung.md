# Anmeldung aus der WLO-Sitzung übernehmen (2026-11-15)

Anlass: Nachricht des MCP-Entwicklers „Für das Chatbot-Team: die Anmeldung aus der WLO-Sitzung
übernehmen“ (MCP-Repo, `docs/plans/2026-11-15-chatbot-anmeldung-aus-der-sitzung.md`) und der
Auftrag des Nutzers vom 15.11.: Das Widget soll ohne eigene WLO-Anmeldung erkennen, ob es in
einer Seite des Repositorys mit angemeldeter Sitzung sitzt, deren Rechte übernehmen und an
Backend und MCP weitergeben, so sicher wie möglich.

## Ausgangslage

- Der MCP tauscht neu eine Repository-Sitzung gegen einen Zugangsblock: `POST /auth/session`
  („Weg B“). Der Pfad ist am MCP ohne Vorgabe aus und muss auf dem Host des Repositorys
  unterhalb von `/edu-sharing` eingehängt sein, nur dorthin schickt der Browser das
  Sitzungs-Cookie. Das Cookie selbst sieht das Widget nie.
- Der Chatbot kann zwei Wege: Ticket der Seite (`ticket`-Attribut, „Weg A“) und die Anmeldung
  von Hand (OAuth-Fenster). Beide enden in einem Block, der je Anfrage in der Kopfzeile
  `WLO-Access-Block` ans Backend reist; das Backend gibt ihn nur an den MCP weiter und speichert
  ihn nicht.
- Ein Block aus der Sitzung hat dieselbe Form. Am Backend ändert sich am Zugangsweg nichts.

## Ablauf (neu)

```
Config-Bündel nennt die Tausch-Adresse ─► gleiche Herkunft wie die Seite? ─ nein ─► nichts tun
                                                    │ ja
        GET  {Herkunft}/{Wurzel}/rest/iam/v1/people/-home-/-me-   (wer ist hier angemeldet?)
                                                    │ Person (nicht Gast)
        POST {Herkunft}{Pfad}/auth/session   credentials: same-origin, Körper {}
                                                    │ 200 {block, authority, displayName?}
        authority == Person der Seite? ─ nein ─► Block verwerfen
                                                    │ ja
        Block im Arbeitsspeicher ─► je Anfrage als WLO-Access-Block ans Backend ─► Bearer an den MCP

vor jedem Abruf mit Block:  GET …/-me-  ─► noch dieselbe Person? ─ nein ─► Block weg, neu tauschen
```

## Entscheide

| Nr. | Entscheid | Grund |
|---|---|---|
| SA-1 | **Erkennen über die Herkunft.** Das Backend nennt im Config-Bündel die Adresse des Tauschs (`MCP_SESSION_URL` → Feld `mcp_session_url`). Das Widget geht den Weg nur, wenn die Adresse dieselbe Herkunft hat wie die Seite. | Keine Anfrage auf fremden Seiten; ein Schalter für den Betrieb; die Einbindung braucht kein neues Attribut. |
| SA-2 | **Riegel im Widget.** Der Pfad muss auf `/auth/session` enden und nur aus schlichten Stufen bestehen; die Anfrage entsteht aus `Herkunft der Seite + Pfad`. Der Wer-bin-ich-Pfad wird aus der ersten Stufe abgeleitet (`/edu-sharing`), nicht eingestellt. | Die Config kommt über das Netz. Sie darf das Widget nicht zu einem beliebigen POST mit den Cookies der Seite bringen. Dieselbe Regel wie bei der vorbereiteten Änderung. |
| SA-3 | **Erst fragen, wer da ist.** Gast oder keine Antwort: kein Tausch. | Kein Aufruf am MCP für Gäste (dessen Begrenzung zählt je Adresse). Geprüft wird die gemeldete Person, nie der Status. |
| SA-4 | **Person vergleichen.** Nennt der Tausch eine andere `authority` als die Seite, wird der Block verworfen. | Empfehlung des MCP-Entwicklers; schützt vor einem falsch eingehängten Pfad. |
| SA-5 | **Block aus der Sitzung nur im Arbeitsspeicher.** Kein `sessionStorage`. Nach dem Neuladen tauscht das Widget neu. | Regel des MCP-Entwicklers. Der Tausch kostet nichts, ein abgelegter Block überlebte einen Wechsel der Person. Ticket- und Hand-Blöcke bleiben wie bisher im `sessionStorage` (die Hand-Anmeldung ließe sich sonst nicht halten). |
| SA-6 | **Reihenfolge:** Ticket vorhanden → Weg A, sonst Weg B. Die Person der Seite ersetzt einen mitgebrachten Block. | Empfehlung des MCP-Entwicklers; dieselbe Regel wie beim Ticket. |
| SA-7 | **Erneuern:** nach Ablauf (12 h) still neu tauschen; nach einer Abweisung einmal; scheitert das, weiter ohne Anmeldung mit einem Satz. | Wie beim Ticket. Ein Tausch vor dem Ablauf verlängert nichts. |
| SA-8 | **Abmelden** widerruft den Block und merkt sich das für den Tab: kein Tausch von selbst. „Anmelden“ nimmt danach wieder die Sitzung; ist dort niemand angemeldet, bietet ein Satz die Anmeldung von Hand an. | Sonst wäre die Person nach dem nächsten Laden wieder angemeldet. Endgültig abmelden kann nur das Repository. |
| SA-9 | **Wer handelt, steht am Knopf** („Abmelden — angemeldet als …“). Kein Satz im Chat. | Die Person hat nichts angeklickt und soll trotzdem sehen, unter welchem Namen der Chatbot arbeitet. Ein Satz je Neuladen wäre Lärm. Der Name bleibt im Arbeitsspeicher. |
| SA-10 | **Der Block reist weiter in der Kopfzeile `WLO-Access-Block`.** Kein Feld im JSON-Körper. | Nicht jeder Abruf mit Block hat einen JSON-Körper: Der Verlauf ist ein GET, der Upload geht als Formular (`multipart`). Hinter dem Proxy der B-API muss der Betrieb die Kopfzeile freigeben (`allowedRequestHeaders`). |
| SA-11 | **Backend:** eine Einstellung, ein Feld. Eine unbrauchbare Adresse beendet den Start mit einer Meldung. Das Feld bekommt nur, wer auch die Anmelde-Adresse bekommt. | Ein Tippfehler soll auffallen, nicht still den Weg abschalten. |
| SA-12 | **Schreiben bleibt hinter der Zustimmung.** | Unverändert: Vorschau, Rückfrage, Freigabe. Die übernommene Sitzung ändert daran nichts. |
| SA-13 | **Vor jedem Abruf, der den Block trägt, fragt das Widget, wer auf der Seite angemeldet ist** (`session/sitzungs-wache.ts`). Das gilt für Züge wie für Verlauf, „Meine Vorgänge“, Ablage und Dokumente. Zeigt die Seite einen Gast, fällt der Block weg, mit einem Satz im Chat. Zeigt sie eine andere Person, fällt er weg und das Widget tauscht neu. War vorher niemand angemeldet und jetzt jemand, tauscht es ebenfalls. Keine Antwort ist kein Urteil: Der Block bleibt. Ein 401 des Repositorys zählt wie ein Gast. | Nachtrag aus den Reviews. Im Repository laufen Anmelden, Abmelden und Ummelden innerhalb derselben Seite, ohne Neuladen. Ohne die Frage trüge der alte Block weiter unter dem alten Namen, und wer sich nach dem Laden anmeldet, bliebe im Chat Gast. Ob das Repository dabei die Sitzungs-Kennung wechselt, ist nicht gemessen; die Prüfung macht die Frage unerheblich. |
| SA-14 | **Grenzen der Wache.** Die Frage wartet höchstens 3 s, danach ein angestoßener Tausch höchstens 5 s; dann geht der Abruf ohne Anmeldung hinaus. Ein Abruf, der während eines laufenden Tauschs kommt, wartet bis zu 10 s (erst die Sperre der Anmeldung, dann der Tausch). Eine Antwort gilt 2 s, eine Folge von Abrufen fragt einmal. Scheitert ein Tausch, gleich wer ihn anstieß, versucht es die Wache 5 Minuten nicht von selbst; liegt es an der Einrichtung (Pfad fehlt, Seite nicht freigegeben, andere Person genannt), bis zum Neuladen oder einem Klick auf „Anmelden“. Eine Anmeldung von Hand und ein Tab nach „Abmelden“ sind nicht ihr Fall. | Die Wache darf selbst kein Hindernis werden und das Anmelde-Budget der Adresse am MCP nicht verbrauchen. Kosten: auf Seiten des Repositorys ein kleiner Abruf je Zug, auch für Gäste. |
| SA-15 | **Für wen der Block gilt, steht neben dem Block** (im selben Modul, nicht in der Shell). **Eine neu gebaute Instanz des Widgets übernimmt einen Block aus der Sitzung nicht:** Sie verwirft ihn beim Start und tauscht selbst. | Bis das Config-Bündel den Weg nennt, hängt die Wache an keinem Abruf; ein geerbter Block ginge so lange ungeprüft hinaus, auch wenn die Seite inzwischen jemand anderen zeigt. Der neue Tausch kostet nichts. Ein Block von Hand oder aus einem Ticket bleibt über den Neubau erhalten. |

## Voraussetzung am Repository-Host

Der Weg braucht einen Pfad unter `/edu-sharing` auf dem Host des Repositorys. Anders geht es
nicht: Das Sitzungs-Cookie trägt `Path=/edu-sharing` und `HttpOnly`, und die Schnittstelle des
Repositorys gibt keinem Browser ein Ticket (gemessen am 15.11.: 321 Pfade; `appauth` bleibt
ausgeschlossen). Der md-editor nutzt dasselbe Muster und läuft so auf Staging
(`/edu-sharing/services/md-editor/`, eigenes Ingress-Objekt aus seinem Chart,
`config.auth.cookie.enabled`).

**SA-16: Der Pfad führt zu unserem Backend, nicht zum MCP.** Unser Chart legt das Ingress-Objekt
an (`sessionIngress` in der Werte-Vorlage für Team 6) und leitet genau
`/edu-sharing/services/boerdi/auth/session` unverändert an unser Backend (kein `rewrite-target`;
das Backend nimmt den Pfad selbst an). Das Backend reicht den Tausch server-zu-server an `POST /auth/session` des MCP weiter
(`services/mcp/sitzung_tausch.py`). So steuert der Betrieb des Chatbots den Weg selbst, und der
MCP kann bleiben, wo er ist (sein Staging-Server läuft auf einem eigenen Rechner; eine
Ingress-Regel im Cluster zeigt dorthin nicht ohne Weiteres). Das Widget ändert sich nicht:
`MCP_SESSION_URL` nennt nur eine andere Adresse.

- **Riegel im Backend:** nur über den Host aus `MCP_SESSION_URL` (sonst 404, also nicht über den
  Host des Chats); nur `POST` mit JSON; `Origin` gleich der Herkunft aus `MCP_SESSION_URL`;
  genau eine `JSESSIONID` (zwei verschiedene weist schon die Route ab, eine Nachbar-Subdomain
  könnte sonst wählen, wessen Sitzung gilt); weitergereicht werden nur diese und höchstens ein
  `INGRESSCOOKIE`, kein `Authorization`; zurück gehen nur die Felder der Tauschstelle und nur
  Status, die ein Urteil sind (sonst 502); Gesamtfrist 8 s; ohne `MCP_SESSION_URL` 404.
- **Kein `rewrite-target`:** Das Backend nimmt den Pfad am Repository-Host unverändert an
  (`PFAD_AM_REPOSITORY`). Ein `rewrite-target` stellte bei ingress-nginx alle Pfade des Hosts
  auf Regex um, auch die von edu-sharing.
- **Budget (SA-17, MCP 1.3.0):** Mit unserem Client-Schlüssel zahlen Tausch und Abmelden beim
  MCP aus dem Protokoll-Budget des Schlüssels (3 × rpm je Minute, geteilt mit `/mcp` und
  `/auth/status`). Den Schutz vor vielen Sitzungen (200 verschiedene in 10 Minuten) zählt der
  MCP je Adresse, die wir in `X-Forwarded-For` nennen. `Origin` und `Content-Type` sind
  außerhalb eines Browsers frei wählbar, die Host-Prüfung ist nur Tiefenverteidigung. Deshalb
  begrenzt das Backend die ganze Anlage mit `MCP_SESSION_EXCHANGE_RPM` (Vorgabe 20, damit vom
  Topf der Adresse 10 für das Abmelden bleiben) und jede Adresse mit 10 je Minute. Gezählt wird
  im gemeinsamen Speicher der Drossel (im Cluster Valkey, über alle Repliken).
  - **Weit nur auf Wunsch (Review SA-17):** Das Backend sieht nicht, ob der MCP 1.3.0 läuft
    und den Schlüssel kennt; `MCP_CLIENT_KEY` ist im Betrieb schon seit dem 7.11. gesetzt. Eine
    Automatik „Schlüssel da → weit“ hätte vor dem MCP-Update das Abmelden ausgehungert. Darum
    setzt der Betrieb den Wert erst nach dem MCP-Update hoch (Empfehlung 100). Ohne Schlüssel
    gilt höchstens 20. Über 20 steigt die Grenze je Adresse auf 60 (Schulklasse hinter einem
    Router).
  - **Warum 100, nicht 200:** Jeder Werkzeugaufruf kostet am Protokoll-Budget drei POSTs
    (eigene Sitzung je Aufruf); bei 300 Werkzeugaufrufen je Minute blieben von 1080 rund 180.
  - **Voraussetzung am Proxy des MCP:** Er muss unseren `X-Forwarded-For` durchlassen
    (Traefik `forwardedHeaders.trustedIPs` mit der Ausgangsadresse des Backends), sonst zählt
    der MCP alle Personen als eine Adresse.
- **Preis:** Das Cookie läuft im Transit durch unser Backend, wie beim Server des md-editors. Es
  wird weder gespeichert noch protokolliert.
- **Keine neue Umgebungsvariable für SA-16.** Die Route gilt, sobald `MCP_SESSION_URL` gesetzt
  ist. SA-17 bringt `MCP_SESSION_EXCHANGE_RPM` (siehe Budget oben).
- **Alternative bleibt möglich:** Läuft der MCP eines Tages im Cluster des Repositorys, kann
  `MCP_SESSION_URL` auch direkt auf seinen eingehängten Pfad zeigen (`WLO_SESSION_MOUNT_PATH`
  am MCP); das Widget merkt keinen Unterschied.

Ohne den Pfad bleibt der Weg aus; der Chatbot-Teil liegt dann still.

## Risiken

- **Der Block ist für Skripte der Seite erreichbar, das Cookie nicht.** Das Sitzungs-Cookie ist
  `HttpOnly`; ein Skript auf der Seite kann es benutzen, aber nicht mitnehmen. Den Block kann es
  mitnehmen und damit von außen am MCP als die Person handeln, solange die Sitzung im
  Repository lebt.
  - Der Block liegt nicht im Web-Speicher und hängt nicht an `window`: Das Widget-Bündel steht
    seit dem 2026-11-15 beim Bau in einer Hülle (`frontend/scripts/build-widget-huelle.mjs`).
    Vorher lief es als gewöhnliches Skript ohne Hülle; seine Variablen und Funktionen waren
    Eigenschaften von `window`, auch die Funktion, die den Block liest (Befund des Reviews).
    Die Hülle ist Hygiene, kein Schutz: Ein Skript der Seite kann `fetch` oder `XMLHttpRequest` umbiegen und den
    Block aus der Kopfzeile lesen.
  - Ein Skript derselben Seite kann die Tauschstelle auch selbst rufen. Der Schutz liegt
    deshalb nicht im Versteck, sondern darin, wo der Weg gilt: nur auf der Herkunft, die der
    Betrieb einträgt, und am MCP nur für freigegebene Seiten.
  - Ein mitgenommener Block nützt höchstens bis zum Widerruf oder bis zum Ende der 12 Stunden.
    Bis 2026-11-15 trug der nächste Tausch derselben Sitzung die alte Kennung wieder ein, und
    ein früher mitgenommener Block galt wieder. Der MCP-Entwickler hat das auf unseren Wunsch
    behoben: Der Block trägt den Zeitpunkt seiner Eintragung, und die Prüfung vergleicht ihn.
  - Der Weg gehört deshalb nur auf Seiten, deren Skripte der Betreiber verantwortet (das
    Repository selbst).
- **Wechsel der Person ohne Neuladen.** Gelöst durch SA-13. Was bleibt:
  - Antwortet das Repository nicht binnen 3 s, bleibt der Block für diesen Abruf.
  - Eine Antwort gilt 2 s; in diesem Fenster und zwischen Frage und Absenden fällt ein Wechsel
    nicht auf.
  - Mehrere Widgets auf einer Seite teilen sich den Block. Verwirft oder tauscht eines, zeigt
    der Knopf des anderen bis zu seinem nächsten Abruf den alten Stand.
  - Das Gespräch bleibt beim Wechsel der Person stehen: Die neue Person sieht den Verlauf der
    alten und schreibt im selben Gespräch weiter. Das ist beim Ticket genauso. Ob das Widget
    dann ein neues Gespräch beginnen soll, ist eine offene Entscheidung (offene-befunde §2).
- **Abrufe vor dem Config-Abruf.** Ob der Weg gilt, weiß das Widget erst mit dem Config-Bündel.
  Ein Abruf davor läuft ohne Anmeldung (einen Block aus der Sitzung gibt es dann noch nicht,
  SA-15). Ab dem Bündel warten Abrufe auf den laufenden Tausch. Nach dem Tausch lädt das
  Widget den Stand der Person nach.

## Nicht in diesem Paket

- Der MCP hinter dem Proxy der B-API; eine Person über die B-API ausweisen (beides laut
  MCP-Entwickler noch nicht möglich).
- Ein Feld im JSON-Körper für den Block.
- Ticket-Blöcke nur im Arbeitsspeicher halten (wäre möglich, eigener Schritt).
- Das Widget-Bündel in eine Hülle setzen, damit seine Variablen nicht an `window` hängen.
  Nachgezogen als eigener Schritt am 2026-11-15:
  [`2026-11-15-widget-buendel-in-huelle.md`](../aenderungen/2026-11-15-widget-buendel-in-huelle.md).
- Ein Rückfall vom Ticket auf die Sitzung: Mit `ticket` im Attribut gilt nur Weg A, auch wenn
  das Ticket abgelaufen ist.

## Umsetzung

1. Widget: `session/session-login.ts` (Riegel, Wer-bin-ich, Tausch, Vergleich), `mcp-access.ts`
   (Block im Arbeitsspeicher), Config-Feld durch `guide-mode-config.ts` / `guide-boot.ts` /
   Hülle, Chat-Shell (stiller Start, Erneuern, Abmelden, Knopf), Texte de/en.
2. Backend: `MCP_SESSION_URL` (Prüfung in `domain/mcp_herkunft.py`), Feld `mcp_session_url` in
   `GET /api/config/guide-mode`.
3. Doku: Einbindung, Anmeldung und Risiken, Betriebsübergabe (Proxy-Kopfzeilen), Deploy-Vorlagen,
   Antwort an den MCP-Entwickler, Änderungsnotiz.
4. Unabhängiges Review, volle Suite, Upload als PR.
