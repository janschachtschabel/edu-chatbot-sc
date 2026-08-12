# Bauvorschlag: Chatbot in fremden Oberflächen — ohne eine Zeile am Repository

Stand 2026-08-12 · Adressaten: **Entwickler des Browser-Plugins** und
**Betreiber des Repositories** · Grundlage: die Messungen dieses Tages, unten
mit Beleg.

## Kurzfassung

Der Chatbot lässt sich in edu-sharing-Oberflächen einbinden, **ohne dass am
Repository etwas gebaut, registriert oder konfiguriert werden muss** — und ohne
dass sich jemand ein zweites Mal anmeldet.

Das Prinzip in einem Satz: **Lesen läuft bei uns, Schreiben läuft im Browser.**

| | wer führt aus | Anmeldung | Rechte |
|---|---|---|---|
| Suchen, Prüfen, Vorschlagen | unser Backend über den MCP-Server | keine | die des Dienstkontos (**nur lesend**) |
| Ändern (Sammlung, Metadaten, Einreichen) | die Seite selbst, im Browser | **keine zweite** — die bestehende Sitzung | genau das, was die Person ohnehin darf |

Damit entfällt die gefährliche Zwischenform „ein festes Konto mit Schreibrechten
für alle": Änderungen entstehen unter dem Namen der handelnden Person, nicht
unter einem Sammelkonto.

Seit 2026-08-12 gibt es daneben eine **zweite Betriebsform** für den Fall, dass
das Repositorium den Chatbot selbst einbettet und der Seite ein Ticket
mitgeben kann (`ticket`-Attribut → §8): dann handelt der MCP-Server
serverseitig als die angemeldete Person — auch für die mehrschrittigen
Schreibfälle, die der Browser-Weg bauartbedingt nicht trägt.

## 1. Ausgangslage — gemessen, nicht angenommen

Alles hier ist am 2026-08-12 gegen `repository.staging.openeduhub.net` erhoben.

**Die Sitzungs-Cookies sind für fremden Code unlesbar und nicht übertragbar.**

| Cookie | Attribute |
|---|---|
| `INGRESSCOOKIE` | `Path=/edu-sharing; Secure; HttpOnly` |
| `JSESSIONID` | `Path=/edu-sharing; HttpOnly` |

* **`HttpOnly`** ⇒ kein JavaScript einer Seite kann den Wert lesen.
* **kein `SameSite`** ⇒ Browser behandeln das wie `Lax`; ein **fremd**
  eingebettetes iframe trägt die Cookies gar nicht mit.
* **`Path=/edu-sharing`, kein `Domain`** ⇒ host-eigen und pfadgebunden.

**Das Repository gibt einem Browser keinen weiterreichbaren Ausweis.** Aus der
eigenen API-Beschreibung (`/edu-sharing/rest/openapi.json`, 317 Pfade):

| Endpunkt | liefert | Folge |
|---|---|---|
| `GET /authentication/v1/validateSession` | `PrimaryLogin` (Status: `authorityName`, `validLogin`, `isGuest`, `toolPermissions` …) | **kein Ausweis** |
| `POST /authentication/v1/appauth/{userId}` | `{userId, ticket}` | nur für eine **registrierte Anwendung**; wäre Identitätsübernahme |
| `oauth2consent[/data]` | `clientId`, `state`, `scopes` | **kein Token-Endpunkt** in allen 317 Pfaden |

**Eine ungültige Sitzung scheitert lautlos.** Mit verfälschter `JSESSIONID`
antwortet die API `200` und meldet `authority: esguest` — zeichengleich mit
„gar kein Ausweis". Ein falsches `Basic` dagegen scheitert mit `401`.
⇒ **Jede Prüfung muss über die gemeldete `authority` gehen, nie über den
Statuscode.** Das gilt für jeden, der hier etwas baut.

**Ein Schreibzugriff verlangt kein CSRF-Token.** Drei `POST` auf die
Sammlungs-Schnittstelle — mit nichts als dem Sitzungs-Cookie, einmal ohne
Herkunftskopf, einmal mit der eigenen, einmal mit einer fremden — erreichten
alle drei den Handler des Repositories (`404`, dessen eigenes Fehlerobjekt).
Ein CSRF-Filter hätte sie vorher abgewiesen; er existiert auf dieser Route
nicht, und auch angeboten wurde kein Token. Damit genügt für den Schreibpfad
ein gewöhnliches `fetch` — ohne dass sich der Code irgendwoher etwas besorgen
müsste, das es beim Repository gar nicht zu holen gibt.

