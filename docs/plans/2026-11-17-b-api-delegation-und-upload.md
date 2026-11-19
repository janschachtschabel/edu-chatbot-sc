# Plan 2026-11-17 (Chatbot): b-api-Delegation, Kestra über den MCP, ein Upload-Weg

Stand 18.11.: **freigegeben**, Paket D in Arbeit. Dieser Plan gilt für den **Chatbot** (Pakete D, K,
U). Der Teil des MCP steht als eigener Plan in `2026-11-17-mcp-wuensche-b-api-flows.md`. Grundlage: Rückmeldung des b-api-Entwicklers
(„(Update) B-API Personen-Nachweis bei Delegation“, 17.11.), Bestandsaufnahme Chatbot und MCP
(17.11.), MCP-Entwurf `wlo-mcp-server-sc/docs/plans/2026-11-15-b-api-betrieb.md`, Rückmeldung des
Nutzers zum Upload-Feld (17.11.).

## 1 Ziel

1. Chatbot und MCP laufen **hinter dem b-api-Proxy** (Delegations-Token) **und weiter ohne ihn**
   (direkt, `B_API_KEY` bzw. OpenAI nativ) — für alle Dienstaufrufe, nicht nur Kestra.
2. **Kestra-Flows sind wieder startbar**, mit den Rechten der angemeldeten Person.
3. Das Upload-Feld hat **einen** verständlichen Weg: Dateien wählen → *wo verarbeiten* → hochladen.
   Kleine Mengen laufen **hier im Chat** (begrenzt, im Studio einstellbar), große und alles, was ins
   Repository gehört, **über edu-sharing und Kestra**. Ergebnis ist in beiden Fällen derselbe
   Datenstrom (Teile im Vorgang), aus dem Abläufe, freier Chat und Werkzeuge greifen.

## 2 Was sich bei der b-api geändert hat (Kurzfassung)

- Eine Person gilt nur, wenn das **Repository** für sie bürgt: Aufruf über `…/rest/bapi/**`, der
  Proxy des Repositorys setzt eine signierte Assertion (30 s, an Methode, Pfad und Schlüssel gebunden).
- Dienste hinter der b-api bekommen statt eines Schlüssels ein **Delegations-Token**
  `Authorization: Bearer bdt_…`: nur durchreichen, nie loggen/speichern, nur während der Anfrage,
  nie zusammen mit `X-API-KEY`. Es erlaubt LLM und lesende Repository-Pfade — **keine Jobs,
  kein Schreiben**.
- `X-Edu-User-Id` ist abgeschafft (mit Schlüssel → 403 `LEGACY_HEADERS`, mit Token ignoriert).
  Ohne verifizierte Person: 400 `EDU_USER_REQUIRED` für alle Repository-Scopes.

Nachtrag 18.11. (Jobs-Doku der b-api): Ein über `/rest/bapi/**` gestarteter Flow bekommt ein
eigenes Token (bis Job-Ende, höchstens 12 h) mit den Scopes aus seinem Label `bapi.scopes` —
darunter auch **Schreiben** (`edu-sharing-repo-write`: Metadaten, Sammlung zuordnen) und **Dateien**
(`edu-sharing-repo-content`: Inhalt ersetzen, Material mit Datei in einem Ordner anlegen). Flows
können FILE-Inputs per Multipart annehmen (50 MB je Datei, 10 Dateien, 100 MB je Start). Für diesen
Plan bleibt das Hochladen beim MCP-Stapel (Multipart durch den Repository-Proxy ist ungeprüft,
die Beispielseite sah 415); „Hochladen über einen Flow“ ist ein späterer Kandidat.
`GET /api/v1/jobs/{id}` liefert bei Schleifen `progress` (started, running, succeeded, warning,
failed), mit `?details=true` auch `iterations` — das nutzt der Chatbot für „k von n fertig“.

## 3 Bestand (gemessen im Code, 17.11.)

**Chatbot** (`boerdi-chat/backend`):
- b-api nur über `llm_auth.b_api_schluessel()` (ContextVar des Zuges, sonst `B_API_KEY`), immer als
  `Authorization: Bearer`, nie `X-API-KEY`. Aufrufer: LLM/Router/Stream, Embeddings, Moderation,
  Speech, Jobs (`services/auftraege/client.py`), Flow-Katalog (`flow_katalog.py`, nur `B_API_KEY`).
