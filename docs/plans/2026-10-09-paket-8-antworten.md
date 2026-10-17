# Paket 8: Antworten auf die offenen Fragen aus Paket 7 (2026-10-09)

**Stand 2026-10-09: umgesetzt** (Phasen M, K, A, P; C als Erklärung; dazu die Nachfrage-Antworten
in §1, Log „Nachtrag“). Keine offene Frage aus diesem Paket. Regeln wie immer: je Aufgabe Test zuerst
rot, Dateien ≤300 Zeilen, Texte de/en, Commits, Upload, Deploy und Golden-/Lastläufe macht der
Nutzer.

## 1 Die Antworten (Nutzer, 2026-10-09)

> nein default modell bleibt b-api-openai mit gpt-6-luna. academiccloud modell müssen laufen können
> aber sollten nicht standard sein - da langsamer und schlechter. ja b-api-openai wie openai (also 20
> als default). retention days bauen und integrieren in backend und studio. p5-7 entscheide du nach
> eigenen ermessen. 5. krisenschwelle auf basis von messwerten und eigenen empfehlungen entscheiden und
> eventuell konfigurierbar machen im studio. 6. verstehe ich nicht ganz - was meinst du damit das
> verlaufsfenster blockweise zu kürzen?

Nachfrage, am selben Tag beantwortet:

> das verlaufsfenster lassen wir erstmal - klingt nach viel korrekturbedarf bei wenig mehrwert. die
> standardfrist für gesprächsverläufe ist 30 Tage als default - aber änderbar. wahrscheinlich
> supporten nicht alle gwdg modelle werkzeuge - das müßte man dann individuell testen. vielleicht ein
> todo außerhalb des chatbots. das studio wird nicht oft aufgerufen - es ist nicht schlimm wenn wir
> etwas über der warnschwelle liegen.

## 2 Befunde vor dem Bau

- **AcademicCloud-Vorgaben laufen nicht.** `llm_models._PROVIDER_DEFAULTS` nennt
  `mistral-large-3-675b-instruct-2512` (Chat) und `e5-mistral-7b-instruct` (Einbettung). Keins von
  beiden steht in `/academiccloud/models` (Probe 2026-10-09, 14 Modelle) — dort steht überhaupt kein
  Einbettungsmodell. Die Wissensbasis liegt im Vektorraum von `text-embedding-3-small` (1 536
  Dimensionen); ALT bettete auf AcademicCloud deshalb über einen OpenAI-Seitenkanal ein.
- **Standardmodell im Code ist `gpt-5.6-luna`**, auch für `b-api-openai`; die Schnellstart-Anleitung
  setzt `LLM_CHAT_MODEL=gpt-5.6-luna`, `LLM_MAX_CONCURRENCY=2`, `BG_LLM_MAX_CONCURRENCY=1`.
- **`retention_days` gilt zwei Protokollen:** `safety-config.logging` (Sicherheitsprotokoll, Seed 90)
  und `quality-log-config.logging` (Qualitätsprotokoll, Seed 180). Gesprächsverläufe selbst haben keine
  Frist. Löschen kann heute nur der Hand-Knopf „Löschen über alle Sitzungen“ (`/api/sessions/purge`).
- **Krisen:** Das Regex-Gate erkennt keine der zehn K8-Andeutungen; die Moderation (Schwelle 0,25)
  drei. Auf `b-api-academiccloud` gibt es keine Moderation — dort ist das Gate der einzige Boden.
  Schwellen und `extra_crisis_terms` sind im Studio schon pflegbar.
- **P5-7:** Das Studio-`index.html` trägt ein Inline-Skript (Beasties schaltet das Stylesheet um) und
  Inline-Styles; Traefik hängt im Prod-Stack direkt am Docker-Socket (`:ro`).

## 3 Phasen

### M — Modelle und Parallelität
- **M1 (L8):** AcademicCloud lauffähig, nicht Standard. Chat-Vorgabe auf ein Modell, das die Probe mit
  Werkzeugaufruf besteht; Einbettung auf AcademicCloud über die b-api (`/openai`,
  `text-embedding-3-small`) — derselbe Vektorraum wie die Wissensbasis. Standard bleibt
  `b-api-openai` mit `gpt-6-luna`: Vorgabe beider OpenAI-Wege auf `gpt-6-luna`, Schnellstart angleichen.