**Und ein solcher Schreibzugriff läuft auch wirklich durch.** Derselbe Lauf hat
mit nichts als dem Sitzungs-Cookie eine Sammlung angelegt (`200`) und sofort
wieder gelöscht. Der Satz, auf dem dieser ganze Vorschlag steht — *ein
gewöhnliches `fetch` aus der Seite kann schreiben* — ist damit gemessen, nicht
geschlossen.

Dass dabei auch die **fremde** Herkunft durchkam, ist kein offenes Scheunentor:
ein echter fremder `POST` aus einem Browser trüge die Cookies mangels `SameSite`
(⇒ `Lax`) gar nicht erst mit. Den Schutz leistet hier der Browser, nicht das
Repository — für uns ändert das nichts, für die Betreiber ist es eine Zeile
wert.

## 2. Warum es trotzdem geht

`HttpOnly` verbietet das **Lesen** des Cookies, nicht das **Benutzen**. Code,
der in der Seite des Repositories läuft, ist same-origin: ein gewöhnliches

```js
await fetch('/edu-sharing/rest/…', { method: 'POST', body })
```

trägt `JSESSIONID` und `INGRESSCOOKIE` automatisch mit — der Code fasst sie nie
an. Genau das ist der Weg. Er verlangt keinen Ausweis, keine Registrierung und
keine zweite Anmeldung.

## 3. Angebot an die **Betreiber des Repositories**

**Was Sie tun müssen: zwei Zeilen HTML.** Kein Endpunkt, keine Anwendung
registrieren, keine Änderung an edu-sharing.

```html
<script src="https://<chatbot-host>/widget/boerdi-widget.js" defer></script>
<boerdi-chat api-url="https://<chatbot-host>"></boerdi-chat>
```

So erscheint der Chat als Knopf unten rechts und erkennt Adresse und Titel der
Seite selbst. Soll er stattdessen einen Kasten Ihrer Oberfläche ausfüllen — ohne
eigenen Rahmen, ohne Kopfzeile —, genügt ein Attribut:
`embed-mode="frameless"`. Beide Varianten laufen als Demo unter
`/widget/` und `/widget/frameless`.

**Was Sie entscheiden:** mit welchem Konto der MCP-Server liest.

| Wahl | Empfehlung |
|---|---|
| anonym | funktioniert; sieht nur öffentliche Inhalte |
| **Dienstkonto ohne Schreibrechte** | **empfohlen** — bessere Treffer, kein Risiko |
| Dienstkonto *mit* Schreibrechten | nicht nötig und nicht empfohlen: in diesem Entwurf schreibt niemand über das Dienstkonto |

**Was Sie bekommen — als Zusagen, nicht als Absichtserklärung:**

1. **Die Sitzung Ihrer Nutzer verlässt den Browser nicht.** Unser Backend sieht
   sie nie, speichert sie nie, protokolliert sie nie. Es *kann* sie nicht sehen
   — die Cookies sind für uns weder lesbar noch übertragbar (§1).
2. **Änderungen tragen den Namen der Person**, die sie bestätigt hat — nicht den
   eines Sammelkontos.
3. **Nichts wird ohne Bestätigung geschrieben.** Der Chatbot zeigt jede
   beabsichtigte Änderung vorher an und fragt; ohne Zustimmung passiert nichts.
4. **Der Browser führt nur Anfragen an Ihr Repository aus**, gegen eine
   Erlaubnisliste von Methode und Pfad (§5), und zeigt vorher, was er tut.
5. Keine externen Schriften, keine Dritt-Dienste in der eingebetteten Ansicht.

*Stand dieser Zusagen (2026-08-12):* 1 und 2 folgen aus der Bauart und gelten
sofort; 3, 4 und 5 sind gebaut. Die Erlaubnisliste aus Zusage 4 steht im
Widget-Bündel und trägt heute zwei Einträge — Material in eine Sammlung legen
und wieder herausnehmen. Welche Aufrufe sie darüber hinaus führen soll, ist
Ihre Entscheidung (§7).

**Optional, später:** wird der Chatbot einmal per Reverse-Proxy unter
`/edu-sharing/…` eingehängt, verschiebt sich der Schreibpfad ins Backend, ohne
dass sich für Ihre Nutzer etwas ändert. Das ist eine Ingress-Regel, kein Bau —
und es ist **nicht** Voraussetzung für dieses Angebot.

## 4. Angebot an die **Entwickler des Browser-Plugins**

Ein Plugin kann mehr als eine Seite — und sollte hier trotzdem **weniger**
tun. Zwei Wege, wir empfehlen ausdrücklich den ersten:

### 4a. Content-Script in der Repository-Seite (empfohlen)

Das Plugin bindet unser Widget als Web-Komponente in die Seite ein. Der
Schreibpfad läuft dann wie in §3: same-origin, mit der bestehenden Sitzung,
ohne dass das Plugin je einen Ausweis in die Hand nimmt.

