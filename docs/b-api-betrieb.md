# Betrieb mit der b-api

Stand: 19.11.2026 (Pakete D, K und N1, Plan `docs/plans/2026-11-17-b-api-delegation-und-upload.md`).

Der Chatbot spricht die b-api (Bildungs-API) für LLM, Einbettungen, Moderation, Sprache und
Aufträge (Kestra-Flows) an. Er läuft in zwei Betriebsarten. Beide gehen mit demselben Image.
Flows, die ins Repository schreiben, startet seit Paket K nicht der Chatbot selbst, sondern der
WLO-MCP über den b-api-Proxy des Repositorys (§5).

## 1 Betriebsarten

### Direkt mit `B_API_KEY`

- Das Widget ruft das Backend direkt auf, ohne b-api-Proxy davor.
- Jeder b-api-Aufruf trägt `Authorization: Bearer <B_API_KEY>`.
- Alle Personen teilen sich diesen Schlüssel, also auch Kosten und Grenzen. Die b-api kennt keine
  Person.
- Einstellung: `LLM_PROVIDER=b-api-openai` (oder `b-api-academiccloud`), `B_API_BASE_URL`,
  `B_API_KEY`, `B_API_KEY_MODE=auto` oder `static`.
- Ohne b-api geht es auch: `LLM_PROVIDER=openai` mit `OPENAI_API_KEY` (OpenAI nativ).

### Hinter dem b-api-Proxy mit Delegation

- Die Seite ruft den Chatbot über `/api/v1/proxy/badboerdichat/…` der b-api auf.
- Der Proxy hängt jeder Anfrage ein **Delegations-Token** an: `Authorization: Bearer bdt_…`.
  - Das Token ist verschlüsselt, seine Länge ist unbekannt. Der Chatbot nimmt 8 bis 8192
    sichtbare ASCII-Zeichen an.
  - Es gilt nur, solange die eingehende Anfrage läuft. Fehler oder Abbruch beenden es.
  - Es erlaubt LLM (`/api/v1/llm/**`) und lesende Repository-Pfade, aber **keine Jobs** und kein
    Schreiben.
- Der Chatbot reicht das Token bei jedem b-api-Aufruf des Zuges unverändert als
  `Authorization: Bearer` weiter.
  - Er setzt nie `X-API-KEY` daneben, denn der hätte Vorrang.
  - Er setzt nie `X-Edu-User-Id`, denn die b-api hat den Kopf abgeschafft.
  - Er loggt und speichert das Token nie.
- Einstellung wie oben, empfohlen `B_API_KEY_MODE=forward`: Ein Zug ohne gültigen Kopf bekommt
  dann 401, statt still unter `B_API_KEY` zu laufen.
- Ältere Proxy-Einträge mit `forwardApiKey` reichen statt eines Tokens einen Schlüssel. Der
  Chatbot behandelt ihn wie bisher (Art `schluessel`).

Woran der Chatbot die Art erkennt (`services/llm_auth.zug_art()`):

| Kopf `Authorization` | Art | Wert für b-api-Aufrufe |
|---|---|---|
| fehlt | `""` | `B_API_KEY` |
| `Bearer bdt_…` (gültige Form) | `delegation` | das Token |
| `Bearer bdt_…` in falscher Form (zu lang, Steuerzeichen, `bearer` klein) | `delegation` | keiner (kein Aufruf) |
| `Bearer <anderer Wert>` | `schluessel` | der Wert |

### Betriebsanzeige (Paket N1)

Welche Art zuletzt galt, zeigt der Chatbot selbst — ohne Werte:

- **Studio**, Übersicht, Statusleiste, Karte „b-api-Betrieb (diese Backend-Kopie)“: „Betriebsart
  erkannt: hinter dem b-api-Proxy (Delegation)“ bzw. „… (durchgereichter Schlüssel)“ oder „direkt
  (B_API_KEY)“, mit Zeit („zuletzt vor 3 Minuten“), `B_API_KEY_MODE` und unter `forward`
  „abgewiesen: N“.
- **`/api/health`** (nur mit Studio-Schlüssel), Feld `b_api`:
  `{"modus": "auto|static|forward", "zuletzt": "delegation|schluessel|direkt"|null, "zuletzt_am": "<ISO, UTC>"|null, "abgewiesen": 0, "warnungen": [...]}`.
  `abgewiesen` zählt Nutzerzüge, die `forward` mangels Kopf mit 401 abwies.
  Das offene `/health` bleibt `{"status":"ok"}` — Zeitpunkte verrieten dort die Nutzung.