- **M2:** `b-api-openai` 20 gleichzeitige Aufrufe wie OpenAI direkt; AcademicCloud bleibt 2.

### A — Aufbewahrung (`retention_days`)
- **A1:** `services/aufbewahrung.py`: fällige Einträge zählen und in Stapeln löschen
  (Sicherheits- und Qualitätsprotokoll; 0 = unbegrenzt).
- **A2:** Lauf alle 6 Stunden im Backend, über alle Kopien nur einer (Advisory-Lock).
- **A3:** Studio: Feld-Hinweise berichtigen (die Fristen wirken jetzt), Panel „Aufbewahrung“ auf der
  Datenschutz-Seite (Fristen, fällige Einträge, „Jetzt bereinigen“).
- **Offen:** eine Frist für Gesprächsverläufe — Nutzer-Entscheid (Kosten-Zeilen hängen an der Sitzung).

### P — P5-7 nach eigenem Ermessen
- **P1:** HSTS als Header des Backends (`HSTS_MAX_AGE`, Vorgabe 1 Tag, 0 = aus).
- **P2:** CSP für das Studio (`STUDIO_CSP` = report | enforce | off); Studio-Build ohne Inline-Skript.
- **Nicht jetzt, mit Grund:** Docker-Socket-Proxy (reine Deploy-Änderung, lokal nicht ohne neue Images
  prüfbar), Sicherung auf zweitem Rechner (braucht Infrastruktur), Studio-Sitzungen (eigenes Paket),
  CORS zu (braucht die Liste der echten Einbettungen).

### K — Krisenschwelle
- **K1:** Messung erweitern (Moderation, OpenAI direkt): mehr Andeutungen, mehr Gegenproben aus dem
  Unterricht.
- **K2:** Entscheid nach Messung: Schwellen; eingebaute Krisen-Wendungen hoher Trennschärfe im
  Regex-Gate (wirken auch ohne Moderation); Studio-Hinweise mit den Messwerten.

### C — Erklärung C1 (nur Antwort)

## 4 Log

### M · erledigt — Modelle und Parallelität
- **Probe 2026-10-09 (Staging-b-api, Schlüssel aus der Umgebung):** `/openai/models` führt
  `gpt-6-luna` (141 Modelle). `/openai/embeddings` mit `text-embedding-3-small`: 200, 1 536
  Dimensionen. Alle `/academiccloud`-Aufrufe: 429 „API rate limit exceeded“ schon beim ersten Aufruf
  (wie zweimal in Paket 7), `qwen3.5-122b-a10b` 503 „Model pricing unavailable“. **Offen:** der
  Werkzeugaufruf auf der AcademicCloud ist ungeprüft; `qwen3-30b-a3b-instruct-2507` ist das einzige
  Modell, das dort je mit 200 antwortete (Paket 7).
- **M1:** Vorgabe beider OpenAI-Wege `gpt-6-luna`; AcademicCloud `qwen3-30b-a3b-instruct-2507`, die
  Einbettung dort `text-embedding-3-small` über den OpenAI-Pfad der b-api (`llm.route`: ein
  `text-embedding-*`-Modell geht auch auf der AcademicCloud nach `/openai`). Neun Tests, die die alte
  Vorgabe prüften, auf die neue gestellt; der W12b-Test der 5.6-Gruppe setzt sein Modell jetzt
  ausdrücklich. Schnellstart, `.env.example`, `architektur.md` §5.6 nachgezogen.
- **M2:** `b-api-openai` 20 wie OpenAI direkt (`llm_parallel._B_API_DECKEL` nur noch AcademicCloud 2).
- Tests: `test_llm_models` (3 angepasst), `test_llm` (+1, 6 angepasst), `test_llm_parallel`
  (+1 parametrisiert, 1 umbenannt), `test_api_health`, `test_classify`, `test_llm_streaming` (je 1).
  437 + 20 grün.