**Warum nicht der andere Weg:** ein Plugin *könnte* mit der `cookies`-Berechtigung
die `JSESSIONID` auslesen — `HttpOnly` schützt davor nicht — und sie an ein
Backend schicken. Wir raten davon ab und nehmen sie auch nicht entgegen: das
Plugin würde damit zum Verwahrer eines Ausweises, der volle Kontorechte trägt
und kein Ablaufdatum im Cookie hat. Der Gewinn wäre null — der Weg in 4a kann
dasselbe.

### 4b. Für Kontexte ohne edu-sharing-Seite

Sitzt das Plugin auf einer **fremden** Seite (Recherche, Qualitätsprüfung eines
beliebigen Fundstücks), gibt es keine Sitzung, die man nutzen könnte. Dort gilt:

* **Lesen** über unsere öffentliche Chat-Schnittstelle — funktioniert heute.
* **Schreiben** nur mit einer eigenen Anmeldung am MCP-Server (OAuth, vorhanden).
  Ein Absprung ist hier zumutbar, weil es keine bestehende Sitzung gibt, die man
  ihm ersparen könnte.

### Was wir dem Plugin schulden

| Baustein | Stand |
|---|---|
| Widget als Web-Komponente, einbindbar | **fertig** |
| Öffentliche Chat-Schnittstelle (`POST /api/chat`, SSE-Variante) | **fertig** |
| Seitenkontext (das Plugin meldet, worauf der Nutzer schaut) | **fertig** |
| Strukturierte Agent-Antwort (`POST /api/agent`, JSON nach Schema) | **fertig und für Plugins nutzbar** (seit 2026-08-12): schickt die Anmeldung der Person als `WLO-Access-Block` mit — kein Admin-Schlüssel im Browser. Gedrosselt wie der Chat |
| Vertrag „vorbereitete Anfrage" für den Schreibpfad | **fertig** (§5, E2–E4) — MCP beschreibt, Backend liefert als `prepared_write` aus, Widget setzt ab |

## 5. Was wir bauen

Vier Pakete, alle in unserem Code. Reihenfolge ist Abhängigkeitsreihenfolge.

**Stand 2026-08-12: E1–E4 alle fertig.** Der Weg steht von der bestätigten
Änderung bis zum abgesetzten Aufruf. Was noch offen ist, sind Entscheidungen und
kein Code — §7.

**E1 — Messung: verlangt edu-sharing ein CSRF-Token für Schreibzugriffe?**
**Erledigt 2026-08-12: nein** (§1, letzter Absatz). E3 und E4 bleiben deshalb so,
wie sie hier stehen — kein Token-Beschaffungsschritt, keine zusätzliche
Abhängigkeit vom Repository. Der Lauf mit `--schreiben` hat zusätzlich belegt,
dass ein Schreibzugriff allein mit dem Sitzungs-Cookie auch **durchläuft**
(Sammlung angelegt und sofort wieder gelöscht).

Nebenbefund für §3: das dabei benutzte Dienstkonto `WLO-Upload` **hat**
Schreibrechte — genau das, was das lesende Konto nicht haben sollte.

**E2 — MCP: Kuratierungs-Werkzeuge können *vorbereiten* statt ausführen.**
Ein zusätzlicher Ergebnis-Typ: statt die Änderung zu schreiben, gibt das
Werkzeug die **fertige Anfrage** zurück (Methode, Pfad, Rumpf) plus den schon
vorhandenen Vorschautext. Damit bleibt das Endpunkt-Wissen an genau **einer**
Stelle — der Browser bekommt nie eine zweite Implementierung.

*Stand 2026-08-12 — durchgängig gebaut für die **Sammlungs-Zugehörigkeit**:*

| Teil | Stand |
|---|---|
| `services/write/prepared-request.ts` — Typ + Regel „nur ans eigene Repository" | **fertig**, 10 Tests |
| `credential-gate.ts` — `resolveMayPrepare` + `requireWriteRoute` hinter `WLO_ALLOW_PREPARED_WRITES` | **fertig**, 4 Tests |
| Anfrage-Bauer `addToCollectionRequest` (Bauen vom Senden getrennt) | **fertig**, 3 Tests |
| `wlo_add_to_collection` gibt sie beim Bestätigen zurück (`structuredContent`) | **fertig**, 4 Tests |
| `removeFromCollectionRequest` + `wlo_remove_from_collection` | **fertig**, 5 Tests |
| übrige Kuratierungs-Werkzeuge | **liegen anders** — siehe unten |