- Eingelesen in `api/turn_auth.py:146-174`, Form `Bearer [!-~]{8,512}` (`llm_auth.py:32`).
- Ein Zug läuft ganz in seiner HTTP-Anfrage (auch der Stream). **Ausnahmen**: der Nachlauf nach
  Auflegen des Clients (`api/sse.py:67-118`) und `abbrechen_im_hintergrund`
  (`ablauf/zug_basis.py:351-365`) — beide nutzen den Schlüssel **nach** der Anfrage.
- `X-Edu-User-Id` nur im Job-Client (`client.py:224-228`).
- Studio, Eval, Lasttest, Warmup, Ingest nutzen `B_API_KEY` (lesen `Authorization` nicht).
- Auth-Kette: Widget → Kopf `WLO-Access-Block` → Backend → MCP als `Authorization: Bearer <Block>`;
  Repository-Sitzung kommt per Sitzungs-Tausch (`api/sitzung.py`, `mcp/sitzung_tausch.py`) zum MCP.

**MCP** (`wlo-mcp-server-sc`): ruft die b-api nur für die Textextraktion (`X-API-KEY`), kennt
`/bapi/**` nicht, hält die Repository-Anmeldung der Person (Sitzung/Ticket/Basic) je Anfrage
(`auth/credential.ts`, `auth/upstream-auth.ts`), Stapel-Ablage `wlo_prepare_file_batch` …
`wlo_store_batch_manifest` (legt `ccm:io` an, startet keine Erschließung), lesen per
`get_node_details` / `get_wlo_content_text`. Läuft heute ohne b-api.

**Upload** (`ui_upload`): drei Wege — „Senden“ (nur Namen), „Lesen lassen“ (nur Strukturdokumente,
`POST /api/ui/dokumente`, höchstens 5 je Sitzung), „Übertragen“ (MCP-Stapel). Inhaltsdateien werden
lokal **nie** gelesen; ohne WLO-Erschließung bleiben nur Dateinamen (`inhalte_aus_dateien`).

## 4 Entscheide (selbst getroffen, Nutzer kann kippen)

| Nr | Entscheid | Grund |
|---|---|---|
| E1 | **Kestra startet der MCP** über `{WLO_REPOSITORY_URL}/rest/bapi/api/v1/jobs/…` mit der Anmeldung der Person; **der Chatbot steuert** (wann, welcher Flow, Freigabe). | Nur der MCP hält die Repository-Sitzung (Auth-Kette Widget → Backend → MCP); das Repository bürgt dann für die Person. Das Delegations-Token kann keine Jobs. Der Entscheid vom 07.11. („Chatbot steuert“) bleibt inhaltlich. |
| E2 | Auch **Stand, Abbruch und Ergebnisse** eines Jobs über den MCP; der Chatbot ruft `/api/v1/jobs` nicht mehr, sobald der MCP es kann. Der alte Direktweg bleibt nur als Rückfall für Flows ohne Repository-Bezug. | Job-Pfade liegen außerhalb der Delegations-Scopes. |
| E3 | Token-Form: `Bearer` + 8–8192 sichtbare ASCII-Zeichen (das Token ist laut Jobs-Doku ein verschlüsseltes JWE, Länge unbekannt); Art `delegation` bei Präfix `bdt_`, sonst `schluessel`. **Mit Delegations-Token nie Rückfall auf `B_API_KEY`** im selben Zug. | Länge des Tokens unbekannt; ein still verworfenes Token liefe sonst ohne Person. |
| E4 | Im Delegationsbetrieb **kein b-api-Aufruf nach dem Ende der Anfrage**: Nachlauf nach Auflegen beendet den Zug ohne weitere b-api-Aufrufe (gespeichert wird, was da ist); `abbrechen_im_hintergrund` wird ein Abbruch im Zug über den MCP (E2). | Token endet mit der Anfrage. |
| E5 | `B_API_KEY` bleibt für den Direktbetrieb und interne Aufrufe (Studio, Eval, Warmup, Ingest, Flow-Katalog), bis die b-api die offene Frage „Rückfall-Schlüssel“ beantwortet. Entfällt er, laufen diese über `LLM_PROVIDER=openai` (nativ). | Abwärtskompatibel; keine Annahme über die Antwort. |
| E6 | Fehlercodes: `EDU_USER_REQUIRED`, `LEGACY_HEADERS`, `EDU_USER_NOT_VERIFIED` in `BEKANNTE_CODES`; 401 mit Delegations-Token → eigener Satz („Anmeldung der Seite abgelaufen, bitte neu laden“). | Person soll den Grund verstehen. |
| E7 | Upload-Feld: nach der Auswahl **eine Frage „Wo verarbeiten?“** als Chips (Stil wie die Stufen-Frage), je Chip eine Zeile Erklärung; dann **ein** Knopf „Hochladen“. Zusätzlich klein: „Nur Namen senden (nichts hochladen)“. | Ein Weg, klare Wahl, Datenschutz-Ausweg bleibt. |
| E8 | **Hier im Chat**: alle gewählten lesbaren Dateien (pdf, docx, txt, md) werden gelesen und als Sitzungsdokumente gehalten (`aufbewahrung_h`). Strukturdokumente: Volltext; Inhalte: zusätzlich je Datei kurze Angaben (Titel, Beschreibung ≤ 400 Zeichen, bis 8 Schlagworte) per LLM → Teil `metadaten` mit `quelle: chatbot`. Grenzen im Studio: `lokal_max_dateien` (Vorgabe 10, 1–30), `lokal_max_mb_gesamt` (Vorgabe 50, 1–200). | Löst „nur Dateinamen reicht nicht“ auch ohne Anmeldung; begrenzt Kosten. |
| E9 | **In WLO ablegen**: Stapel-Ablage wie heute; danach startet der Chatbot über den MCP den Metadaten-Flow für die **Inhalte**; **Strukturdokumente** bekommen keinen Flow, ihr Volltext kommt aus dem Repository (`get_wlo_content_text`). Ergebnis: Teile `ablage`, `metadaten` (`quelle: wlo`), `strukturdokument` (`quelle: wlo`). | Lange, asynchrone Arbeit dorthin, wo die Daten bleiben. |
| E10 | Vorauswahl: angemeldet und mehr Dateien als `lokal_max_dateien` → „In WLO“ vorgewählt, „Hier“ gesperrt mit Grund; nicht angemeldet → „Hier“ vorgewählt, „In WLO“ gesperrt mit „braucht Anmeldung“; sonst „Hier“. Ein Ablauf kann die Orte per Modul-Argument `orte` einschränken. | Kein Raten für die Person. |
| E11 | **Ein Datenstrom**: Teile `struktur` (immer), `strukturdokument`, `metadaten`, `ablage` (nur WLO), jeweils mit `quelle`. Abläufe, freier Chat (`dokument_lesen`, `[ARBEITSSTAND]`) und Werkzeuge greifen nur darauf zu. Das Upload-Feld kennt kein Ziel (TG-1 bleibt). | Generisch, mit und ohne Abläufe. |
| E12 | Ablauf „Themenbaum erstellen“: Fragen `wlo_frage`/`schnell` entfallen (der Ort ist im Feld gewählt); `dateien_weg` verzweigt nur nach vorhandenen Teilen. | Doppelte Frage weg. |