### K · erledigt — Krisenschwelle nach Messung
- **K1 (Messung 2026-10-09, `evals/moderation_messung.py`, OpenAI direkt, `omni-moderation-latest`):**
  die Satzliste um je 18 Sätze erweitert — Andeutungen auch in Jugendsprache und Englisch,
  Gegenproben aus dem Unterricht (Werther-Effekt, Romeo und Julia, Prävention, „todmüde“, „ich kann
  nicht mehr, diese Hausaufgaben …“). Ergebnis bei 28 + 28 Sätzen:

  | Schwelle `self_harm` | erkannte Andeutungen | Fehlalarme |
  |---|---|---|
  | 0,10 | 22/28 | 1 |
  | 0,13–0,15 | 19/28 | 1 (Romeo und Julia, 0,158) |
  | 0,17–0,25 | 16/28 | 0 |
  | 0,30 | 13/28 | 0 |

  `self_harm/intent` bringt über `self_harm` ≥ 0,25 hinaus keine weitere Andeutung. Das Regex-Gate
  erkannte vorher 2/28 (einen bewusst festgehaltenen Fehlalarm: „suicide prevention“, englisch).
- **K2 (Entscheid):** Die Schwellen bleiben bei 0,25 — Senken bringt keinen Treffer ohne Fehlalarm
  bei Literatur- und Präventionsunterricht. Die Lücke schließen **Krisen-Wendungen im Regex-Gate**
  (`services/safety/krisen_wendungen.py`, 23 Muster): selbstbezogen und eng gefasst („ich sehe
  keinen Ausweg mehr“, nicht „sieht keinen Ausweg“; „ich will sterben“, nicht „Faust will
  sterben“), Umlaute auch ausgeschrieben. Fest eingebaut wie die ALT-Muster — sie wirken auch ohne
  Moderation (AcademicCloud) und auf bestehenden Anlagen sofort; eigene Wendungen ergänzt das Studio
  über `extra_crisis_terms`. Erkannt werden jetzt 24/28 Andeutungen allein durchs Gate, zusammen mit
  der Moderation 25/28. Bewusst offen: verhüllte Andeutungen ohne trennbare Wendung („Heute Abend
  ist es vorbei, ich habe alles vorbereitet.“, „Ich habe meine Sachen verschenkt …“, „Bald bin ich
  nicht mehr da …“).
- Breitenprüfung: alle 50 Nutzersätze der Golden-Suite und der Szenarien — kein Treffer der neuen
  Wendungen.
- Studio: Hinweise zu „Schwellen je Kategorie“ (Messwert) und „Zusätzliche Krisenbegriffe“
  (eingebaute Wendungen) ergänzt; Seed-Kommentar zur Schwelle.
- Tests: `test_krisen_wendungen.py` (neu, 59: 24 Andeutungen, 35 Gegenproben, davon 8 zusätzliche
  Alltags- und Unterrichtssätze nah an den Wendungen).

### A · erledigt — Aufbewahrung durchgesetzt
- **A1:** `services/aufbewahrung.py` liest die Fristen beider Bereiche. Fehlt das Feld, gilt die
  Vorgabe des Bereichsmodells — dieselbe, die das Studio anzeigt; ein Wert, der keine Zahl ist, löscht
  nichts und warnt im Log. Je Protokoll zählt der Dienst Frist, fällige Einträge und den ältesten
  Eintrag und löscht in Stapeln zu 5 000 Zeilen, jeden in einer eigenen Transaktion (jeder Zug
  schreibt in diese Tabellen). Das Bereichsmodell nimmt nur noch `retention_days` ≥ 0 an.
- **A2:** Lauf alle 6 Stunden, der erste 5 Minuten nach dem Start (nicht mitten in die Vorwärmung);
  gestartet im Lebenszyklus der App, beim Herunterfahren abgebrochen. Abweichung vom Plan: über alle
  Kopien sorgt nicht ein Advisory-Lock für nur einen Lauf, sondern die vorhandene Lease der
  Sitzungssperre (`session_locks`, Schlüssel `__lauf:aufbewahrung`) — ein zweiter Sperrweg wäre eine
  zweite Mechanik für dieselbe Frage.
- **Studio-API:** `GET /api/sessions/retention` (Überblick), `POST /api/sessions/retention` (Lauf
  vorziehen; 409, wenn er gerade läuft). Im OpenAPI-Vertrag ist nur dieser Pfad neu.
