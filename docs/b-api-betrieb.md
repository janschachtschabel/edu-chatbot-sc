# Betrieb mit der b-api

Stand: 18.11.2026 (Paket D, Plan `docs/plans/2026-11-17-b-api-delegation-und-upload.md`).

Der Chatbot spricht die b-api (Bildungs-API) für LLM, Einbettungen, Moderation, Sprache und
Aufträge (Kestra-Flows) an. Er läuft in zwei Betriebsarten. Beide gehen mit demselben Image.

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
  - Ein ersetzter oder abgebrochener Auftrag wird bei Delegation nicht im Hintergrund bei der b-api
    beendet. Er läuft im Repository zu Ende. Den Abbruch im Zug über den MCP bringt Paket K.
- **Aufträge** (Kestra) startet, prüft und bricht der Chatbot bei Delegation nicht ab
  (`llm_auth.darf_jobs()`). „Stand prüfen“ sagt „nicht abrufbar“, ein Abbruch sagt ehrlich, dass der
  Auftrag weiterläuft. Das Token deckt keine Jobs, ein
  Start wäre eine sichere 401. Der Ablauf nimmt seinen Ersatzweg (`bei_fehler`). Der Start über den
  MCP mit der Repository-Anmeldung der Person folgt mit Paket K.
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
- `allowedRequestHeaders`: `WLO-Access-Block`, `Accept-Language`, `x-client-trace-id` und die
  B3-Köpfe.
  - Ohne `WLO-Access-Block` reißt die Auth-Kette Widget → Backend → MCP hinter dem Proxy.
- `pathToIgnore`: Studio-, Admin-, Eval- und Debug-Pfade (nicht in die öffentliche Doku).
- **Für den Kestra-Weg** (Jobs-Doku der b-api, 18.11.; gilt erst mit Paket K):
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
| 400 `EDU_USER_REQUIRED` | Die Ursprungsanfrage hatte keine verifizierte Person | Auftrag `abgewiesen` (nicht `eingaben`); „Aufträge mit deiner Anmeldung sind gerade nicht möglich – das wird gerade umgestellt.“ (bis Paket K) |
| 400 ohne bekannten Code | Eingaben passen nicht zum Flow | Auftrag `eingaben`; der Ablauf nimmt seinen Ersatzweg |
| kein Token mehr nach dem Auflegen | — (kein Aufruf) | Vermerk „Die Verbindung zur Seite brach ab …“ im Verlauf |
| kein gültiges Token bei der Moderation | — (kein Aufruf) | Moderation gilt als ausgefallen, `MODERATION_FAILURE_MODE` entscheidet (`open`: antworten, `closed`: freundliche Absage) |

Die Codes stehen in `services/auftraege/client.BEKANNTE_CODES`. Nur sie kommen ins Log, nie freier
Servertext. Die Sätze stehen in `i18n/bot_text.py` (de und en). Die LLM-Fälle ordnet
`services/fehlertext.antwort_fehlertext` zu.