**Warum die Reihe hier endet, und nicht aus Bequemlichkeit.** Eine vorbereitete
Anfrage ist **eine** Anfrage. Die beiden gebauten Vorgänge sind das auch; alles
Übrige nicht: Anlegen und Umbenennen schreiben den Titel über die
Sammlungs-Route und die Beschreibung über die Knoten-Route, weil die
Sammlungs-Route `cm:description` gemessen still verwirft — und beim Anlegen
hängt der zweite Aufruf an der ID, die erst der erste zurückgibt. Inhalt ändern
schickt die Felder gebündelt und fällt bei Ablehnung auf **ein Feld pro Aufruf**
zurück, damit im Bericht steht, welches nicht ankam. Aus dem Typ eine Liste zu
machen wäre eine Zeile; die Folge
wäre keine: der Browser bekäme damit einen **halb geschriebenen Datensatz** als
Zustand, den er nicht zurückrollen kann. Das ist eine Entscheidung für den
Nutzer, kein Rest.

Für „Herausnehmen" fiel dabei die Arbeit an, die den Umweg überhaupt
rechtfertigt: der Endpunkt nimmt die **Referenz-ID**, der Aufrufer nennt das
**Material**. Die Auflösung läuft bei uns; eine Seite, die sich die Anfrage
selbst zusammensetzte, schickte `DELETE …/references/{originalId}` — gemessen
2026-08-03: antwortet 200 und entfernt **nichts**. Genau deshalb wird die
Anfrage übergeben und kein Rezept veröffentlicht. Zwei ehrliche Ausgänge ohne
Anfrage gibt es dabei: das Material liegt nicht in der Sammlung, oder die Liste
war nicht lesbar — beide in denselben Worten wie der ausführende Weg, per Test
festgehalten.

`WLO_ALLOW_PREPARED_WRITES` steht jetzt in `DEPLOYMENT.md` — mit dem Satz, dass
die Route heute `wlo_add_to_collection` und `wlo_remove_from_collection` hat und
jedes andere Kuratierungs-Werkzeug weiter ablehnt. **Pro Werkzeug**, nicht pro Server: der
Schalter sagt, dass die Betreiberin den eingebetteten Weg überhaupt will; das
Kennzeichen am Werkzeug sagt, dass dieses eine ihn hat. Ohne beides bleibt alles,
wie es war.

Die Ergebnisform ist am SDK abgelesen, nicht geraten: `structuredContent` reist
**ohne** deklariertes `outputSchema`, weil der Server nur prüft, wenn eines da
ist (`server/mcp.js: if (!tool.outputSchema) return`) — ein deklariertes Schema
hätte jede Vorschau-Antwort ungültig gemacht, die trägt nämlich keine.

Drei Entscheidungen sind dabei am Bestand gefallen, nicht geraten:

1. **Vorbereiten ist keine vierte Schreib-Art, sondern eine zweite Frage.**
   `WriteMode` bleibt `user|service|none`. Sonst hieße „darf vorbereiten"
   irgendwann versehentlich „darf schreiben" — `writeRefusal()` prüft auf
   `!== 'none'`.
2. **Das Dienstkonto darf vorbereiten, anonym niemand.** Der Einwand, der dem
   gemeinsamen Konto das Schreiben verbietet (*eine Änderung unter einer
   Sammelidentität ist niemandem zuzuordnen*), trägt hier nicht: geschrieben
   wird im Browser, zugeordnet wird die Person. Anonym bleibt draußen, weil die
   Vorschau den Datensatz mit **unserer** Kennung liest — ein öffentliches
   „Vorbereiten" wäre ein Weg, Felder zu lesen, die dem Aufrufer nicht zustehen.
3. **Die vorbereitete Anfrage entsteht erst beim Bestätigen**, nicht bei der
   Vorschau. Der Bestätigungsschlüssel ist an den Hash der Änderung gebunden und
   genau deshalb eine Sperre gegen untergeschobene Anweisungen; gäbe die
   Vorschau die Anfrage schon mit heraus, könnte der Browser sie ausführen, ohne
   je einen Schlüssel einzulösen — die zweistufige Abnahme wäre Dekoration.

**E3 — Backend: den bestätigten Schritt ausliefern statt ausführen.**
Die Schreib-Abnahme (Vorschau → Rückfrage → Bestätigung) steht bereits. Neu ist
nur der letzte Zentimeter: im eingebetteten Betrieb wandert die vorbereitete
Anfrage in die Antwort.

*Präzisierung nach E2 (2026-08-12):* dieser Absatz hieß ursprünglich „statt an
den MCP zu gehen" — geschrieben, bevor E2 gebaut war. So ist es nicht. Das
Backend **entscheidet nichts**; der MCP entscheidet (an seinem Schalter und an
der Kennung des Aufrufers) und antwortet mit der Beschreibung statt zu
schreiben. E3 ist damit *erkennen und weiterreichen*, nicht *umleiten* — eine
Stelle weniger, an der zwei Systeme dieselbe Regel führen müssten.