## 4a Nachtrag 18.11. — Kestra zuerst (Nutzer-Auftrag)

Auftrag: möglichst viel Umwandlung in den Kestra-Flow verlegen; Strukturdokumente dort mitnehmen und
sich merken, welcher Knoten das Strukturdokument war; sauber mit dem Stand des Flows arbeiten
(Warten mit gesperrter Eingabe, Stand, Info, Abbruch); Rückkehr zu einem begonnenen Ablauf innerhalb
der Fristen; Umwandlung im Chatbot nur für kleine Mengen, ohne WLO-Anmeldung oder wenn zwingend.

| Nr | Entscheid (ersetzt E8–E10, wo sie widersprechen) |
|---|---|
| E13 | **Mit WLO-Anmeldung und Flow-Werkzeugen des MCP ist „In WLO ablegen und erschließen“ die Vorgabe — für jede Menge.** „Hier im Chat“ bleibt Zweitwahl bis `lokal_max_dateien` („nur für diese Sitzung, schnell“). **Ohne Anmeldung:** „Hier im Chat“ bis zur Grenze; darüber nur Namen, mit dem Hinweis, dass mit Anmeldung alles erschlossen wird. Zwingend lokal: die Person wählt es ausdrücklich (soll nicht ins Repository), oder der WLO-Weg ist gerade nicht verfügbar (Grund wird genannt). |
| E14 | **Strukturdokumente gehen beim WLO-Weg mit ins Repository** (Rolle `structure` in der Stapel-Ablage; `ablage` trägt `rolle: struktur` je Eintrag; Teil `strukturdokument` mit `quelle: wlo`, `ref` = nodeId). **Der Metadaten-Flow läuft über Inhalte UND Strukturdokumente** (hebt den älteren Entscheid „nur Inhalte“ auf): so liefern auch Strukturdokumente Fach, Bildungsstufe und Schlagworte für die Vorbelegung. Den **Volltext** eines Strukturdokuments erzeugt das Repository beim Hochladen; der Chatbot liest ihn per `get_wlo_content_text` (nur GET). Fehlt er noch, wartet der Ablauf am selben Halt wie auf den Flow. |
| E15 | **Später, nicht jetzt:** ein eigener Umwandlungs-Flow (Markdown mit Gliederung, Ausgabe als Datei) für Strukturdokumente — besser als `textContent`, braucht aber einen neuen Flow und W5 beim MCP. Als Wunsch an die Flow-Autoren in `offene-befunde`. |
| E16 | **Warten auf den Flow** baut auf K1b/K2b auf: Der Ablauf hält am Auftragsschritt (`wartet_auftrag`); `ui_fortschritt` fragt selbst in wachsenden Abständen nach (`POST /api/ui/auftrag/stand`), jetzt über den MCP (`wlo_flow_status` mit dem Zugangsblock der Person statt b-api-Schlüssel) und mit **„k von n fertig“** aus `progress`. Die Eingabe ist gesperrt (`eingabe_gesperrt`) mit drei Wegen: **„Stand prüfen“**, **„Abbrechen“** (`wlo_cancel_flow`; der Lauf endet, danach „Neues Vorhaben“ und „Arbeitsstand löschen“ — angeglichen nach dem Durchtest vom 19.11., der Code bleibt so), **„Später weitermachen“** (der Lauf bleibt im Vorgang wartend, der Chat wird frei; Rückkehr über „Meine Vorgänge“). |
| E17 | **Rückkehr:** „Meine Vorgänge“ zeigt den wartenden Lauf; „Fortsetzen“ prüft sofort den Stand (gibt es schon: `fortsetzen.pruefen`). Fristen: Vorgang nach der Aufbewahrung im Studio, Job 30 Tage bei der b-api; die Ergebnisse liegen dauerhaft an den Datensätzen. Ist der Job unbekannt (MCP-Neustart, Frist) → direkt `metadaten_lesen`. Der Text nennt die Frist („Du kannst bis … weitermachen“). |
| E18 | **Reihenfolge neu:** nach D zuerst **K** (gegen den lokalen MCP-Stand gebaut, nur lesend aus der Arbeitskopie gestartet; Staging-Durchtest nach dem Rollout), dann **U** (Upload-Feld nach E13, lokaler Zweig). |