- **A3:** Panel „Aufbewahrung“ auf der Datenschutz-Seite zwischen „Qualitäts-Logging“ und „Gespräche
  löschen“: Tabelle je Protokoll (Frist, jetzt fällig, ältester Eintrag; 0 Tage = „unbegrenzt“, fällig
  „nie“), „Bereinigen …“ mit einer Rückfrage, Fokus wie im Lösch-Panel, Ergebnis in der
  Status-Region, 409 und Fehler als Alarm. Die Feld-Hinweise beider `retention_days` sagen jetzt, was
  geschieht (de/en).
- **Wirkung nach dem Deploy:** Der erste Lauf löscht nach den gepflegten Fristen (Seed: 90 Tage
  Sicherheits-, 180 Tage Qualitätsprotokoll). Wer ältere Einträge behalten will, setzt vorher 0.
- Tests: Backend `test_aufbewahrung.py` (6, Postgres), `test_aufbewahrung_takt.py` (3),
  `test_aufbewahrung_api.py` (4); Studio `retention.component.spec.ts` (10),
  `sessions-api.service.spec.ts` (+2), `curated-view.component.spec.ts` (Panel-Liste).
- Die Frist für Gesprächsverläufe folgte nach der Nachfrage (Log „Nachtrag“).

### P · erledigt — HSTS und CSP für das Studio (P5-7 nach eigenem Ermessen)
- **P1:** `Strict-Transport-Security: max-age=86400` auf jeder Antwort (`main._security_headers`),
  einstellbar über `HSTS_MAX_AGE` (0 = kein Header, negativ zählt als 0). Ein Tag als Vorgabe: bricht
  das Zertifikat, sperrt sich ein Browser höchstens einen Tag lang aus; ein Jahr empfiehlt sich,
  sobald HTTPS stabil läuft. Ohne `includeSubDomains` und `preload` — beide gälten auch für Hosts,
  die diese Anlage nicht kennt.
- **P2:** CSP auf der Studio-Seite (`index.html` und jeder SPA-Rückfall, `api/studio_static.py`):
  `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:
  https:; media-src 'self' blob:; connect-src 'self' <MCP-Herkunft>; object-src 'none'; base-uri
  'self'; frame-ancestors 'self'; form-action 'self'`. `'unsafe-inline'` nur für Stile: Angular setzt
  Komponenten-Stile als `<style>`, das Widget der Vorschau in seinem Shadow-Root. `blob:` für das
  Vorlesen im Widget, `https:` für Vorschaubilder fremder Repositorien, die MCP-Herkunft für die
  WLO-Anmeldung im Widget (siehe unten). `STUDIO_CSP` = `enforce`
  (Vorgabe) | `report` | `off`; ein unbekannter Wert setzt durch. Der Studio-Build schreibt kein
  Inline-Skript mehr (`angular.json`: `inlineCritical: false`) — Beasties schaltete das Stylesheet
  per Inline-Skript von `media="print"` um; unter `script-src 'self'` stünde das Studio ohne Stil da.
- **Durchsetzen statt nur beobachten:** Eine Report-Only-Regel ohne Meldeadresse liest niemand, und
  die Browser-Probe fand keinen Verstoß. Zurück auf `report` geht es mit einer Zeile in der `.env`.
- **Browser-Probe 2026-10-09:** lokales Backend gegen eine frische Wegwerf-Datenbank mit Seed, offener
  Admin ohne Schlüssel, Studio-Produktions-Build. Alle 21 Seiten der Navigation, die Widget-Vorschau
  (Widget im Shadow-Root, Stile aktiv) und das Aufbewahrungs-Panel: 0 Verstöße
  (`securitypolicyviolation`), Stylesheet aktiv. Aufbewahrung durchgängig: 4 + 3 Protokollzeilen
  angelegt, davon 3 bzw. 2 älter als die Frist → das Panel zeigt 3 bzw. 2 fällig, „Bereinigen“
  löscht genau diese (Log `gelöscht {'safety_logs': 3, 'quality_logs': 2}`), die frischen bleiben.
  Wegwerf-Datenbank danach gelöscht.