*Stand 2026-08-12 — **E3 komplett**:*

| Teil | Stand |
|---|---|
| `domain/prepared_write.py` — lesen + prüfen (Vertrauensgrenze) | **fertig**, 9 Tests |
| `services/mcp/transport.py` reicht `structuredContent` durch | **fertig**, 2 Tests |
| `services/mcp/client.py` — Sammler je Zug (ContextVar wie `_query_metas`) | **fertig**, 3 Tests |
| `graph/nodes/setup.py` leert ihn zu Zugbeginn | **fertig** |
| `single_prepared_write` — höchstens eine je Zug | **fertig**, 3 Tests |
| `ChatResponse.prepared_write` + Verdrahtung in `turn_persist` | **fertig**, 3 Tests |

**Höchstens eine Anfrage je Zug**, und bei zweien **keine**. Der
Bestätigungs-Wall lässt je Zug einen Schlüssel einlösen; zwei Vorbereitungen
sind also kein Mehrfachfall, sondern ein gebrochener Zusicherungszustand — dann
ist nicht feststellbar, welcher Änderung ein Mensch zugestimmt hat. Eine nicht
ausgeführte Änderung kostet eine Wiederholung, eine falsch ausgeführte einen
Datensatz. Der Fall wird protokolliert, nicht verschwiegen.

Der Vertrag ist mitgezogen: `prepared_write` ist der einzige Zusatz gegenüber
§5.1, rein additiv mit Vorgabe `None`, und `docs/api/openapi-v1.json` wurde im
selben Zug neu erzeugt (`export_openapi.py --check` grün).

**Zwei Stellen verloren die Anfrage bisher still**, und beide waren echte
Befunde, keine Vermutungen: `transport.call_tool` normalisierte auf reine
Textblöcke (`{"result": {"content": …}}`) und warf `structuredContent` weg;
`call_mcp_tool` las ohnehin nur Text. Der strukturierte Teil reist jetzt nur
mit, **wenn** ein Werkzeug einen schickt — für die übrigen 40 Werkzeuge bleibt
die Ergebnisform Zeichen für Zeichen dieselbe, per Test festgehalten.

**Geprüft wird beim Lesen, nicht erst im Widget.** Was durch diese Naht geht,
setzt später ein fremder Browser mit den Rechten einer echten Person ab — damit
ist die MCP-Antwort hier *Eingabe*, auch wenn sie von unserem eigenen Server
kommt. Abgelehnt wird alles, was die Herkunft verlassen könnte: `//host/x` ist
protokoll-relativ und landet bei einem fremden Rechner, `/\host` wirkt in
Browsern genauso, dazu absolute Adressen, andere Methoden als POST/PUT/DELETE
und Steuerzeichen im Pfad. **Nicht** geprüft wird, ob dieser eine Aufruf
erlaubt ist — die Erlaubnisliste gehört ins Widget (E4), das ihn absetzt, und
eine zweite Kopie hier würde driften. Jede Seite bewacht ihre eigene Grenze.

*Entscheidung für den offenen Teil:* die Anfrage bekommt ein **eigenes Feld**
in `ChatResponse`, nicht einen weiteren `page_action`-Typ. `page_action` ist ein
einzelner Platz und schon von Canvas/Guide belegt — ein Zug, der eine Leinwand
öffnet *und* eine Änderung vorbereitet, überschriebe sich selbst. Und ein
Ausführer, der eine von vielen `action`-Sorten abarbeitet, lädt dazu ein, die
nächste Sorte am Riegel vorbei einzufügen.

**E4 — Widget: der Ausführer, und sein Riegel.**
Führt genau eine vorbereitete Anfrage je Bestätigung aus. Der Riegel ist der
wichtigste Teil des Pakets, denn ohne ihn wäre das Widget ein Universal-Ausführer
mit fremden Rechten.

*Stand 2026-08-12 — **E4 komplett**, alles in
`frontend/projects/ui/src/session/prepared-write.ts` (213 Z.) und einer
Verdrahtungs-Naht in der Chat-Shell:*

| Regel des Riegels | Wie sie hält |
|---|---|
| nur die **Herkunft des Repositories**, sonst nichts | die Adresse entsteht aus `origin() + path`; die Herkunft kommt nie aus der Anfrage. Eine *relative* Anfrage täte es fast auch — sie folgte aber einem `<base href>` der Gastgeberseite |
| nur eine **Erlaubnisliste** aus Methode + Pfadmuster, im Bündel | drei Einträge (`PUT`/`DELETE` auf `…/collections/-home-/<id>/references/<id>`, `POST` auf `…/suggestions/v1/-home-/<id>?type=AI&version=…`) = genau das, was E2 vorbereiten kann. Beidseitig verankerte Muster, Kennungen ohne `.`, `/`, `%` — kein Aufstieg, kein angehängter Pfadteil, keine zusätzliche Abfrage |
| Ergebnis über die gemeldete `authority`, nicht den Statuscode (§1) | **vor** dem Schreiben `GET …/rest/iam/v1/people/-home-/-me-`; ohne Person wird gar nicht erst geschrieben |
| abgelaufene Sitzung ⇒ ehrliche Meldung, kein stiller Gast-Modus | `esguest` ⇒ eigener Satz mit Handlungsanweisung, und die Anfrage bleibt ungesendet |