- Gezählt werden nur **Nutzerzüge** über Chat und Agent (`api/turn_auth.uebernimm_zugang`), nicht
  Studio-Proben, Eval oder Lasttest (`ist_interner_zug`). `zuletzt_am` ist der Zeitpunkt des letzten
  solchen Zuges. Im Modus `static` ist jeder Zug `direkt`.
- **Je Prozess**: Mit mehreren Kopien zeigt jede Antwort die Sicht der Kopie, die antwortet; nach
  einem Neustart ist `zuletzt` leer, bis der erste Nutzerzug kommt.
- Warnungen:
  - `forward_ohne_token` — „B_API_KEY_MODE=forward gesetzt, aber kein Token gesehen“: mit
    b-api-Anbieter, seit dem Start kein durchgereichter Wert, und mindestens ein Nutzerzug bekam
    deshalb 401. Proxy-Eintrag und Adresse prüfen. Direkt nach dem Start ohne Abweisung keine
    Warnung.
  - `zugangsblock_fehlt` — „Zugangsblock fehlt hinter dem Proxy – allowedRequestHeaders prüfen“:
    mindestens 20 Delegationszüge, und bei keinem kam die Kopfzeile `WLO-Access-Block` (§3). Nur
    ein Hinweis: Solange sich niemand anmeldet, schickt das Widget den Block nicht — bei rein
    anonymer Nutzung ist das normal.

## 2 Rückfall-Regeln (Entscheid E5)

- **Mit Delegations-Token nie Rückfall auf `B_API_KEY`**, auch nicht bei einem unbrauchbaren
  Token. Sonst liefe der Zug still ohne Person.
  - Ein unbrauchbares Token führt zu keinem b-api-Aufruf. Die Person liest „Deine Anmeldung auf
    der Seite ist abgelaufen. Bitte lade die Seite neu.“
  - Mit `B_API_KEY_MODE=forward` weist schon der Endpunkt ab (401).
- **Nach dem Ende der Anfrage kein b-api-Aufruf mehr** (E4):
  - Legt der Client im Strom auf, rechnet der Zug nur noch bis zum nächsten b-api-Aufruf. Dort
    endet er und speichert, was da ist: die Nutzernachricht sowie die fertige Antwort oder den
    Vermerk „Die Verbindung zur Seite brach ab …“. Das Widget findet ihn beim Nachladen.
  - Ein Auftrag des Direktwegs wird bei Delegation nicht im Hintergrund bei der b-api beendet. Er
    läuft im Repository zu Ende. Einen Auftrag über den MCP bricht der Zug selbst ab
    (`wlo_cancel_flow`, nach dem Festschreiben; Paket K4).
- **Aufträge** (Kestra) über den **Direktweg** der b-api startet, prüft und bricht der Chatbot bei
  Delegation nicht ab (`llm_auth.darf_jobs()`): Das Token deckt keine Jobs, ein Start wäre eine
  sichere 401. „Stand prüfen“ sagt dann „nicht abrufbar“, ein Abbruch sagt ehrlich, dass der
  Auftrag weiterläuft. Schritte mit `repo_schreibt` gehen dagegen immer über den MCP — auch bei
  Delegation (§5).
- **`B_API_KEY` bleibt** für den Direktbetrieb und für interne Aufrufe ohne eingehende Anfrage:
  Studio, Eval, Lasttest, Vorwärmung, RAG-Import und den Flow-Katalog.
  - Das gilt, bis die b-api die offene Frage „Bleibt `B_API_KEY` außerhalb des Proxys erlaubt?“
    beantwortet.
  - Entfällt er, laufen diese Aufrufe über `LLM_PROVIDER=openai` (nativ).
- `B_API_KEY_MODE=static` liest den Kopf nie. Hinter einem Proxy mit Delegation läuft dann jeder
  Zug unter `B_API_KEY`, also ohne Person. Das ist nur für den Übergang gedacht.

## 3 Für den b-api-Admin (Proxy-Eintrag `badboerdichat`)

- `forwardDelegation: true` und `delegationScopes: [llm]`.
  - Mehr braucht der Chatbot nicht, denn WLO läuft über den MCP.
- `delegationLifetimeSeconds` mindestens 300 (längster Zug samt Agent-Schleife).
- `responseTimeout` mindestens 120 s.
- `allowedResponseContentTypes` mit `text/event-stream` (der Chat-Strom).
- `allowedRequestHeaders`: `WLO-Access-Block`, `X-Boerdi-Engine`, `Accept-Language`,
  `x-client-trace-id` und die B3-Köpfe.
  - Ohne `WLO-Access-Block` reißt die Auth-Kette Widget → Backend → MCP hinter dem Proxy.
