# Paket D: der Chatbot an der Delegation der b-api (2026-11-18)

Plan: `docs/plans/2026-11-17-b-api-delegation-und-upload.md`, §5 Paket D (Entscheide E3–E6).
Betriebsdoku: `docs/b-api-betrieb.md` (neu).

## Warum

Seit dem 10.11. reicht der b-api-Proxy statt eines Schlüssels ein **Delegations-Token**
`Authorization: Bearer bdt_…` durch. Das Token ist verschlüsselt und unbekannt lang. Es gilt nur,
solange die eingehende Anfrage läuft, und deckt LLM und lesende Repository-Pfade, aber keine Jobs.
`X-Edu-User-Id` ist abgeschafft. Der Chatbot nahm bisher höchstens 512 Zeichen an, fiel bei einem
verworfenen Kopf still auf `B_API_KEY` zurück und rief die b-api auch nach dem Ende der Anfrage
auf (Nachlauf nach Auflegen, Abbruch im Hintergrund).

## Was

### D1 Token annehmen, kein Rückfall (`services/llm_auth.py`)

- Form `Bearer` + 8–8192 sichtbare ASCII-Zeichen (vorher 512).
- Neu `zug_art()`: `delegation` (Präfix `bdt_`), `schluessel`, `""`.
- `b_api_schluessel()`: Bei Art `delegation` gilt nur das Token. Fehlt es (unbrauchbare Form) oder
  ist es beendet, folgt die neue Ausnahme `KeinDelegationsToken` (`grund`: `unbrauchbar` bzw.
  `beendet`), nie `B_API_KEY`.
- Ein Kopf `bearer bdt_…` in falscher Form bleibt Art `delegation` ohne Wert. Er wird nicht
  weitergereicht und fällt nicht zurück.
- Der Stand des Zuges ist ein geteiltes Objekt im `ContextVar`. So erreicht das Auflegen auch die
  Kopien in Tasks und LangGraph-Knoten (`beende_delegation`, `delegation_beender`).
- Das Token steht nie im `repr`, im Log oder im Text der Ausnahme (Test).
- `speech_proxy.speech_enabled()` fängt `KeinDelegationsToken` ab. Die Sprachauskunft ist kein Zug
  und darf nicht mit 500 enden.
- `turn_auth.uebernimm_llm_schluessel` ist unverändert. `static` liest den Kopf nicht, `forward`
  weist auch ein unbrauchbares Token mit 401 ab (Tests ergänzt).

### D2 Kein Personen-Kopf (`services/auftraege/client.py`, `services/mcp/auth.py`, `services/mcp/anmeldung.py`)

- `_person()` und `X-Edu-User-Id` sind überall entfernt: Start, Stand, Abbruch, Datei. Damit
  entfällt auch der Parameter `extra_koepfe` von `_anfrage`.
- `auth.benutzername()`, `Befund.benutzer`, `_kopfwert` und der Parameter `benutzer` von
  `setze_bestaetigung` sind entfernt. Sie dienten nur diesem Kopf (grep: keine weiteren Nutzer).
  Die Bestätigung ist wieder ein Tripel.
- `BEKANNTE_CODES` += `EDU_USER_REQUIRED`, `LEGACY_HEADERS`.
- 400 mit Code `EDU_USER_REQUIRED` wird `abgewiesen` mit diesem Code statt `eingaben`.
- Findet `_koepfe()` kein Token mehr (`KeinDelegationsToken`), meldet der Client
  `AuftragFehler("fehler")`. Es folgt kein Aufruf.
- Test: In keiner Anfrage (Start, Stand, Abbruch, Datei) steht `X-Edu-User-Id` oder `X-API-KEY`.

### D3 Auflegen im Strom (`api/sse.py`, `api/chat.py`, `graph/nodes/respond.py`)

- **Gewählte Mechanik:** Der vorhandene Weg „zu Ende rechnen“ (Paket 7, P2) bleibt. Beim Auflegen
  markiert der Strom das Token als beendet.
  - Der Zug läuft weiter, bis er die b-api bräuchte. Dort wirft `b_api_schluessel()`
    `KeinDelegationsToken`, ein Aufruf findet also nicht statt.
  - Die vorhandenen Fehlerwege speichern dann, was da ist: Die Nutzernachricht steht schon im
    Verlauf (`persist_user`). Scheitert die Antwort, wird `respond` zum Satz
    `error.connectionLost`. Scheitert der Zug außerhalb, speichert `_fehlerblase` den Satz.
  - Ist die Antwort schon fertig und braucht der Rest keine b-api mehr, wird sie normal gespeichert.
  - Kein harter Abbruch (`cancel`) mitten im Speichern, keine Daten verloren.