- **Zwei Funde, die der Seitenrundgang nicht zeigen konnte** (sie brauchen eine Handlung, kein Laden):
  - **Drucken:** Die Druckansicht des Widgets schrieb ein Inline-Skript (Dokument: Druck nach dem
    Laden) und `onclick`-Knöpfe (Arbeitsblatt, Lernpfad) in ein leeres Pop-up. Ein solches Pop-up
    erbt die CSP der öffnenden Seite — in der Studio-Vorschau und auf jeder Gastseite mit strenger
    CSP wären Druck und Knopf tot gewesen. Jetzt hängt das Widget beides von außen an
    (`ui/print/print-fenster.ts`: Druck nach dem Laden, Knopf per `addEventListener`). Rot-Grün
    belegt: die vier neuen Tests scheitern am alten Code, alle 31 Druck-Tests laufen am neuen.
  - **WLO-Anmeldung in der Vorschau:** Das Widget spricht für die Anmeldung den MCP-Server direkt an
    (Entdeckung, Registrierung, Code-Tausch); mit `connect-src 'self'` wäre der Anmelde-Chip in der
    Vorschau still verschwunden. Die Regel nennt jetzt die Herkunft von `MCP_SERVER_URL` — dieselbe,
    die das Widget-Bündel als `mcp_auth_base` veröffentlicht (`domain/mcp_herkunft.py`, vorher in
    `api/config`). Eine kaputte Adresse (Leerzeichen, Semikolon) kommt nicht in die Kopfzeile.
  - **Zweite Browser-Probe** (neuer Build, frische Wegwerf-Datenbank): `connect-src` nennt genau die
    Herkunft aus `mcp_auth_base`; alle 21 Seiten wieder ohne Verstoß. Pop-ups sperrt der eingebaute
    Browser ganz, deshalb die Erbregel an einem `about:blank`-iframe (dieselbe Regel des Standards):
    unter der Studio-CSP liefen weder Inline-Skript noch `onclick`, ein von außen gesetzter Listener
    schon; auf der Widget-Demo desselben Backends (ohne CSP) liefen beide — der Unterschied ist die
    Regel.
- Compose: `HSTS_MAX_AGE` und `STUDIO_CSP` in der Umgebung des Backends (leer = Vorgabe); dazu
  `.env.example`, die Abnahme-Tabelle in `deploy/README.md` und ein Fehlerbild in der
  Schnellstart-Anleitung.
- **Nicht jetzt, mit Grund:** Docker-Socket-Proxy (reine Deploy-Änderung, lokal nicht ohne neue Images
  prüfbar; traefik hat den Socket schon nur lesend), Sicherung auf einem zweiten Rechner (braucht
  Infrastruktur), eigene Studio-Sitzungen statt des festen Cookie-Tokens (eigenes Paket), CORS zu
  (braucht die Liste der echten Einbettungen). Eine CSP für die Demo-Seiten ist ein eigener Schritt:
  sie tragen Inline-Skripte.
- Tests: `test_studio_csp_hsts.py` (neu, 12), `test_deploy_compose.py` (+1), ui
  `print/print-fenster.spec.ts` (neu, 4); die Fenster-Attrappen in `print-utils.spec` und
  `print-gates.spec` kennen jetzt `querySelector` bzw. `addEventListener` wie ein echtes Fenster.
- Volle Backend-Suite danach: zwei Vertrags-Wächter rot (`test_openapi_contract`,
  `test_openapi_additions`) — die beiden Routen fehlten im Inventar und in
  `docs/api/bewusste-vertragszusaetze.md`; nachgetragen, grün. Dazu ein Ausreißer beim Aufbau von
  `test_agent_api` (die NOTIFY-Verbindung zur Dev-Datenbank kam nicht binnen der Frist); einzeln
  wiederholt grün.

### C · Erklärung C1 — was „das Verlaufsfenster blockweise kürzen“ meint
- Jeder Zug schickt dem Modell den festen Kopf (Systemteil, Werkzeuge, Seitendaten, ≈ 20 000
  Tokens), dann die letzten Nachrichten (`domain/history_window.verlaufs_fenster`: höchstens 10, die
  jüngste bis 4 000 Zeichen, ältere bis 1 200, zusammen höchstens 9 000), dann die neue Frage. Der
  Prompt-Cache von OpenAI rechnet nur den Anfang billig, der Zeichen für Zeichen dem vorigen Aufruf
  gleicht; ab der ersten Abweichung zahlt alles den vollen Preis.