## 5 Pakete

Abhängigkeiten: **D** und **U1–U4** sind unabhängig voneinander. **K** braucht **M** (MCP-Entwickler).
**U5** braucht **K** nur für den WLO-Zweig; der lokale Zweig geht ohne. Jedes Paket: Schritt 0
`/better-coding-workflow` (bei UI zusätzlich `/better-coding-frontend`), Test zuerst, danach
unabhängiges Review, Änderungsnotiz unter `docs/aenderungen/`.

### Paket D — Chatbot an die Delegation (Chatbot, klein)

| Task | Dateien | Inhalt | Test |
|---|---|---|---|
| D1 | `services/llm_auth.py` | `_FORM` auf 8–8192; neue Funktion `zug_art() -> Literal["delegation","schluessel",""]` (Präfix `bdt_`); `b_api_schluessel()` gibt bei Art `delegation` nie `B_API_KEY` zurück (leer, wenn der Zug-Wert fehlt — kann nicht vorkommen, Absicherung). Doku-Kopf neu (forwardDelegation). | `test_llm_auth_delegation.py`: 600-Zeichen-Token angenommen, `bdt_`-Art erkannt, kein Rückfall, nie im `repr`/Log. |
| D2 | `services/auftraege/client.py`, `services/mcp/auth.py`, `services/mcp/anmeldung.py` | `_person()`/`X-Edu-User-Id` entfernen (auch bei Abfrage/Abbruch/Datei); `BEKANNTE_CODES` += `EDU_USER_REQUIRED`, `LEGACY_HEADERS`; `auth.benutzername()` bleibt nur, wo es noch gebraucht wird (sonst entfernen). | Bestehende Tests anpassen; neuer Test: kein Kopf `X-Edu-User-Id` in irgendeiner Anfrage. |
| D3 | `api/sse.py`, `api/chat.py` | Bei `zug_art()=="delegation"` und Auflegen des Clients: Zug abbrechen statt Nachlauf (Nutzernachricht und fertige Teile speichern, Vermerk `abgebrochen`). Ohne Delegation unverändert. | Test mit simuliertem Auflegen: keine b-api-Aufrufe danach. |
| D4 | `services/ablauf/zug_basis.py` | `abbrechen_im_hintergrund` bei Delegation nicht starten; stattdessen Abbruch im Zug (bis K da ist: Hinweis „läuft im Repository zu Ende“). | Test: kein Task nach der Antwort. |
| D5 | `i18n/bot_text.py`, `services/ablauf/auftrag_zug.py` | Sätze für 401-mit-Delegation und `EDU_USER_REQUIRED`. | Texttests de/en. |
| D6 | `docs/b-api-betrieb.md` (neu), `deploy/.env.example` | Admin-Liste für den Proxy-Eintrag `badboerdichat` (siehe §6), Betriebsarten, Rückfall-Regeln. | — |