**Der Wer-bin-ich-Pfad wird aus der Anfrage abgeleitet**, nicht konfiguriert:
die Wurzel (`/edu-sharing`) steht in der Konfiguration des MCP-Servers, und ein
zweiter Knopf im Bündel liefe auseinander. Fest verdrahtet wäre sie in einer
anders benannten Installation still falsch. Die Ableitung greift erst *nach*
dem Riegel — die Frage kann also nirgends hinzeigen, wo die Anfrage nicht
ohnehin hindürfte.

**Fünf Ausgänge, fünf Sätze** (`prepared.done` · `blocked` · `signedOut` ·
`unreachable` · `failed`), in beiden Katalogen. Vier davon sagen dasselbe
Wichtigste — *es wurde nichts geändert* — und haben trotzdem je einen eigenen
Satz, weil sie verschiedene nächste Schritte verlangen. Bei Erfolg steht der
Satz des Werkzeugs, das die Änderung kennt (`done_message`); es weiß, welches
Material in welche Sammlung ging, hier ist davon nur eine Kennung übrig.

Der Vorgang wird **nicht abgewartet**: der Zug ist zu Ende, seine Antwort steht
im Verlauf, und das Eingabefeld darf nicht auf ein fremdes Repositorium warten.
Er schreibt sein Ergebnis selbst als Blase — in jedem der fünf Fälle.

*Wo E4 bewusst schweigt:* auf einer Seite, die gar kein Repositorium ist,
scheitert schon die Frage nach der Person → „nicht geklärt, wer du bist", kein
Schreibversuch. Und eine Kennung, die eine Prozent-Kodierung bräuchte, fällt
durch den Riegel — er schließt lieber zu viel als zu wenig.

**Nicht Teil der Pakete, weil bereits vorhanden:** Anzeige der Vorschau,
Rückfrage, Zustimmungs-Erkennung, Sicherheits- und Richtlinien-Prüfung,
Seitenkontext, Zweisprachigkeit.

## 6. Was wir bewusst **nicht** anbieten

| | warum nicht |
|---|---|
| Sitzung an unser Backend übergeben | technisch unmöglich (§1) — und wäre auch unerwünscht |
| Endpunkt beim Repository, der uns die Sitzung reicht | verlangt einen Bau am Repository; ausgeschlossen |
| `appauth` mit registrierter Anwendung | Identitätsübernahme per Bauart: wer es rufen darf, darf jeder sein. Nur mit einer Bindung zwischen behaupteter Nutzer-ID und tatsächlichem Besucher vertretbar — die kann eine eingebettete Seite nicht liefern |
| Dienstkonto mit Schreibrechten | jede Änderung liefe unter einem Sammelkonto, für jeden Besucher, ohne Zuschreibung |
| Sitzungs-Cookie im Browser-Plugin verwahren | voller Kontoausweis ohne Ablauf, ohne Gewinn gegenüber 4a |

## 7. Offen — Entscheidungen, keine Aufräumarbeit