- Der Strom bindet den Beender beim Start im Kontext der Anfrage. Ein Abschluss des Generators
  kann später in fremdem Kontext laufen.
- `_stream_turn` schließt den inneren Strom jetzt mit `contextlib.aclosing`. Vorher schloss ihn erst
  das Aufräumen des Generators, also spät und in fremdem Kontext. Der Nachlauf selbst bleibt
  unverändert.
- Im Weg „abbrechen“ (Agent, Chat ohne Verlauf) wird das Token ebenfalls beendet, bis der Abbruch
  greift.
- `KeinDelegationsToken` ist ein erwarteter Ausgang: INFO statt Traceback (`chat._run_impl`,
  `respond`).
- Ohne Delegation ist alles unverändert (Test: zwei b-api-Aufrufe, keine Fehlerblase).

### D4 Kein Abbruch im Hintergrund (`services/ablauf/zug_basis.py`, `services/auftraege/client.py`)

- `bei_der_b_api_abbrechen` und `client.abbrechen_im_hintergrund` starten bei Art `delegation`
  keine Task. Es gibt nur `logger.info` ohne Daten: Der Auftrag läuft im Repository zu Ende.
- Paket K ersetzt das durch einen Abbruch im Zug über den MCP.

### D5 Sätze (`i18n/bot_text.py`, `services/ablauf/auftrag_zug.py`, `services/fehlertext.py`)

- `action.ablauf.auftragAbgelehntPerson` (`EDU_USER_REQUIRED`): bis Paket K „Aufträge mit deiner
  Anmeldung sind gerade nicht möglich – das wird gerade umgestellt.“ (de/en; Review-Befund 5).
- `action.ablauf.auftragAbgelehntTechnik` (`LEGACY_HEADERS`): technischer Hinweis (de/en).
- `error.delegationExpired`: „Deine Anmeldung auf der Seite ist abgelaufen. Bitte lade die Seite
  neu.“ (de/en).
- `error.connectionLost`: der Vermerk nach dem Auflegen (de/en).
- **LLM-401:** Die Stelle ist `services/fehlertext.antwort_fehlertext`, eine Stelle für Muster-Weg,
  Werkzeugschleife und Chat-Fehlerblase.
  - Sie nimmt bei Art `delegation` und einer 401 in der Kette (`llm_ereignisse.ist_abgelehnter_schluessel`)
    den Neuladen-Satz ohne Fehlernummer.
  - Bei `KeinDelegationsToken` nimmt sie `connectionLost` bzw. `delegationExpired`.
- **Agent-Weg** (Nachtrag, Entscheid des Koordinators): `AgentRun.fehler` (neu, nie im `repr`)
  trägt die Ausnahme des LLM-Aufrufs, an dem der Lauf endete (`services/agent_loop.py`).
  - `agent_abschluss.antwort_oder_ersatz` reicht sie an `antwort_fehlertext` durch.
  - Damit kommt auch dort bei einer 401 mit Delegation `error.delegationExpired` ohne Fehlernummer.
  - `KeinDelegationsToken` steht in der Schleife auf INFO statt mit Traceback im Log.

### D6 Doku

- `docs/b-api-betrieb.md` (neu): Betriebsarten, Rückfall-Regeln (E5), Admin-Liste (Plan §6),
  Fehlerzuordnung.
- `deploy/.env.example`: nur Kommentare (`forwardDelegation`, Modus `static`/`forward`, kein
  `X-Edu-User-Id`, keine Aufträge bei Delegation).

## Abweichungen vom Plan (selbst entschieden)

1. **Obergrenze 8192 statt 4096:** Die Tabelle in §5 nennt 4096, E3 und der Auftrag nennen 8192.
   Genommen wurde 8192.
2. **Bei Delegation startet der Direktweg keine Aufträge** (`auftrag_zug.starter()` gibt `None`;
   vom Koordinator am 18.11. bestätigt).
   - Das steht nicht in D, folgt aber aus E1/E2: Das Token deckt keine Jobs, also wäre jeder Start
     eine sichere 401.
   - Die Person läse dann „Anmeldung abgelaufen, bitte neu laden“, und Neuladen hülfe nicht.
   - Bis Paket K nimmt der Schritt seinen Ersatzweg (`bei_fehler`).
   - Folge: Der gewünschte 401-Satz greift bei Aufträgen derzeit nicht (kein Start). Er gilt für
     LLM-Aufrufe.
3. **Unbrauchbares Delegations-Token:** Der Plan setzt „kann nicht vorkommen“ voraus. Es wird
   trotzdem abgesichert: kein Aufruf, kein Rückfall, Neuladen-Satz; bei `forward` 401 schon am
   Endpunkt.