### Paket M — beim MCP-Entwickler (extern, nicht Teil dieses Plans)

Eigener Plan: `docs/plans/2026-11-17-mcp-wuensche-b-api-flows.md` (W0 gemessen 18.11.: der
Repository-Proxy reicht Job-Pfade durch). Kurz: Repository-Proxy-Client (`/rest/bapi/**` mit der
Anmeldung der Person), Werkzeuge `wlo_start_flow`, `wlo_flow_status`, `wlo_cancel_flow`
(Freigabeliste, nur persönlich), optional Datei, Flow-Liste, Textextraktion; alles abschaltbar.
Dazu Labels und Input `bapi_token` am Flow (Flow-Autor) und Rechte am Repository-Schlüssel
(b-api-Admin). **Für uns:** Paket K beginnt, sobald der MCP die Werkzeuge auf Staging bereitstellt;
bis dahin bleibt der Kestra-Zweig im Upload „In WLO“ ohne Erschließung (Ablage geht, Metadaten
nicht) und sagt das der Person.

### Reihenfolge im Chatbot

Neu nach E18 (18.11.):

1. **D** → volle Suite, Review, PR.
2. **K** (inkl. E14 Strukturdokumente im Flow, E16 Warten über den MCP, E17 Rückkehr) gegen den
   lokalen MCP-Stand → Suite, Review, PR; Staging-Durchtest nach dem MCP-Rollout.
3. **U** (Upload-Feld nach E13, lokaler Zweig U2/U3, Ablauf U6, freier Chat U7) → Suite, Review,
   Durchtest U8 inkl. WLO-Zweig, PR.

### Paket K — Chatbot startet Flows über den MCP (Chatbot, nach M)

| Task | Dateien | Inhalt | Test |
|---|---|---|---|
| K1 | `services/auftraege/mcp_starter.py` (neu) | Gleiche Schnittstelle wie `client.starten/stand/abbrechen/datei`, aber über die MCP-Werkzeuge; Fehler auf `AuftragFehler` abgebildet. | Tests gegen die echte Drahtform aus dem MCP (Fixture aus seinen Schemas). |
| K2 | `services/auftraege/__init__.py` bzw. `auftrag_zug.py` | Auswahl des Trägers: MCP kennt `wlo_start_flow` (`faehigkeiten.kennt_werkzeug`) → MCP; sonst Direktweg (nur ohne `repo_schreibt`); sonst `aus` mit Grund. | Matrix-Test der drei Fälle. |
| K3 | `services/mcp/faehigkeiten.py`, `ui_module/dienst_upload.py` | `wlo_erschliessen` bzw. Schalter `ablage_in_wlo` berücksichtigt den neuen Träger. | Schalter-Tests. |
| K4 | `services/ablauf/zug_basis.py` | Abbruch eines Laufs bricht den Job über den MCP im Zug ab (ersetzt D4-Hinweis). | Test. |
| K5 | Seed `06-ablaeufe/themenbaum.yaml`, `services/ablauf/vorbelegung.py` | E14: `node_ids` des Schritts `metadaten` aus `ablage` mit Rolle inhalt **und** struktur; Vorbelegung nimmt Fach/Stufe auch aus den Metadaten der Strukturdokumente; Volltext der Strukturdokumente fehlt noch → Halt mit Stand-Abfrage wie beim Flow. | Seed-Selbsttests, Vorbelegungs-Tests. |
| K6 | `api/ui_auftrag.py`, `frontend/…/ui-fortschritt` | E16: Stand über den MCP (Zugangsblock statt b-api-Schlüssel), `progress` → „k von n fertig“; `unknown` erneut abfragbar, `unknown_job` → Abholen geht zu `metadaten_lesen`. | API- und Modul-Specs. |
| K7 | `services/ablauf/auftrag_zug.py`, Widget-Sperre (`eingabe_gesperrt`) | E16: Knopf „Später weitermachen“ neben „Stand prüfen“ und „Abbrechen“; der Lauf bleibt wartend, die Sperre fällt nur für diese Sitzung, der Text nennt die Rückkehr über „Meine Vorgänge“ und die Frist (E17). | Zug- und Widget-Tests. |
| K8 | `services/ablauf/auftrag_zug.py`, Teil des Auftrags | `outcomeOpen`-Regel (kein Neustart), Bericht je Knoten (`written.changedKeys`) als Zahl „n Materialien erschlossen“, `jobId` nie an Person/Modell/Log. | Tests inkl. Log-Prüfung. |
| K9 | `services/auftraege/flow_katalog.py`, Studio | Das Studio hat keine Person (kein Zugangsblock) — die Flow-Liste kommt weiter über `B_API_KEY`; ohne Schlüssel gilt die Werksvorgabe (`client.WERKSVORGABE`) plus Freitext, mit dem Hinweis, dass der MCP die Freigabeliste `WLO_BAPI_FLOWS` hält. | Katalog-Tests. |