- `pathToIgnore`: Studio-, Admin-, Eval- und Debug-Pfade (nicht in die öffentliche Doku).
- **Für den Kestra-Weg** (Jobs-Doku der b-api, 18.11.; gilt seit Paket K):
  - Der b-api-Schlüssel des **Repositorys** (den sein Proxy `/rest/bapi/**` setzt) braucht die
    Rolle `JOBS` bzw. das Privileg `JOB_RUN_EDUSHARING_CHATBOT_NODE-METADATA-WRITE`.
  - Er braucht außerdem die Rechte `EDU_SHARING_REPO_READ` und `EDU_SHARING_REPO_WRITE`.
  - Der Flow `node-metadata-write` braucht die Labels `bapi.expose: "true"` und
    `bapi.scopes: "edu-sharing-repo,edu-sharing-repo-write,llm"`, optional `bapi.maxRuntime`
    (etwa `PT30M`), und den Input `bapi_token` vom Typ SECRET.

## 4 Fehlerzuordnung

| Antwort der b-api | Bedeutung | Was der Chatbot tut |
|---|---|---|
| 401 bei einem LLM-Aufruf mit Delegation | Token ungültig, abgelaufen oder außerhalb des Bereichs | Satz „Deine Anmeldung auf der Seite ist abgelaufen. Bitte lade die Seite neu.“ (ohne Fehlernummer); nach dem Auflegen der Vermerk „Die Verbindung zur Seite brach ab …“ |
| 401 bei einem LLM-Aufruf ohne Delegation | Schlüssel abgewiesen | Satz mit Fehlernummer; Log `llm_schluessel_abgelehnt` (ERROR beim eigenen Schlüssel) |
| 403 bei einem Auftrag | Dem Schlüssel fehlt das Recht | Auftrag `abgewiesen`; Satz „Der Dienst hat den Auftrag abgelehnt.“ |
| 403 `EDU_USER_NOT_VERIFIED` | Konto bei der b-api nicht freigeschaltet | „… Dein Konto ist dort noch nicht freigeschaltet.“ |
| 403 `LEGACY_HEADERS` | Ein abgeschaffter Kopf (`X-Edu-User-Id`) kam an | „… Der Chatbot hat einen veralteten Kopf mitgeschickt (LEGACY_HEADERS) …“ (technischer Hinweis; ein Fehler der Einrichtung) |
| 400 `EDU_USER_REQUIRED` | Die Ursprungsanfrage hatte keine verifizierte Person | Auftrag `abgewiesen` (nicht `eingaben`). Über den MCP: „… Er hat keine angemeldete Person erkannt – vermutlich ist deine Anmeldung abgelaufen …“ (`auftragAbgelehntPerson`); auf dem Direktweg: „… Das geht nur über den WLO-Dienst mit deiner Anmeldung …“ (`auftragAbgelehntDirekt`) |
| 400 ohne bekannten Code | Eingaben passen nicht zum Flow | Auftrag `eingaben`; der Ablauf nimmt seinen Ersatzweg |
| kein Token mehr nach dem Auflegen | — (kein Aufruf) | Vermerk „Die Verbindung zur Seite brach ab …“ im Verlauf |
| kein gültiges Token bei der Moderation | — (kein Aufruf) | Moderation gilt als ausgefallen, `MODERATION_FAILURE_MODE` entscheidet (`open`: antworten, `closed`: freundliche Absage) |

Die Codes stehen in `services/auftraege/client.BEKANNTE_CODES`. Nur sie kommen ins Log, nie freier
Servertext. Die Sätze stehen in `i18n/bot_text.py` (de und en). Die LLM-Fälle ordnet
`services/fehlertext.antwort_fehlertext` zu.

## 5 Kestra-Flows über den MCP (Paket K)

Eine Person gilt bei der b-api nur, wenn das Repository für sie bürgt. Die Anmeldung der Person
hält der WLO-MCP, also startet er. Der Chatbot steuert weiter: wann, welcher Flow, Zustimmung.

- **Weg:** Backend → MCP (`wlo_start_flow`, mit dem Zugangsblock des Zuges) → Proxy des
  Repositorys `{WLO_REPOSITORY_URL}/rest/bapi/**` → b-api → Kestra. Der Proxy des Repositorys
  setzt seinen eigenen Schlüssel und eine signierte Assertion für die Person (30 s, an Methode,
  Pfad und Schlüssel gebunden). Der gestartete Job bekommt ein eigenes Token (`bapi_token`, bis
  zum Ende des Jobs) und schreibt damit als die Person. Das Delegations-Token braucht dieser Weg
  nicht.