4. **D3 ohne `cancel`:** Statt den Zug sofort abzubrechen, endet er vor dem nächsten b-api-Aufruf
   (siehe D3). Ein `cancel` hätte mitten in einem DB-Schreiben treffen und die schon fertige
   Antwort verlieren können.

## Review-Befunde behoben (18.11.)

Review: 0 CRITICAL, 0 MAJOR, 6 MINOR, 2 NIT. Jeder Befund wurde an der Quelle geprüft und mit Test
zuerst behoben (`tests/test_paket_d_review.py`, Studio `fields.spec.ts`).

1. **`hat_zug_schluessel()` galt als „kann Jobs“.** Neu `llm_auth.darf_jobs()`: ein Zug-Schlüssel
   ist da, und es ist keine Delegation.
   - Genutzt in `auftrag_zug` (`starter`, `abbrechen`, `pruefen`), `abbruch_zug._satz`,
     `api/ui_vorgaenge.loeschen` und zusätzlich `api/ui_auftrag` (Stand-Abfrage der Leiste,
     dieselbe Klasse).
   - Bei Delegation greifen jetzt `auftragNurHierAbgebrochen` bzw. `auftragNichtAbrufbar`, und
     `auftrag_laeuft_weiter` ist wahr.
   - Die Test-Nähte wurden in den bestehenden Tests von `hat_zug_schluessel` auf `darf_jobs`
     umgestellt.
2. **`tool_loop`:** `KeinDelegationsToken` ist ein erwarteter Ausgang (INFO, kein Traceback).
3. **Moderation:** `moderate()` fängt `KeinDelegationsToken` um `_moderation_target()`.
   - Der Befund ist „ungeprüft“ (`{}`, Zähler `fehler`), wie bei jedem Ausfall. Danach entscheidet
     `MODERATION_FAILURE_MODE`.
   - Kein Aufruf, kein Rückfall, keine 500 mehr, etwa bei `POST /api/ui/dokumente`.
   - Gewählt statt einer 401 im Endpunkt, weil die Moderation alle Ausfälle so behandelt.
4. **401 nach dem Auflegen:** Neu `llm_auth.delegation_beendet()`. `fehlertext` nimmt dann
   `error.connectionLost` statt `delegationExpired`.
5. **`auftragAbgelehntPerson`:** ehrlich bis Paket K (siehe D5).
6. **Studio** (`frontend/projects/studio/src/app/i18n/catalogue/fields-ablaeufe.ts`): Der Hinweis
   zu `repo_schreibt` nennt `X-Edu-User-Id` nicht mehr (de/en). Der Flow läuft mit den Rechten der
   angemeldeten Person, das Repository weist sie nach (Start über seinen Proxy). Neue Spec in
   `fields.spec.ts`.
7. **NIT:** Die Meldung „Auftrag nicht gestartet: Delegation …“ in `starter()` steht auf DEBUG.
8. **NIT:** `llm_auth.beende_delegation()` ist entfernt (nur Tests nutzten es). Tests und Docstrings
   nutzen `delegation_beender()`.

## Deploy-Hinweise

- Keine Migration, keine neue Variable.
- Mit dem Proxy-Eintrag `forwardDelegation` (Admin-Liste in `docs/b-api-betrieb.md` §3) empfiehlt
  sich `B_API_KEY_MODE=forward`.
  - Mit `static` liefe jeder Zug ohne Person unter `B_API_KEY`.
  - Mit `auto` läuft ein Direktaufruf ohne Kopf weiter unter `B_API_KEY`.
- Widget-Bundle: nicht betroffen (nur Backend).
- Nach dem Umstellen auf Delegation starten Abläufe keine Kestra-Aufträge mehr über den Chatbot.
  Der Themenbaum aus eigenen Inhalten nimmt seinen Ersatzweg, bis Paket K da ist.

## Offene Punkte

- **`POST /api/chat` (ohne Strom), bleibt bewusst so:**
  - Legt der Client hier auf, bemerkt der Endpunkt das nicht (Starlette meldet das Auflegen nur dem
    Strom).
  - Nach dem Auflegen beendet die b-api das Token. Folgende b-api-Aufrufe enden mit 401, und
    gespeichert wird, was da ist.
  - Das ist der Rückfallweg des Widgets und selten.
- **Kestra bei Delegation:** erst mit Paket K (MCP-Weg). Bis dahin keine Aufträge hinter dem
  Delegations-Proxy.
- **Offene Fragen an die b-api** (Plan §7): ob `B_API_KEY` außerhalb des Proxys erlaubt bleibt, ob
  SSE durch den Proxy kommt (30-s-Abbruch?), Länge und Form von `bdt_…`.