**Vertrag des MCP (Antwort 18.11., gebaut W1–W4 und W6; W5/W7 zurückgestellt)** — bindend für K:

- **Start** `wlo_start_flow(flow, inputs, confirmToken?)`: ohne `confirmToken` → `status: preview` mit
  `confirm.token` und Vorschautext (jedes Material „nodeId Titel“ und was überschrieben wird); mit →
  `started` (`jobId`, `flow`) oder `failed` mit `reason` (`not_allowed`, `login_required`,
  `edu_user_required`, `rejected`, `bad_inputs`, `rate_limited`, `upstream_error`), `retryAfter?`,
  `code?`, bei `node-metadata-write` `problems: [{nodeId, problem}]` (`not_found`, `not_readable`,
  `not_a_record`, `is_reference`, `not_writable`, `unchecked`). Der MCP prüft vor der Vorschau jeden
  Datensatz als die Person (Material, keine Verknüpfung, schreibbar). `language` wird ausdrücklich
  mitgeschickt (`de`/`en`). Derselbe Schlüssel zweimal → erste Antwort mit `replayed: true`.
- **Entscheiden nach `error.outcomeOpen`, nicht nach `reason`:** `true` (5xx, 202 ohne jobId,
  Abbruch, auch 429) → ein Job kann laufen: **nicht neu starten**, Person darauf hinweisen, Stand
  nachsehen; `false` (4xx der b-api) → nichts gestartet, Schlüssel verbraucht, neue Vorschau.
- **Stand** `wlo_flow_status(jobId)`: `running|succeeded|failed|cancelled|unknown` (`unknown` =
  undokumentiertes Statuswort — **nicht** als laufend behandeln, erneut abfragbar), `progress`,
  `iterations` (nur Zahlen), `outputs` (nur bei Erfolg, ≤ 1 MB), `files` ohne Link. Fehler:
  `status: failed`, `reason` (`unknown_job`, `edu_user_required`, `rejected`, `rate_limited`,
  `login_required`, `upstream_error` = offen, ob er noch läuft).
- **Abbruch** `wlo_cancel_flow(jobId)`: `cancelled|already_finished|unknown_job`; ohne Antwort
  `upstream_error` + `outcomeOpen: true` → Stand nachsehen.
- **Flow-Liste** `wlo_list_flows`: Flows der Anmeldung ∩ `WLO_BAPI_FLOWS`, mit Beschreibung und
  Eingabeschema — Quelle für die Flow-Auswahl im Studio (ersetzt bei Delegation den Katalog über
  `B_API_KEY`).
- **Bereitstellung (zweite Fassung der Antwort):** Die Werkzeuge erscheinen, sobald der MCP beim
  Start anonym erkennt, dass das Repository den b-api-Proxy hat (festlegbar mit
  `WLO_BAPI_VIA_REPOSITORY=1/0`); `node-metadata-write` ist ab Werk startbar (`WLO_BAPI_FLOWS` nur
  zum Einschränken). Auf Staging ist nichts zu setzen. **Nach einem MCP-Neustart** fehlen die
  Werkzeuge Sekunden bis Minuten in `tools/list`; ein Aufruf mit alter Liste ergibt den
  Protokollfehler „unbekanntes Werkzeug“ (kein `error.code`) → Fähigkeiten neu holen, der Person
  „gerade nicht verfügbar“ sagen, beim Stand wie `upstream_error` (vorübergehend) behandeln.
  Abweisung vor dem Werkzeug: nur `error.code: login_required`. `reason`-Liste nicht abschließend.
- **Eigene Jobs** bindet der MCP **im Arbeitsspeicher** an das Konto. Nach einem MCP-Neustart ist
  auch ein eigener laufender Job `unknown_job`. **Folge für K:** `unknown_job` bei einem Job, den
  dieser Vorgang gestartet hat, ist kein Fehlschlag des Flows — der Ablauf geht weiter zu
  `metadaten_lesen` (die Ergebnisse stehen an den Datensätzen) mit dem Hinweis, dass der Stand
  nicht mehr abrufbar ist.