- **Träger je Schritt** (`services/ablauf/auftrag_zug.traeger`):

| Schritt | Lage | Träger |
|---|---|---|
| mit `repo_schreibt` | MCP führt die Flow-Werkzeuge, Person bestätigt angemeldet (auch bei Delegation) | MCP |
| mit `repo_schreibt` | Werkzeuge fehlen, waren aber vor höchstens 10 Minuten da (Neustart des MCP) | keiner: „gleich noch einmal“, zurück an die Rückfrage |
| mit `repo_schreibt` | sonst | keiner: `auftragNurUeberWlo`, dann der Ersatzweg |
| ohne `repo_schreibt` | b-api eingerichtet und `darf_jobs()` (Schlüssel der Person, keine Delegation) | Direktweg wie vor Paket K |
| ohne `repo_schreibt` | sonst | keiner |
| jeder | ohne Anmeldung | keiner |

- **Start in zwei Schritten** (`services/auftraege/mcp_starter.py`): erst die Vorschau (der MCP
  prüft jeden Datensatz als die Person), dann derselbe Aufruf mit dem Bestätigungsschlüssel. Die
  Zustimmung der Person ist die Rückfrage direkt vor dem Schritt. Der Schlüssel erreicht nie das
  Modell, den Vorgang oder das Log.
- **`error.outcomeOpen` entscheidet:** `true` (auch keine Antwort, 202 ohne jobId) heißt, ein Job
  kann laufen. Der Chatbot startet dann nie neu und sagt „Stand prüfen“ (`auftragOffen`). `false`
  heißt, nichts lief.
- **Stand und Abbruch:** `wlo_flow_status` liefert „k von n fertig“ (gescheiterte getrennt);
  `unknown_job` (etwa nach einem Neustart des MCP) ist kein Fehlschlag, der Ablauf liest dann die
  Datensätze (`metadaten_lesen`). `wlo_cancel_flow` bricht im Zug ab.
- **jobId:** Über den Proxy des Repositorys kann jede bestätigte Person jeden Job lesen, dessen
  jobId sie kennt. Die jobId steht darum nur in `vorgang_auftraege.job_id`, nie in Text, Modell
  oder Log.
- **md und txt** gehen nicht an `node-metadata-write`: Der Flow scheitert dort (`FLOW_FAILED`,
  gemessen 19.11.). Der Satz `metadatenOhneText` sagt es der Person.
- **Flow-Katalog im Studio:** Das Studio hat keine Person. Die Vorschläge kommen weiter über
  `B_API_KEY`; ohne ihn gilt die Werksvorgabe `edusharing.chatbot/node-metadata-write`.

| Antwort des MCP | Was der Chatbot tut |
|---|---|
| `not_allowed` | „Dieser Auftrag ist hier nicht freigegeben – das ist eine Frage der Einrichtung.“, dann der Ersatzweg |
| `rate_limited` (429) ohne offenen Ausgang | zurück an die Rückfrage, „in etwa N Minuten noch einmal“ (`auftragVoll`) |
| `outcomeOpen: true` | kein neuer Start, „Stand prüfen“ liest die Datensätze (`auftragOffen`) |
| Werkzeug unbekannt (Neustart des MCP) | Fähigkeiten neu holen, „gleich noch einmal“ (`auftragNichtVerfuegbar`) |
| Flow `FAILED` (`FLOW_FAILED`, `TIMEOUT`) | „Der Auftrag in WLO ist fehlgeschlagen (…).“, dann der Ersatzweg |

**Einstellungen am MCP** (setzt das MCP-Team, beim Chatbot gibt es keine neue Variable): Der MCP
erkennt den b-api-Proxy des Repositorys beim Start selbst und bietet dann `wlo_start_flow`,
`wlo_flow_status`, `wlo_cancel_flow` und `wlo_list_flows` an. `WLO_BAPI_VIA_REPOSITORY=1` bzw. `0`
legt das fest, statt zu erkennen. `WLO_BAPI_FLOWS` schränkt die startbaren Flows nur ein;
`node-metadata-write` ist ab Werk startbar. Ein schreibender Flow braucht am Ablauf-Schritt
`repo_schreibt`, auf Seite des Chatbots die Freigabe im Studio („Abläufe → Kestra-Flows freigeben“,
mit `B_API_JOBS_FLOWS` als Obergrenze; `mcp_starter.flow_erlaubt` → `client.freigegebene_flows`) und,
falls die Liste am MCP gesetzt ist, einen Eintrag in `WLO_BAPI_FLOWS`.