1. ~~**`POST /api/agent` für Plugins.**~~ **Entschieden und gebaut 2026-08-12.**
   Der normale Weg herein ist jetzt die **Anmeldung der Person**
   (`WLO-Access-Block`), nicht mehr der Admin-Schlüssel; `AGENT_OPEN` öffnet für
   Testläufe, der Studio-Schlüssel bleibt für Server-zu-Server.

   Zwei Dinge daran sind wichtiger als die Reihenfolge der Prüfungen. Erstens:
   die Prüfung der Kopfzeile ist eine **Form-, keine Echtheitsprüfung** — belegen
   kann einen Zugangsblock nur der MCP-Server, und der ausdrücklich anonyme
   `wlo-anon.v1` ist wohlgeformt. Er wird deshalb ausgeschlossen; ohne das wäre
   der Riegel eine Formalie. Zweitens, und das ist der eigentliche Schutz: der
   Endpunkt trägt seither dieselbe **Drosselung** wie der Chat. Sein eigener
   Modul-Kommentar hatte den Tag benannt, an dem sie fällig wird — „wenn ein
   Gastgeber ohne Studio-Schlüssel zugelassen wird".

   Die **Rechte** ändert das nicht: was ein Lauf auf WLO darf, entscheidet
   weiterhin allein der MCP-Server, und Schreiben verlangt ohnehin eine echte
   Person. Belegt in `tests/test_agent_api.py` („Wer darf rufen").
2. **Erlaubnisliste des Schreibpfads.** Stand 2026-08-12: **drei Einträge** —
   Material in eine Sammlung legen, wieder herausnehmen, **Metadaten
   vorschlagen** (Nutzer-Entscheid: „ermitteln und vorschlagen ja, mit Abnahme
   durch die Person"). Die Abnahme leistet der vorhandene Bestätigungs-Wall;
   dazu war nichts zu bauen.

   Beim Vorschlag ist die **Abfrage Teil der Regel**: `type=AI` ist die
   Herkunftsangabe, die das Repositorium mitspeichert. Im Widget-Muster
   festgeschrieben heißt das, dass über diesen Weg kein Vorschlag abgesetzt
   werden kann, der einen Menschen als Urheber behauptet.

   Was weiter offen bleibt und **kein** Listeneintrag mehr ist: Anlegen,
   Umbenennen, Inhalt ändern brauchen mehrere Anfragen nacheinander — dafür
   fehlt ein Entwurf, nicht eine Zeile (§5, E2).
3. **Reverse-Proxy-Weg (§3, optional) — bewusst vertagt** (Nutzer 2026-08-12:
   „erstmal offen lassen"). Das ist eine Entscheidung, keine offene Aufgabe: es
   fehlt nichts, was ohne ihn nicht ginge.

   Damit ihn niemand neu herleiten muss — die Abwägung in zwei Sätzen. **Gewinn:**
   hinge der Chatbot unter der Adresse des Repositoriums, wanderte das Schreiben
   zurück in unser Backend, und im Browser passierte weniger. **Preis:** von da
   an schickte der Browser die Sitzungs-Cookies des Repositoriums auch an uns —
   Zusage 1 aus §3 („die Sitzung verlässt den Browser nicht, wir können sie gar
   nicht sehen") gälte dann nur noch als Versprechen, nicht mehr bauartbedingt.

   *Wann er wieder auf den Tisch gehört:* wenn ein Schreibfall gebraucht wird,
   der **mehrere** Anfragen nacheinander verlangt (Anlegen, Umbenennen,
   Inhalt-Ändern — siehe Punkt 2). Für die gibt es im heutigen Entwurf keinen
   Weg, und der Proxy wäre einer. Solange nur einzelne Anfragen anstehen, kostet
   er mehr, als er bringt.

## 8. Zweite Betriebsform: das Repositorium bettet ein und reicht ein Ticket

*(Nutzer-Entscheid 2026-08-12: „wir sollten diesen Weg unterstützen, da er
praktisch genutzt wird von der anderen App" — gemeint ist der md-editor, dessen
Einbettungs-Anmeldung über `?ticket=…` in Produktion läuft. Gebaut am selben
Tag; MCP-Server + Widget, Backend unverändert.)*

E1–E4 beantworten die Frage „Chatbot in einer edu-sharing-Seite, **ohne** dass
das Repositorium von uns weiß". Diese Betriebsform beantwortet die andere: das
Repositorium **will** den Chatbot einbetten und kann etwas beisteuern, das sich
ein Browser nie selbst holen kann (§1) — den Ausweis der angemeldeten Person,
als edu-sharing-**Ticket**. Damit handelt der MCP-Server serverseitig als diese
Person: alle Werkzeuge, auch die mehrschrittigen Schreibfälle, für die der
E4-Weg bauartbedingt keinen Weg hat (eine vorbereitete Anfrage ist EINE
Anfrage, §5). Und es ist der bessere Tausch als der vertagte Reverse-Proxy aus
§7.3: ein Ticket ist ein begrenzter, widerrufbarer Ausweis — keine
Sitzungs-Cookies, die plötzlich auch an uns gingen.

**Der Weg** (jede Station prüfbar):

1. Die edu-sharing-Seite rendert das Widget und templatet das Ticket der
   angemeldeten Person hinein — **Attribut, nicht URL**: nur die Seite selbst
   kann es liefern, ein Link von außen nicht (keine Sitzungs-Fixierung per
   Link).

   ```html
   <boerdi-chat api-url="https://chat.example.org" ticket="TICKET_…"></boerdi-chat>
   ```

2. Die Hülle liest das Attribut **einmal** und tilgt es sofort aus dem DOM
   (`widget.component.ts`, `ngOnInit`) — die md-editor-Regel „ein Ticket darf
   nirgends liegenbleiben", dort für die Adresszeile, hier fürs DOM.
3. Sobald `mcp_auth_base` aus dem Config-Bündel da ist, tauscht die Shell das
   Ticket still beim MCP-Server (`session/ticket-login.ts`):
   `POST /auth/ticket` prüft es an der gemeldeten **authority** (nie am
   Statuscode, §1) und antwortet mit einem gewöhnlichen `wlo2.`-Zugangsblock,
   dessen Inhalt diesmal das Ticket ist (`k: 'ticket'` → upstream
   `EDU-TICKET <ticket>` statt `Basic`). Deterministische Block-Id = Hash des
   Tickets, damit Seiten-Neuladen die Registry nicht flutet. Doku:
   `wlo-mcp-server-sc/docs/AUTH.md` §5c.
4. Ab hier ist **nichts** mehr besonders: derselbe Speicher, dieselbe
   Kopfzeile je Zug durchs Backend (formgleicher Block → **null**
   Backend-Änderung; auch `/api/agent` nimmt ihn als persönliche Anmeldung),
   derselbe Abmelde-Knopf, dieselbe Widerrufung (`/auth/revoke-all` erwischt
   Ticket-Blöcke über das Authority-Label mit).
5. Scheitert der Tausch (Ticket abgelaufen, Ausgabe abgeschaltet), bleibt das
   Widget still: der Anmelde-Knopf steht auf „Anmelden" — der Rückfall auf die
   Handanmeldung, den der md-editor „hybrid fallback" nennt — und eine
   `console.warn`-Zeile nennt der Betreiberseite den Grund.

**Parameter für die Einbindung im Repositorium:**

| Was | Wert |
|---|---|
| Widget-Attribut | `ticket="<edu-sharing-Ticket>"` — einmalig beim Rendern; wird nach dem Lesen aus dem DOM entfernt |
| MCP-Server | `WLO_AUTH_PRIVATE_KEY` gesetzt (Zugangsblock-Ausgabe an); ohne ihn antwortet `/auth/ticket` 404 und das Widget bleibt anonym |
| Backend/Studio | nichts — `mcp_auth_base` muss (wie für den Anmelde-Knopf ohnehin) auf den MCP-Server zeigen |
| Ticket besorgen | Sache des Repositoriums (serverseitig templaten). Browser können keins holen — §1, gemessen |

**Ehrliche Grenzen:**

* Diese Betriebsform verlässt den Rahmen „ohne Repo-Änderung" — die Seite muss
  das Widget einbetten und das Ticket templaten. Deshalb ist sie ein **eigener
  zweiter Modus neben** E1–E4, kein Ersatz: das Browser-Plugin (§4) behält den
  E4-Weg, denn im Browser gibt es keinen Ticket-Spender (§1: kein Endpunkt
  gibt einem Browser einen weiterreichbaren Ausweis).
* Die Live-Probe steht aus: dass edu-sharing `EDU-TICKET <ticket>` als
  `Authorization` annimmt, belegt die Produktions-Praxis des md-editors
  (`md-editor-merged/server.js`, `/api/login`; `server/edu-sharing-api.js`) —
  ein eigener Lauf braucht ein echtes Ticket, und das kann nur eine
  einbettende Seite liefern.
* Stirbt die Repository-Sitzung, stirbt das Ticket: jeder Werkzeug-Aufruf
  endet dann 401, der Zugang endet mit der Sitzung — gewollt, nur ohne
  eigenen Satz im Chat (der Anmelde-Status zeigt es).

## 9. Belege

* Cookie-Attribute, Verhalten bei ungültiger Sitzung, Verhalten ohne
  `INGRESSCOOKIE`: `wlo-mcp-server-sc/docs/plans/2026-08-12-relay-credential-limiter.md`,
  Abschnitt „P2 — session credential"; wiederholbar mit
  `wlo-mcp-server-sc/scripts/session-cookie-probe.mjs` (gibt Namen, Wertlängen,
  Attribute, Status und `authority` aus — nie einen Wert).
* Fehlender Ausweis-Endpunkt: `/edu-sharing/rest/openapi.json`, Schemata
  `PrimaryLogin`, `AuthenticationToken`, `OAuth2Consent`.
* CSRF-Freiheit des Schreibpfads (E1): derselbe Plan, Abschnitt „Does a write
  need a CSRF token?"; wiederholbar mit `wlo-mcp-server-sc/scripts/csrf-write-probe.mjs`
  (Normallauf ändert nichts; `--schreiben` legt eine Sammlung an und löscht sie
  sofort). Die Einstufung „403 heißt *unentschieden*, nicht *Riegel*" ist in
  `tests/csrf-write-verdict.test.ts` festgenagelt.
* Schreib-Abnahme (Vorschau/Bestätigung), auf der E3 aufsetzt:
  `boerdi-chat/docs/plans/2026-08-11-schreib-abnahme.md`.