- **Bericht** des Flows je Knoten: `{nodeId, status, written: {changedKeys, ignoredKeys}, httpCode,
  characters}`; Dauer gemessen rund 30 s; ersetzt werden acht Felder (Titel, Beschreibung,
  Schlagworte, Sprache, Bildungsstufe, Zielgruppe, Ressourcentyp, Fach).
- **Messung:** Schreiben mit eingefrorener Person geht (Plan §7 Frage 3 endgültig beantwortet).
  Ticket-Anmeldungen am Proxy sind ungemessen — beim Durchtest mit einem Ticket-Block prüfen und
  dem MCP melden.
- **Sicherheitslücke bei der b-api** (Bericht des MCP §4, an das b-api-Team): Über `/bapi/**`
  hängen Jobs am Schlüssel des Repositorys, nicht an der Person — jede bestätigte Person liest jeden
  Job, dessen `jobId` sie kennt; ohne `DisableGuest` liest der Gast jeden Job. Für uns (Task in K
  prüfen): `jobId` nie an die Person oder ins Modell geben (auch nicht über den Teil des Auftrags),
  nie in Logs; die 20 offenen Jobs
  teilen sich alle Personen des Repositorys (429 sauber behandeln).

### Paket U — ein Upload-Weg (Chatbot)

| Task | Dateien | Inhalt | Test |
|---|---|---|---|
| U1 | `domain/config_models/upload.py`, Seed `01-base/upload-config.yaml`, Studio-Katalog `fields-upload.ts` | Felder `lokal_max_dateien` (10; 1–30), `lokal_max_mb_gesamt` (50; 1–200); `services/dokumente/ablage.MAX_JE_SITZUNG` liest `lokal_max_dateien`. | Modell- und Lader-Tests; Studio-Spec. |
| U2 | `services/dokumente/inhalt_angaben.py` (neu), `api/ui_dokumente.py` | `POST /api/ui/dokumente` nimmt `rolle: inhalt|struktur`; bei `inhalt` nach Umwandlung und Moderation ein LLM-Aufruf (kleines Modell, Anfang ≤ 4000 Zeichen) → `{titel, beschreibung, schlagworte}`; Ergebnis in der Antwort, nie der Text. | Tests mit Attrappe des LLM; Moderation `closed`. |
| U3 | `services/ablauf/inhalte_aus_dateien.py` → `services/dokumente/metadaten_lokal.py` | Teil `metadaten` (`wlo.metadaten@1`, `quelle: chatbot`) aus den Angaben der gelesenen Inhalte; nicht lesbare Dateien mit Titel aus dem Namen (`lesbar: false`). | Format-Test gegen `metadaten.als_dokument`. |
| U4 | Modul `frontend/projects/ui-module/src/ui-upload/*` | Nach der Auswahl die Frage „Wo verarbeiten?“ (Chips mit Erklärzeile, Vorauswahl nach E10, gesperrte Chips mit Grund als Text, nicht nur Farbe); ein Knopf „Hochladen“; Fortschritt je Datei; „Nur Namen senden“ als Nebenknopf. Antwort `aktion: "bereitgestellt"` mit `ort: "chat"|"wlo"|"namen"` (alte Aktionen nimmt das Backend weiter an). Texte de/en. | Element-Specs (Zustände: leer, Auswahl, gesperrt, lädt, Fehler je Datei, fertig), Tastatur, axe; E2E `upload-bereitstellen.spec.ts`. |
| U5 | `ui_module/upload_antwort.py`, `services/arbeitsstand_teile.py`, `api/ui_ablage.py` | Antwort → Teile nach E11; bei `ort: wlo` nach der Ablage Start des Metadaten-Flows über K (Freigabe-Box wie bisher, `repo_schreibt`). | Teile-Tests je Ort. |
| U6 | Seed `06-ablaeufe/themenbaum.yaml` | E12: `wlo_frage`, `schnell`, `schnell_da` entfallen; `dateien_weg` nach Teilen; Selbsttests nachziehen. | Seed-Selbsttests, Leiste. |
| U7 | `services/dokument_lesen.py`, `docs/skills/vorgehen-knapp.md`, `docs/ui-module.md` | `dokument_lesen` sieht auch gelesene Inhalte; Master-Skill: „was liegt bereit, wie greife ich zu“. | Test: Inhalt lesbar im freien Chat. |
| U8 | — | Durchtest gegen Wegwerf-DB: hier im Chat (3 Dateien), Grenze überschritten, nur Namen, freier Chat ohne Ablauf; WLO-Zweig nach K. | Protokoll `docs/aenderungen/`. |