- Zwei Stellen verändern den Verlauf von Zug zu Zug nicht nur hinten, sondern mittendrin:
  1. **Gleitfenster:** Ist das Fenster voll (ab etwa Zug 6, mit langen Antworten früher über die
     Zeichengrenze), fällt jeden Zug die älteste Nachricht vorn heraus. Der Verlauf beginnt dann
     jedes Mal anders, und er ist jedes Mal ganz ungecacht (bis ≈ 9 000 Zeichen, gut 2 000 Tokens).
     **Blockweise** hieße: erst wenn das Fenster voll ist, mehrere alte Nachrichten auf einmal
     streichen, etwa die ältere Hälfte. Danach wächst der Verlauf wieder nur hinten, und die
     nächsten Züge treffen den Cache.
  2. **Kürzen nach Position:** Eine lange Antwort geht als jüngste Nachricht ganz mit und im nächsten
     Zug gekürzt. Ab ihr weicht der Verlauf ab — gemessen ≈ 300 Tokens mehr ungecacht je Zug und
     langer Antwort (Paket 7, B-3: 802 → 1 114 → 1 424). **Positionsunabhängig** hieße: jede Antwort
     von Anfang an so lang mitschicken, wie sie später im Verlauf steht.
- Der Preis: blockweise sieht das Modell nach dem Streichen auf einmal weniger Vorgeschichte;
  positionsunabhängig heißt entweder weniger von der jüngsten Antwort oder mehr Zeichen im Verlauf.
- Empfehlung: niedrige Priorität. Es geht um einige hundert bis gut 2 000 ungecachte Tokens je Zug,
  und erst in langen Gesprächen oder mit langen Antworten. Ob es sich lohnt, zeigen Golden- und
  Langläufe; bis dahin bleibt das Fenster, wie es ist.

### Nachtrag · erledigt — Antworten auf die Nachfrage (2026-10-09)
- **Gesprächsverläufe: Vorgabe 30 Tage, änderbar.** Neues Feld `privacy-config.logging.retention_days`
  (Bereichsmodell `PrivacyLoggingBlock`, Vorgabe 30, ≥ 0; Seed mit Kommentar). Der Aufbewahrungs-Lauf
  löscht Chatnachrichten (`messages`) und Sitzungsgedächtnis (`memory`), die älter sind — beim
  Gedächtnis zählt der letzte Schreibvorgang, `save_memory` erneuert den Zeitstempel. Gelesen aus dem
  rohen Bereich, weil `load_privacy_config` nur die Schalter zurückgibt.
  - **Die Sitzungen bleiben**, mit ihnen Zustand und Verbrauchszahlen: `usage_events` hängen per ON
    DELETE CASCADE an der Sitzung, und die Kostenübersicht verlöre ihre Vergangenheit. Gefragt war
    nach den Gesprächsverläufen; ganze Sitzungen löscht weiter nur „Gespräche löschen“.
  - Studio: Feld „Aufbewahrung der Gesprächsverläufe (Tage)“ im Abschnitt „Datenschutz“; das Panel
    „Aufbewahrung“ führt Chatnachrichten und Sitzungsgedächtnis vor den Protokollen.
  - Tests: `test_aufbewahrung.py` (+2, 4 angepasst: die Fristen sind jetzt vier), `test_aufbewahrung_takt`
    (+1, Modell-Grenze auch für die neue Frist), Studio `retention.component.spec.ts` (+2).
- Geprüft: volle Backend-Suite 5603 bestanden (4 übersprungen), Studio 1465, Lint und Prüfskripte grün. Browser-Probe gegen eine Wegwerf-Datenbank: das Feld zeigt 30 Tage (mindestens 0) mit dem neuen Hinweis; das Panel führte 3 fällige Nachrichten und 1 Gedächtnis-Eintrag; „Bereinigen“ löschte genau diese — die frische Nachricht, die Sitzung und ihre Verbrauchszeile blieben; kein CSP-Verstoß. Die erste Tabellenspalte heißt jetzt „Daten“ statt „Protokoll“.
- **C1 (Verlaufsfenster):** lassen — viel Korrekturbedarf bei wenig Mehrwert.
- **AcademicCloud und Werkzeuge:** vermutlich können nicht alle GWDG-Modelle Werkzeuge aufrufen; das
  ist je Modell zu testen — ein Todo außerhalb des Chatbots (Befundliste §3).
- **Studio-Startpaket:** etwas über der Warnschwelle ist in Ordnung; das Studio wird selten
  aufgerufen.