## 6 Für den b-api-Admin (Proxy-Eintrag `badboerdichat`)

- `forwardDelegation: true`, `delegationScopes: [llm]` (mehr braucht der Chatbot nicht: WLO läuft
  über den MCP), `delegationLifetimeSeconds` ≥ 300 (längster Zug inkl. Agent-Schleife).
- `responseTimeout` ≥ 120 s; `allowedResponseContentTypes` mit `text/event-stream`.
- `allowedRequestHeaders`: `WLO-Access-Block`, `Accept-Language`, `x-client-trace-id`, B3-Köpfe —
  ohne `WLO-Access-Block` reißt die Auth-Kette Widget → Backend → MCP hinter dem Proxy.
- `pathToIgnore`: Studio-, Admin-, Eval- und Debug-Pfade (nicht in die öffentliche Doku).
- **Für den Kestra-Weg** (Jobs-Doku der b-api, 18.11.): Der b-api-Schlüssel des **Repositorys** (den
  sein Proxy `/rest/bapi/**` setzt) braucht die Rolle `JOBS` (bzw. das Privileg
  `JOB_RUN_EDUSHARING_CHATBOT_NODE-METADATA-WRITE`) und die Rechte `EDU_SHARING_REPO_READ` und
  `EDU_SHARING_REPO_WRITE`. Der Flow `node-metadata-write` braucht die Labels `bapi.expose: "true"`,
  `bapi.scopes: "edu-sharing-repo,edu-sharing-repo-write,llm"` (Lesen, Metadaten schreiben, Agent),
  optional `bapi.maxRuntime` (z. B. `PT30M`), und den Input `bapi_token` vom Typ SECRET.

## 7 Offene Fragen an die b-api (nicht blockierend für D und U)

1. Bleibt `B_API_KEY` außerhalb des Proxys erlaubt (Studio, Eval, lokale Tests)?
2. Kommt `text/event-stream` durch den Proxy, gilt dort ein 30-s-Abbruch?
3. ~~Läuft `node-metadata-write` mit eingefrorener Person (Schreiben im Flow)?~~ **Beantwortet
   (Jobs-Doku 18.11.):** ja, mit dem Scope `edu-sharing-repo-write` am Flow (PATCH
   `…/nodes/{id}/metadata`) und dem Recht `EDU_SHARING_REPO_WRITE` am Schlüssel (§6). Ob der Flow
   heute schon so gelabelt ist, prüft der Flow-Autor.
4. ~~Proxied `…/rest/bapi/**` auch `/api/v1/jobs/**`?~~ **Ja, gemessen 18.11.** (Liste, Flows,
   unbekannter Job → 404). Der Start selbst ist nicht ausprobiert (er schriebe Metadaten).
5. Länge und Form von `bdt_…` (für E3 nur zur Bestätigung).

## 8 Risiken

| Risiko | Abhilfe |
|---|---|
| ~~Repository-Proxy reicht Job-Pfade nicht durch~~ | **Gemessen 18.11.:** `/rest/bapi/api/v1/jobs/flows` 200 mit `node-metadata-write`, `/jobs` 200, unbekannter Job 404 (Testkonto, Sitzungs-Cookie, nur lesend). |
| Lokale Angaben kosten je Datei einen LLM-Aufruf | Deckel `lokal_max_dateien`; kleines Modell; parallel höchstens 3. |
| Inhalte bleiben bis `aufbewahrung_h` gespeichert | Hinweis am Chip; nur Text, nie Rohdatei; Moderation wie bei Strukturdokumenten. |
| Auth-Kette reißt hinter dem Proxy | `allowedRequestHeaders` (§6); Chatbot meldet fehlenden Block wie heute. |
| Alte Abläufe/Antworten | Backend nimmt alte Aktionen weiter an; Werksabgleich beim Deploy. |

## 9 Abnahme

- D: volle Backend-Suite grün; Test „kein `X-Edu-User-Id`“; Test „Delegation ohne Rückfall“.
- U: Backend-Suite, `ng test ui-module`, E2E Upload; Durchtest U8 alle Wege ok.
- K: gegen den gebauten MCP lokal (Port 8291, nur lesend aus der Arbeitskopie gestartet) und auf
  Staging mit dem Testkonto: Ablage → Flow-Start → Stand → `metadaten_lesen` → Themenbaum mit
  Titeln/Beschreibungen.
