# Offene Befunde und Todo

Stand 2026-09-29 (Zwischenstand), nachgezogen 2026-10-03 nach Paket 4 und 2026-10-08 nach Paket 4b, 4c und 6, 2026-10-09 nach Paket 7, Paket 8 und Paket 9, 2026-10-14/15 nach Paket 10, 2026-10-17 nach Paket 12, den Chat-Proben und dem Merge von PR #16 (main `dfd7152`): Master-Skill-Kurzfassung im Knoten (22/22 Regeln, M05/M12 und „Ändern“ damit übertragen), die fünf Paket-11-L-Bereiche zieht der Werksabgleich nach. Nachgezogen 2026-10-30 nach Paket 18 (Störtest-Audit, 18A–18F, main `924662a`). Diese Liste sammelt an einer Stelle, was nach diesem Stand offen ist, jeweils mit Quelle.
Erledigtes steht in den Logs der Pläne, nicht hier. Wer einen Punkt erledigt, streicht ihn hier und
trägt ihn im Log des zugehörigen Plans ein. Zeilennummern gelten für den Stand 2026-09-29.

Die zugehörigen Pläne:
- **Betriebsmodi-Plan:** [`2026-09-26-betriebsmodi-und-studio.md`](plans/2026-09-26-betriebsmodi-und-studio.md)
- **Runde-2-Plan:** [`2026-09-28-agent-runde-2.md`](plans/2026-09-28-agent-runde-2.md) — erledigt dort (Paket 2, 2026-10-01): die Schreib-Abnahme im Agent-Modus (früher §1.1), Log unter „Nebenbefund außerhalb dieser Runde“.
- **Responses-Plan:** [`2026-09-29-responses-systemteil-und-cache.md`](plans/2026-09-29-responses-systemteil-und-cache.md)
- **Kette-Plan (Tempo):** [`2026-09-30-muster-kette-zeit.md`](plans/2026-09-30-muster-kette-zeit.md)
- **Paket 1 (Sprache, Kleinbefunde):** [`2026-10-01-paket-1-sprache-und-kleinbefunde.md`](plans/2026-10-01-paket-1-sprache-und-kleinbefunde.md) — erledigt dort: Schnellantworten in der Antwortsprache, Startnachricht beim Sprachwechsel, Guide-Regeln ohne Neustart, Quick Wins aus Audit §7.
- **Token-Streaming-Plan:** [`2026-10-01-token-streaming.md`](plans/2026-10-01-token-streaming.md) — freigegeben 2026-10-03 (alle Empfehlungen), gebaut hinter `CHAT_TOKEN_STREAMING` (PR #9); Stand im Log des Plans.
- **Paket 3 (offene Befunde, erste Runde):** [`2026-10-03-paket-3-offene-befunde.md`](plans/2026-10-03-paket-3-offene-befunde.md) — erledigt dort: Neustart mitten im Zug (früher §1.4), EscalationBlock-Vorgaben und Kennung `AGENT` (früher §2) sowie sieben Befunde aus dem Audit 2026-09-29 (Nachtrag dort in §7).
- **Paket 4b (Folgebefunde aus Paket 4):** [`2026-10-08-paket-4b-folgebefunde.md`](plans/2026-10-08-paket-4b-folgebefunde.md) — erledigt dort: Studio-Auslieferung mit `Cache-Control` (früher §1.5), zehn `role="status"`-Stellen, `type` beim Speichern, Umwandlungsfehler am Typ statt am Präfix, Datenbankfehler als 400 mit Bereich.
- **Paket 4c (Rest aus den Reviews):** [`2026-10-08-paket-4c-rest-aus-den-reviews.md`](plans/2026-10-08-paket-4c-rest-aus-den-reviews.md) — erledigt dort: URL-Import ohne markitdown, Wert ohne JSON als 400 mit Bereich, Ansage „kein Werkzeug“ im MCP-Abgleich, „nicht gesetzt“ und „leer“ im Formular unterscheidbar.
- **Befund Kontext-Ping (2026-10-08):** [`2026-10-08-befund-abnahme-nach-kontext-ping.md`](plans/2026-10-08-befund-abnahme-nach-kontext-ping.md) — erledigt dort: Die Schreib-Abnahme verfiel an einem Zug, den die Person nie sah (Kontext-Ping, Tour-Tick ohne Tour). Auf „bestätigen“ kam deshalb wieder eine Vorschau.
- **Paket 6 (Plan-Rest, Werkszustand, Aufräumen):** [`2026-10-08-paket-6-plan-rest-und-werkszustand.md`](plans/2026-10-08-paket-6-plan-rest-und-werkszustand.md) — erledigt dort: ST-3d, ST-4c und die Architektur-Referenz (früher §6), der Werkszustand per Seed-Prüfung und Kommandozeile, sieben Punkte aus §5 (ReDoS, URL-Import-Frist, DB-Tore in der CI, „Tool not found“, `sources: []`, Umwandlungsfehler, wirksame Wissensbereiche), die Untersuchung des Gatekeeper-Skills (früher §3) samt drei Folgebefunden.
- **Paket 7 (Entscheide vom 2026-10-09):** [`2026-10-09-paket-7-entscheide.md`](plans/2026-10-09-paket-7-entscheide.md) — erledigt dort: Seitentext und System-Blöcke auf dem Responses-Weg (früher §1.1, Phase R samt Nachmessung), aus §2 die Fragen zum Responses-Plan, die ST-5-Befunde 1 und 2, D-10/D-11 (Kosten in EUR), `AgentLimits.safety`, Ablehnungen als ERROR (bleibt), GV-RED-1 (nur auf Abruf), B-H3 (Schreiben nur mit eigenem Konto, Gastkonto per Studio-Schalter), C-H1 (Sitzungssperre über alle Kopien), `markitdown`-Extras samt MPL-2.0-Ausnahme, SSE-Abbruch (zu Ende rechnen), B-API-Moderation, Moderations-Schwelle, Vorgabe-Maschine (Agent), Agent-Schnellantworten, Fast-Modus und Token-Streaming (Studio-Schalter), RAG neben der Klassifikation (Einbettung vorab), Antwortsprache, Kontext-Gruß beim Sprachwechsel, M10 und „Freigabe“; aus §3 die Folgezug-Messung (E-C); aus §5 vier Einstellungen ohne Leser und die Skill-Suche der Testinstanz (S5: `search_skill` nur Rückfall, standardmäßig verborgen).
- **Paket 8 (Antworten vom 2026-10-09):** [`2026-10-09-paket-8-antworten.md`](plans/2026-10-09-paket-8-antworten.md) — erledigt dort: `retention_days` (früher §1.2: Lösch-Lauf alle 6 Stunden, Studio-Panel „Aufbewahrung“), aus §2 die AcademicCloud-Modelle (L8: lauffähig, nicht Vorgabe; Einbettung über `/openai`), die Parallelität `b-api-openai` (20), P5-7 (HSTS und CSP für das Studio — damit auch die CSP/HSTS-Frage aus Audit 2026-09-29 §10), die Krisen-Andeutungen (Wendungen im Regex-Gate) und die Erklärung zu C1.
- **Paket 9 (Review-Befunde zu Paket 7 und 8):** [`2026-10-09-paket-9-review-befunde.md`](plans/2026-10-09-paket-9-review-befunde.md) — erledigt dort: alle Befunde des Reviews vom 2026-10-09 (3 CRITICAL, 9 MAJOR, 26 MINOR, die NITs, V1–V8); zwei Vorschläge mit Begründung nicht übernommen, zwei Dateien bewusst nicht geteilt (Log dort).
- **Paket 11 (Fremde MCP-Server, Einbettungswechsel, Anmeldungs-Dokument):** [`2026-10-15-paket-11-mcp-fremdserver-und-einbettung.md`](plans/2026-10-15-paket-11-mcp-fremdserver-und-einbettung.md) — erledigt dort: Werkzeuge weiterer MCP-Server (nur lesend, eigener Namensraum, Review 8/8 behoben), Kommando zum Einbettungswechsel, Studio-Akzentfarbe, Dokument für das MCP-Team, Prüfung auf Drittressourcen (nichts gefunden).
- **Paket 10 (drittes Audit vom 2026-10-10 und Paket-9-Prüfer):** [`2026-10-14-paket-10-drittes-audit.md`](plans/2026-10-14-paket-10-drittes-audit.md) — erledigt dort: alle Befunde aus Fehlerprotokoll und Kurzaudit, die sich am Quelltext bestätigten (H-2, H-3, M-1 … M-8, L-1, L-3, L-4, L-5, L-7, L-9, L-12, A-1, A-3, A-8, A-10, S-1, Drift), M-3 gemessen (trägt heute nicht), dazu die 14 Befunde des Paket-9-Prüfers (P9-1 kritisch: Suchen nach `query_knowledge` galten als „nicht im Katalog“). Entscheidungen (H-1, S-2, S-6(b) und A-6 gefallen, S-7 umgesetzt; A-2, A-4, A-7, A-9, P9-3 offen) in `entscheidungen-offen.md`.
- **Paket 12 (Werk und eigene Fassung):** [`2026-10-16-paket-12-werk-und-eigene-fassung.md`](plans/2026-10-16-paket-12-werk-und-eigene-fassung.md) — Werksfassung (Seed) plus umschaltbare eigene Fassung je Bereich, `migrate` = Werksabgleich, Review behoben.
- **Paket 17 (b-api-Router, Schlüssel des Proxys, Clusterfähigkeit, Übergabe an den Betrieb):** [`2026-10-20-paket-17-b-api-router-und-betriebsuebergabe.md`](plans/2026-10-20-paket-17-b-api-router-und-betriebsuebergabe.md) — erledigt dort: `B_API_ROUTE`, durchgereichter Schlüssel samt Schalter `B_API_KEY_MODE` (auto/static/forward), interner Port 8101 mit `/health` `/ready` `/metrics`, JSON-Logs und Trace-ID, öffentliche Spec, Helm-Werte, Lauf-Herzschlag (0014), geteilter Master-Skill-Stand (0015), Lauf-Abschluss beim Herunterfahren, `FORWARDED_ALLOW_IPS`. Offen: D10 (Ressourcen unter Last messen, braucht einen Lasttest), die Nutzer-Eintragungen in `uebergabe-betrieb.md` (Ansprechperson, Wartung, Spec-Text, SSE mit Wolli) und die Klärung mit dem b-api-Team (Proxy-IP, Weitergabe der Nutzer-Adresse).
- **Paket 18 (Störtest-Audit und Fehlerbehandlung):** [`2026-10-28-paket-18-audit-und-fehlerbehandlung.md`](plans/2026-10-28-paket-18-audit-und-fehlerbehandlung.md) (18A/18B), [`2026-10-29-paket-18cd-volle-umsetzung.md`](plans/2026-10-29-paket-18cd-volle-umsetzung.md) (18C/D) und [`2026-10-30-paket-18ef.md`](plans/2026-10-30-paket-18ef.md) (18E/18F) — erledigt und gemergt (PR #27–#35): Moderationsausfall sichtbar, mehrere Medientypen, Logs ohne Inhalte, Zugakte und Fehlernummer, `ui` statt `debug` für alle, still geschluckte Ausnahmen, Schalter wie das Gate, Datenschutz fail-closed, abgelehnter LLM-Schlüssel, Frist beim LLM-Platz, Ratenlimit 120/min, 429 im Widget. Rückmeldung an die Audit-Personen: [`audits/2026-10-28-audit-follow-up.md`](audits/2026-10-28-audit-follow-up.md). Offen: siehe §2, §4, §6.
- **Paket 19 (Audit 2026-10-31):** [`2026-10-31-paket-19-audit-befunde.md`](plans/2026-10-31-paket-19-audit-befunde.md) — alle Befunde des Audits [`audits/2026-10-31-audit.md`](audits/2026-10-31-audit.md) behoben, gemergt (PR #42, main `483ea45`). Entscheide in §2.
- **Paket 20 (Aufräumen aus §5):** [`2026-10-31-paket-20-aufraeumen.md`](plans/2026-10-31-paket-20-aufraeumen.md) — A1–A3 und B1–B3 erledigt (in §5 vermerkt); der Rest von §5 bleibt und läuft mit, wenn die Dateien angefasst werden.
- **Paket U1 (UI-Module):** [`2026-11-02-paket-u1-ui-module.md`](plans/2026-11-02-paket-u1-ui-module.md) — U1-a … U1-f umgesetzt und reviewt (Stand 2026-11-03); U1-g (UI-Module in der Evaluation, §17) umgesetzt und reviewt (14 Befunde behoben, Stand 2026-11-03). U1-h (Unterthemen im selben Themenbaum aufklappen, §18, eigener öffentlicher Endpunkt `POST /api/ui/themenbaum/zweig`) umgesetzt und reviewt (11 Befunde behoben, Stand 2026-11-03). Offen: die Punkte „Paket U1“ in §1, §2 und §5; Einzelheiten im Plan unter „Offen“ von §13, §15 und §16.
- **Paket U2 (Themenbaum: Bestand und KI-Entwurf):** [`2026-11-04-paket-u2-themenbaum-entwurf.md`](plans/2026-11-04-paket-u2-themenbaum-entwurf.md) — umgesetzt 2026-11-04 (zwei Module `ui_themenbaum` / `ui_strukturentwurf`, gemeinsamer Kern `_baum/`, Dienst `strukturentwurf`, Brücke `edit_collection_as_draft`, Master-Skill-Regeln, Gold-Abläufe GV-UI-8 … 12). **Master-Skill geändert** (`docs/skills/vorgehen-knapp.md`, zuletzt im dritten Review 2026-11-05): muss in den WLO-Knoten übertragen werden. Offen: Plan §7 und §9 D6 (Knopf „Als Entwurf bearbeiten“ je gemeldeter Module — begründet nicht umgesetzt). Dazu erledigt am 2026-11-05: die rechtliche LLM-Stufe scheiterte mit gpt-6-luna still (json-Hinweis; Änderungsnotiz U2, Abschnitt „Fix rechtliche Prüfung“).
- **MCP-Vertrag (M1–M7, 2026-11-07):** [`2026-11-07-mcp-vertrag.md`](plans/2026-11-07-mcp-vertrag.md) — der Chatbot
  am MCP-Stand vom 07.11.: Fehler mit Code, Abnahme aus `structuredContent.confirm`, Anlegen mit Sammlung in einer
  Bestätigung (`addToCollectionId`, `find_content_by_url`), Übersicht/Zählung/Skill-Wahl per `task`, Pläne
  (Sammlungsbaum, Massen-Aufnahme, „Plan fortsetzen“, bis 08.11. „Weiter anlegen“), letzte Ablagen im Upload-Modul. Je Paket eine Notiz
  `aenderungen/2026-11-07-paket-m{1..7}-*.md`; Offenes unten in §3 (U3-3), §4 und §6.
- **Paket 4 (externes Audit und Restliste):** [`2026-10-03-paket-4-audit-extern.md`](plans/2026-10-03-paket-4-audit-extern.md).
  - Status: freigegeben und umgesetzt 2026-10-03 (Phasen V, A–E, L, S; Log im Plan). Zurückgestellt an Paket 5 bzw. ins Backlog: siehe Plan §5/§6.
  - Er gleicht das externe Audit [`audits/2026-10-03-audit-extern.md`](audits/2026-10-03-audit-extern.md) (Stand `610abec`) mit `e38006d` ab.
  - Jeder Befund geht an eine Aufgabe, an Paket 5 oder ins Backlog.
- **Audit 2026-09-29:** [`audits/2026-09-29-audit.md`](audits/2026-09-29-audit.md) — behoben dort: der Transport-Retry mit `confirmToken` und das Token im INFO-Log (früher §1.2/§1.3), `pip-audit` (jetzt in der CI), zwei Aufräumpunkte aus §5 und eine der unter Last kippenden Test-Dateien (siehe §5).

## 1 Befunde mit Wirkung im Betrieb

- **Formeln im Widget falsch dargestellt (Nutzer 2026-11-10) — für den nächsten Plan.** Im Widget
  werden Formeln für die Person nicht korrekt angezeigt (etwa LaTeX-Ausdrücke in Erklärungen von
  Mathe/Physik). Noch nicht untersucht: welche Schreibweise das Modell liefert (`$…$`, `\(…\)`,
  Unicode), was der Markdown-Weg im Widget daraus macht (Bubble, `ui_inhaltsrahmen`, Druckfenster)
  und ob eine Darstellung ohne fremde Netzquelle möglich ist (Guardrail: keine CDN-Schriften/
  -Skripte aus dem Netz). **Aufnehmen in den nächsten Plan** als eigenes Paket: Befund nachstellen
  (Beispiele aus echten Antworten), Lösungswege abwägen (Formel-Renderer im Bündel und Budget,
  Unicode/Text-Fallback, Prompt-Vorgabe an das Modell), Entscheid, Umsetzung mit Specs.
- ~~**Widget-Bündel am Budget (2026-11-10):** Haupt-Bündel 199,93 kB gzip bei harter Grenze 200 kB.~~
  **Erledigt mit Paket BU (10.11., Plan `2026-11-09-ablaeufe-im-studio.md` §5i):** BU-1 (Debug-Panel
  ohne Pipes, Logo gerundet), BU-2 (`ui_strukturentwurf` nachgeladen) und BU-3 (Debug-Panel
  nachgeladen) bringen das Widget mit AS-Ud auf **186,9 kB gzip / 644,8 kB roh** (Stand 10.11.), also
  unter die Warnschwelle von 190. Notizen `aenderungen/2026-11-10-paket-bu-*.md`.
  **Weiter gilt:** Neue, selten gebrauchte Widget-Oberfläche wird nachgeladen, sobald sie mehr als
  2 kB gzip kostet oder das Bündel über 190 kB triebe (Plan §5j, Ud-5). Nächster Kandidat mit
  Messung: `ui_themenbaum` (18 kB roh).

- ~~**Wahl mit ≥ 4 Chips schneidet den Ablauf-Knopf ab (offen seit AS-5b, verschoben aus §4):**~~
  **Erledigt 10.11.** (`wahl_zug.platz_fuer_vorschlag`, Notiz `aenderungen/2026-11-10-befunde-nach-pr51.md`): Wartet
  ein Lauf an einer Wahl mit vier oder mehr Chips, schneidet `anhaengen(alle=True)` den Knopf eines
  Ablauf-Werkzeugs ab, obwohl das Werkzeug angeboten wird. In AS-U nicht behoben. Vorschlag: in
  diesem Fall kein Ablauf-Werkzeug anbieten (wie bei Gastgeber-Chips) — eigenes kleines Paket.

- **Lehrplan-PDF → Themenbaum: Probe vom 10.11.** (Notiz `aenderungen/2026-11-10-probe-lehrplan-upload.md`).
  Der Weg funktioniert: das Hochladen, markitdown und `ui_strukturentwurf` mit `aus_dokument` laufen durch
  (Ausbildungsrahmenplan, 23 Abschnitte, 37 Punkte). Die Schleife ohne Anmeldung ist behoben. **Seit dem
  Nutzer-Entscheid vom 10.11. geht das auch anonym** (`dokument_ohne_anmeldung` Vorgabe an). Offen bleibt:
  - **Die KI zeigt das Auswahlfeld nicht immer.** In einem von drei Läufen beschrieb sie es nur
    („Wähle die PDF … aus“). Die Regel „Lehrplan → `ui_upload`“ steht im Master-Skill
    `docs/skills/vorgehen-knapp.md` (U3-5). Im WLO-Knoten fehlt sie noch; der Nutzer aktualisiert den
    Master-Skill. Danach Golden GV-UI-13/14 (startet der Nutzer).
  - **Versprechen vor dem Auswahlfeld (nur noch bei „Aus“ im Studio):** Den `hinweis` schreibt die KI, bevor
    sie die Schalter kennt. Ist Lesen nur für Angemeldete eingestellt, verspricht er zu viel; das Modul sagt
    es danach richtig. Kandidat: Das Modul nennt die Anmeldung gleich unter dem Hinweis.
  - **Lesen, dann anmelden:** Ein anonym gelesenes Dokument gehört `aufrufer=None`
    (`services/dokumente/stand.py`, `ablage.py`). Meldet sich die Person zwischen Lesen und Entwurf an,
    findet der Entwurf es nicht mehr (`kein_dokument`), und sie muss es noch einmal lesen lassen. Kandidat:
    beim Laden auch das Dokument derselben Sitzung ohne Besitzerin annehmen und es dann der Person
    zuschreiben. Das ist ein Entscheid über Besitz, darum offen.
  - Die Zeile „[ edu-sharing Skill ] Chatbot Masterskill - aktiv“ über den Antworten ist **gewollt**
    (Aktivierungszeile des Master-Skills im WLO-Knoten, Nutzer 10.11.).

- **Führungen (AS-7, 10.11.) — Grenze aus dem Querschnitts-Review, Befund 4:** Bei angemeldeten Personen
  holt der Verlauf den Stand nur, wenn der MCP die Anmeldung binnen 1 s bestätigt (Z-6). Sonst fehlt nach
  einem Seitenaufruf der Stand, und es geht kein Seiten-Ping hinaus. Die Ankunft kommt dieses eine Mal
  nicht an; der nächste getippte Satz holt den Chip zurück, der nächste Seitenaufruf pingt wieder.
  Kandidat: bei einer Zeitüberschreitung ein Kennzeichen `ablauf_unbestimmt`, und das Widget pingt dann einmal.
- **Führungen (AS-7, 10.11.):** ~~E2E für Führungs-Chip, Seiten-Ping und Begrüßungs-Chip fehlt noch.~~
  **Erledigt 10.11.:** Browser-Abnahme (`aenderungen/2026-11-10-browser-abnahme-as-7.md`) und E2E für den
  Kernweg (`frontend/e2e/fuehrung.spec.ts`, Notiz `aenderungen/2026-11-10-e2e-fuehrung.md`). Offen bleibt
  ein E2E für das Angebot unter der Begrüßung (Auslöser `seite`), durch Specs abgedeckt. Angular meldet für das Widget-Roh-Budget 650 kB eine Überschreitung um wenige Byte (Warnung);
  gzip 188,6 kB < 190.

- **Upload → Volltext → Metadaten (Anwendungsfall „Strukturdokument + Inhalte“, 2026-11-07):** Auftrag an das
  MCP-Team [`mcp-auftrag-volltext-metadaten.md`](mcp-auftrag-volltext-metadaten.md) (W1 Volltext an Knoten, W2/W3 als
  Plan, W4 Rolle im Stapel). Entscheid: der Chatbot steuert auch die Kestra-Flows. Die B-API erlaubt Flows derzeit nur
  Lesen; geschrieben wird über den MCP. **Später klären:** Benachrichtigung über das edu-sharing-Frontend, wenn ein
  Flow fertig ist.
  - **MCP-Stand 2026-11-08: W1–W4 geliefert** (live erst nach dem MCP-Deploy). W4 ist angebunden
    ([`aenderungen/2026-11-08-w4-rolle-im-stapel.md`](aenderungen/2026-11-08-w4-rolle-im-stapel.md)).
    W1–W3 (`wlo_attach_fulltext(s)`, `wlo_update_contents`) sind seit K2d-3 als Werkzeuge des Agent-Modus und
    von M18 angebunden, W2/W3 als Pläne
    ([`aenderungen/2026-11-08-paket-k2d3-volltexte-und-metadaten.md`](aenderungen/2026-11-08-paket-k2d3-volltexte-und-metadaten.md));
    als Ablaufschritt seit Paket S nur W1 (W2/W3 sind Pläne und bleiben vorerst dem Chat). Knopf
    „Plan fortsetzen“, Wartezeit bei „ausgelastet“ und der
    Durchlauf-Test W2/W3 sind erledigt ([`aenderungen/2026-11-08-kleine-punkte-nach-k2d.md`](aenderungen/2026-11-08-kleine-punkte-nach-k2d.md)).
    Offen: `would_replace_file` merkt den Text nicht vor — ein echtes Vormerken im Vorgang wäre ein eigenes Paket.
    `WriteGate.prepare` (Agent-Modus `execute`) gibt die Freigabe bei „ausgelastet“ ohne Code zurück (erledigt
    08.11.); bei `upstream_busy` bleibt sie verbraucht (Ausgang aus dem Text nicht ablesbar).
    Zu beachten: Datensätze mit Datei lehnt W1/W2 vorerst mit `would_replace_file` ab (bis zur Messung des
    MCP-Teams) — beim Upload-Fall also immer; das ist „vorgemerkt“, kein Fehler. Staging nimmt seit 06.11. keinen
    Inhalt an (500 `InvalidTypeException`). Neue Codes `changed_since_preview`, `file_replaced`, `upstream_busy`.

- **Stabilität der MCP-Anbindung (2026-11-07):** umgesetzt gegen den ausgerollten MCP-Stand S1–S7. Plan
  [`plans/2026-11-07-stabilitaet-mcp-anbindung.md`](plans/2026-11-07-stabilitaet-mcp-anbindung.md), Rückmeldung
  an das MCP-Team [`mcp-rueckmeldung-2026-11-07.md`](mcp-rueckmeldung-2026-11-07.md) (3 kleine Befunde dort).
  - Erledigt damit: der offene Befund „bestätigter Schreibaufruf ohne Antwort → bitte nachsehen“ (früher §1.2),
    soweit der Server die erste Antwort noch kennt (30 min, kein Neustart).
  - Noch offen:
    - der Client-Schlüssel (Tausch mit dem MCP-Team);
    - der Lasttest mit 30 Personen (startet der Nutzer).
  - Der Block liegt weiter im `sessionStorage` der Gastseite: R1 begrenzt das auf 12 h. Die Bindung an die
    Sitzung im Backend ist ein eigenes Paket.

- **Querschnitts-Review 2026-11-06** (Pakete V1 … U3-3b, K1b): alle 7 MAJOR und die MINOR/NIT behoben in den
  Paketen Q1–Q4 (Plan [`plans/2026-11-06-querschnitts-befunde.md`](plans/2026-11-06-querschnitts-befunde.md),
  Notizen `aenderungen/2026-11-06-paket-q{1,2,3,4}-*.md`). Beim Deploy: Migration **0020**, Widget-Bündel neu.
  Noch offen daraus: ein Einstieg zu „Arbeitsstand löschen“ außerhalb eines Ablaufs (Entscheid);
  `ui_auftrag._wartender_auftrag` liest den Verweis ohne Auffrischen; theoretische Verklemmung Verdrängen in
  `vorgaenge.anlegen` gegen die sortierte Sperre in `dokument_teile_entfernen`; Bestands-Brücke und alter
  `draft` (bewusst, Q4-Notiz); `Teil` doppelt definiert. Nicht in diesem Plan: markitdown-Update/`pip-audit`,
  Multipart vor den Prüfungen (Starlette), Text in 429-`detail`, `_`-Entities des Klassifikators.

1. **Klassifikator ohne Prompt-Cache auf dem Responses-Weg** (abgeleitet in Paket 7, nicht gemessen; nur Muster-Modus).
   - Der Systemprompt des Klassifikators endet mit dem Zug-Kontext (Zugzähler, Zustand, Entities — `services/classify_prompt.py`, `_dynamic_block`). Auf `/v1/responses` steht er ganz in `instructions`, und jede Änderung dort kostet den ganzen Cache (Responses-Plan §2.4). Bei gpt-6 über OpenAI direkt wäre damit jede Klassifikation ungecacht.
   - Hebel wie in Paket B: den Zug-Kontext als Nachricht hinter den festen Teil setzen. Vorher nachmessen (`usage.cached_tokens` je `classify`-Phase im Debug-Block).
2. **Befunde aus dem Audit 2026-09-29**, die noch offen sind: siehe [`audits/2026-09-29-audit.md`](audits/2026-09-29-audit.md), Abschnitte 6–9. Behoben sind die Punkte der Tabelle in Abschnitt 4a (seit Tag `0.3`).
3. **Externes Audit 2026-10-03** (22 Befunde, Stand `610abec`), am Stand `e38006d` gegengeprüft:
   - 12 gelten weiter, 7 sind teilweise behoben, 3 sind behoben bzw. ohne die behauptete Wirkung.
   - Abgleich, Vermerke und Zuordnung stehen im Paket-4-Plan, §1.
   - Neu gegenüber dieser Liste:
     - Schreib-Abnahme ohne Identitätsprüfung beim Einlösen;
     - RAG-Import verliert Text;
     - Agent-Frist und Budget greifen nicht in laufende Aufrufe;
     - Ergebnis-Schema wird nicht geprüft;
     - MCP-Cache ohne Server;
     - Konfig-Abrufe überholen sich.
   - Paket 4 (2026-10-03/04) hat alle Befunde behoben, die nicht auf eine Entscheidung warten. Offen sind die Paket-5-Punkte (Plan §5) und das Backlog (Plan §6).
- **Vorschläge C-1…C-6 aus dem MCP-Feedback** (Paket 11; C-5 und der Teil von C-3 zu `search_skill`/`excludeNodeIds` umgesetzt in J, C-1 umgesetzt in L — der Rest wartet auf den MCP-Neubau): Plan Paket 11, Abschnitt „Vorschläge für den Chatbot aus dem MCP-Abgleich“; Feedback an das MCP-Team in [`mcp-feedback-werkzeuge.md`](mcp-feedback-werkzeuge.md) — u. a. `lookup_wlo_vocabulary`-Beschreibung (verursacht 339 unnötige Aufrufe), Karten aus `structuredContent`.
- **Chat-Proben 2026-10-17** (16 Abläufe + Wiederholungen am Testcontainer, Vokabular und Master-Skill-Kurzfassung):
  - Vokabular-Abgleich trägt: Fach, Stufe (auch „Klasse 6“, „Sek 2“), Inhaltstyp (auch „Podcast“ → Audio) und Lizenz (OER, `CC BY-SA 4.0` → `CC_BY_SA`, gemeinfrei → `PDM`; Unbekanntes fällt weg).
  - Behoben am selben Tag: Platzhalter „ein Thema“ auf einer Sammlung → Seitenregel im Code (`seitenkontext_prompt`) plus Master-Skill; Filter sparsam (Nutzer-Vorgabe: Fach, Bildungsstufe, Inhaltstyp; Lizenz und Zielgruppe nur auf Wunsch — Master-Skill und Werkzeugbeschreibungen); Anrede bleibt im Gespräch; Rettung ohne Treffer führt die Schritte selbst aus; Quiz-Lösungen mit Begründung; Kernbegriff auch in der Sammlungssuche; Muster-Modus ersetzt die Antwort bei 0 Inhaltstreffern nicht mehr durch „… dort finden Sie die gefilterten Treffer“.
  - Zweite Runde (Image `proben-lokal`, Master-Skill 19/19 im Knoten): Platzhalter auf der Sammlung 5/5 erst Rückfrage mit drei Unterthemen (vorher 2/6); kein Lizenz- oder Zielgruppenfilter ohne Wunsch (Eltern, Videos ohne OER); Rettung führt Lockerung selbst aus; Quiz mit Begründung — danach ergänzt: richtige Antwort über die Positionen verteilen (war fünfmal „A“).
  - Beobachtet, nicht geändert: bei „Bruchrechnen für Eltern“ setzte der Agent `Sekundarstufe I` ohne Stufenangabe; bei unklarer Zielgruppe duzt er auf einer Sammlung meist; im Muster-Modus suchte eine Folgesuche einmal mit dem ganzen Nutzersatz (Muster-Prompts, nicht der Master-Skill).
  - Dritte Runde (gleicher Tag), Beobachtungen gelöst: Vorabsuche übernimmt die Entität `lizenz` (Programmfehler, `prefetch`); Beispiel `Alle OER` → `OER` in `04-entities` (Server ignoriert „Alle OER“: 3 616 Treffer wie ungefiltert, „OER“ 941); Domänenregeln (`02-domain/domain-rules.md`, Muster-Modus): `query` nur Kernbegriff auch in Folge- und Rettungssuchen, Filter sparsam, verlangte Lizenz bleibt gesetzt; Master-Skill: Stufe und Fach nie aus dem Thema erschließen, Anleitungen/Kompendium/Seitentext geben keine Anrede vor, Rettung lockert zuerst Inhaltstyp und Stufe, eine verlangte Lizenz nur mit Hinweis. `quick_replies.max_count` bleibt 2 (Studio-Einstellung); der Master-Skill verlangt keine drei Vorschläge mehr.
  - Vierte Runde (Master-Skill 22/22 im Knoten): keine erfundene Stufe mehr (Bruchrechnen für Eltern); verlangte OER-Lizenz bleibt im Muster-Modus gesetzt, der Agent lockert sie nur mit Hinweis; Anrede bei unklarer Zielgruppe in allen Rückfragen „Sie“; Platzhalter auf der Sammlung 3/4 erst Rückfrage (zusammen mit Runde 2: 8/9); Quiz verteilt die richtige Antwort, die Begründung fehlte in 1 von 2 Läufen — Kandidat: Format-Beispiel „1. B – weil …“ in M10.
- **Paket U1 — Direktaktion „Inhalte anzeigen“ ohne Angebotsprüfung** (Plan §15 „Offen (U1-e)“): `_handle_browse_collection` ruft `get_collection_contents`, ohne zu prüfen, ob das Werkzeug angeboten ist (Studio-Schalter, Sperren, Modus der Einbettung). `themenbaum_aktion` prüft seit Review U1-e #3 über `agent_tools.angebotene_mcp_werkzeuge`; hier fehlt das Gegenstück. Bestand vor U1-e.
- **Zweites Review K2b (2026-11-08), älter als K2b:**
  - Der Deckel der Schnellantworten (`widget_postprocess`, `max_count`, Muster, Gastgeber) streicht auch
    System-Knöpfe (`__action__`: „Weiter im Ablauf“, „Stand prüfen“, „Neues Vorhaben“ …), sobald er kleiner ist als
    ihre Zahl. Im gesperrten Lauf behält er seit K2b die beiden Auftrags-Knöpfe; allgemein offen.
  - Mit `MODERATION_FAILURE_MODE=closed` ist jede Direktaktion gesperrt, solange die Moderation ausfällt — auch
    „Stand prüfen“ und „Abbrechen“, deren Parameter keinen Text der Person tragen.
  - Die Seitenwege `/api/ui/*` (Ablage, Upload, Themenbaum) sind keine Chat-Züge und kennen die Sperre nicht —
    vermutlich gewollt, zu bestätigen.
- **Pakete M1, U4, U5, U3-5 (2026-11-08), offen:** Plan
  [`plans/2026-11-08-pakete-m1-u4-u5-u3-5.md`](plans/2026-11-08-pakete-m1-u4-u5-u3-5.md), Notizen
  `aenderungen/2026-11-08-paket-{m1,u4,u5,u3-5}-*.md`.
  - Master-Skill (`docs/skills/vorgehen-knapp.md`) in den WLO-Knoten übertragen (Nutzer), dann Golden-Lauf
    GV-UI-13 … 16 (Nutzer).
  - Messen: Kostet `includeContentCounts` bei Tiefe 2 zu viel (ein Aufruf je Sammlung)? Reicht `contentsCount`?
  - Der Lücken-Abschnitt nennt bei Ebene 2 den Elternpunkt nicht; die Blockgröße steigt mit Abdeckung um
    höchstens etwa 60 kB.
  - M2 (`browse_collection_tree` Tiefe 3) bewusst nicht umgesetzt (E-10); O-13 („reicht Tiefe 2?“) bleibt bis
    zur Messung offen.
  - Browser-Abnahme der Module `ui_strukturabgleich` (mit und ohne Abdeckung) offen.
- **Paket S (2026-11-08), offen:**
  [`aenderungen/2026-11-08-paket-s-schreibende-schritte.md`](aenderungen/2026-11-08-paket-s-schreibende-schritte.md)
  - Ein Ablauf löscht nicht (`wlo_delete_content`, `wlo_delete_collection` ausgeschlossen, eigener Entscheid —
    bei Bedarf umstellbar in `werkzeuge._NICHT_IM_ABLAUF`).
  - Pläne als Ablaufschritt: erledigt mit S4
    ([`aenderungen/2026-11-08-paket-s4-plaene-als-schritt.md`](aenderungen/2026-11-08-paket-s4-plaene-als-schritt.md)).
  - Ein „ja“ zu einer Freigabe, deren Lauf nicht mehr wartet, schreibt nicht (eigener Entscheid, Gesamt-Review).
  - `freigabe` an `auftrag`, sobald die B-API schreibende Flows kennt.
  - Der Nachlauf nach dem „ja“ läuft vor der Sicherheitsprüfung mit leeren Sperren. Vertretbar, weil die
    Nachricht ein kurzes, geprüftes Ja ist.
  - Ein „ja“ speichert zwei Assistenten-Nachrichten (Einlösen und Ablauf); live ist es eine Blase.
  - Unter gewöhnlichen Antworten steht nur „Vorschau erneut zeigen“, ohne „Ablauf abbrechen“ (Deckel der
    Schnellantworten).
  - Browser-Abnahme (Studio-Formular, Widget-Box) offen.
- **Review K2c-1/K2c-4 (2026-11-08), älter:** erledigt — `bei_fehler` nur bei `modul`, `werkzeug`, `agent`,
  `auftrag` (Befund sonst), `weiter` als Liste außerhalb einer Verzweigung gilt im Treiber wie kein `weiter`
  ([`aenderungen/2026-11-08-kleine-punkte-nach-k2d.md`](aenderungen/2026-11-08-kleine-punkte-nach-k2d.md)).

## 2 Entscheidungen des Nutzers

- ~~**Preis für `gpt-6-luna` fehlt in der Preistafel des Seeds**~~ — erledigt 2026-10-18: die Werksfassung `01-base/pricing` trägt die OpenAI-Listenpreise (Standard, kurzer Kontext) in **USD** (Nutzer-Entscheid; hebt „Seed ohne Preise“ auf). Nicht abgebildet: Cache-Schreibpreise, langer Kontext, abweichende Abrechnung über b-api/AcademicCloud. Achtung Präfix-Suche: eine ungelistete Variante (etwa `gpt-5.4-nano`) bekäme still den Preis von `gpt-5.4`. Eine Anlage, deren Preistafel unberührt ist, übernimmt die Preise beim nächsten Werksabgleich (`migrate`).
Kurz erklärt — je Punkt, worum es geht und welche Antwort gebraucht wird — in [`entscheidungen-offen.md`](entscheidungen-offen.md). Die Entscheide vom 2026-10-09 sind in Paket 7 und Paket 8 umgesetzt (siehe die Plan-Liste oben); offen ist:

- **AcademicCloud und Einbettungen:** entschieden 2026-10-15 (so lassen); Einbettungswechsel machbar machen → Paket 11 (D), [`plans/2026-10-15-paket-11-mcp-fremdserver-und-einbettung.md`](plans/2026-10-15-paket-11-mcp-fremdserver-und-einbettung.md).
- **Neue MCP-Server und ihre Werkzeuge:** Nutzer 2026-10-15: sollen nutzbar sein → Paket 11 (E). MCP- und Anmeldungs-Punkte für das MCP-Team: [`mcp-und-anmeldung.md`](mcp-und-anmeldung.md).
- **Paket 18, E5 — Agent-Deckel für Anonyme:** Nutzer-Entscheid 2026-10-28: erst die Kosten eines anonymen Zugs messen, dann entscheiden (Audit-Rückmeldung §5). **Entschieden 2026-10-31:** anonyme Züge sollen im Studio eigene Werte bekommen können, Vorgabe = dieselben wie mit Anmeldung — **ist so gebaut**: Agent-Deckel `agent.anonymous` (Runden, Frist, Token-Budget; als Minimum angewandt, ein höherer anonymer Wert hebt nichts an) und seit Paket 19 die Zug-Grenzen `safety-config.turn_limits` (anonym/angemeldet). Kein Code nötig.
- **Paket 18A — `MODERATION_FAILURE_MODE`:** `open` (Vorgabe, Zug läuft ungeprüft weiter, Zähler und Alarm) oder `closed` (Zug wird höflich abgewiesen) für den Betrieb festlegen (Steckbrief Punkt 10).
- **Paket 18G, G-E2 — Entwicklungsmodus:** Mit `BOERDI_ALLOW_OPEN_ADMIN` ohne Studio-Passwort und ohne `STUDIO_API_KEY` buchen Studio-Züge auf `B_API_KEY`, auch unter `B_API_KEY_MODE=forward`. Empfehlung: so lassen (die Chat-Probe läuft lokal ohne eigenen Schlüssel), Entscheid steht aus.
- **Paket 18G — Fehlernummer bei festem Vorsatz:** Schickt ein Aufrufer `x-client-trace-id` mit festem Vorsatz (`dienst-<uuid>`), tragen alle seine Züge dieselbe Fehlernummer (die ersten 12 Zeichen). Mit Team 6 klären, welche IDs der B-API-Proxy schickt; sonst einen serverseitigen Anteil in die Nummer nehmen. (Stand 2026-10-31: Nutzer kann derzeit keine Auskunft geben — bleibt offen.)
- **Paket 19 (Audit N-8) — PII im Sicherheitsprotokoll:** Erkannte personenbezogene Daten (E-Mail, Telefon, IBAN …) heben die Stufe auf `medium`; genau diese Nachrichten stehen mit den ersten 500 Zeichen im Klartext und der IP in `safety_logs` (`obs/quality_events.py:77`). Die Frist ist seit Paket 19 (P19-E4) 30 statt 90 Tage. Offen: die PII-Treffer geschwärzt speichern? Abzuwägen ist die Nachvollziehbarkeit von Verstößen (P19-E1) gegen die Datensparsamkeit. **Nutzer-Entscheid 2026-10-31: bleibt lesbar, wird nicht anonymisiert.** Zweck und Frist gehören in die Datenschutzerklärung.
- **Paket 19 (Review 19-1) — Titel fremder Seiten im Metadaten-Cache:** Für eine nicht auflösbare Seite cacht `services/page_context.resolve_page_context` den Tab-Titel als `entities._page_metadata.title` (Gruß und Prompt der Folgezüge lesen ihn) — bei fremden Seiten ein Stück Browserverlauf, 30 Tage. Titel und Suchbegriff als eigene Entities fallen seit Paket 19 weg; ob auch der Cache bei `external` ohne Titel auskommt (der Gruß nennt dort den Host), ist zu prüfen. **Nutzer-Entscheid 2026-10-31: bleibt so.** Der Titel ist Kontext für Seitenerkennung und Aktionen; der Chatbot ist nicht für fremde Seiten gedacht. Eine Lösung „im Zug nutzen, vor dem Speichern entfernen“ erst nach gründlicher Folgenprüfung (nachgelagerte Aktionen, Auswertungen).

- **Paket U1 — offene Entscheide** (Plan [`2026-11-02-paket-u1-ui-module.md`](plans/2026-11-02-paket-u1-ui-module.md)):
  - `ui_upload` (§13, „Konzept `ui_upload`“): wer darf hochladen (**entschieden 10.11.:** Dokument lesen und
    Entwurf auch anonym, Ablage in WLO nur angemeldet) und mit welchen Grenzen; Aufbewahrung samt Datenschutz-Hinweis; Ziel (nur Kontext im Chat, edu-sharing, Kestra); Virenprüfung; Formate über MarkItDown hinaus (OCR). Die übrigen vorgeschlagenen Module (`ui_freigabe`, `ui_fortschritt`, `ui_befund`, `ui_themenbaum_auswahl`) sind nicht freigegeben. `ui_freigabe` entfällt seit Paket S: ein schreibender Ablaufschritt zeigt die Vorschau-Box und den Chip des Chats.
  - Themenbaum statt `browse_collection_tree`: die Master-Skill-Kurzfassung (`docs/skills/vorgehen-knapp.md`, live) ist seit 2026-11-03 auf `ui_themenbaum` umgestellt. Offen: `docs/skills/vorgehen.md`, `docs/skills/vorgehen-kompakt.md`, `services/response_prompt_tools_text.py` und die Muster, die `browse_collection_tree` nennen — umstellen oder so lassen (§15 „Offen (U1-e)“).
  - Textfassung im Verlauf für abgeschaltete Module (§16, F-2 und „Offen (U1-f)“): heute bleiben gespeicherte Blöcke, wie sie gezeigt wurden; rückwirkend verschwinden bräuchte eine Widget-Regel „leere Daten → Textfassung“.
  - Themenbaum: Nachgeladenes (U1-h, §18 H-8) gilt nur bis zum Neuladen der Seite; der Verlauf zeigt den ursprünglichen Baum. In die gespeicherte Nachricht schreiben hieße einen Schreibweg ohne Zug (und `eingabe` kennt nur eine Ebene Kinder) — ja oder nein?
  - **Golden-Lauf 2026-11-03 (Agent, gpt-6-luna, Testcontainer `ui-abstaende-5659fed`)** — Reports `evals/reports/golden-20261103-112633-u1-ui-agent.json`, `…-113227-u1-seed-agent.json`, `…-113234-u1-ui7-muster.json`. Seed-Suite 90/91 hart (98,9 %); UI-Abläufe 28/32 (87,5 %); GV-UI-7 Muster 4/4. Befunde zum Entscheiden:
    - **`ui_entscheidung` wählt der Agent nie** (GV-UI-3/4/5): bei offenen Anfragen sucht er zuerst und fragt im Text nach („Zuerst handeln“ des Master-Skills). Entweder die Master-Skill-Vorlagen (`docs/skills/vorgehen*.md`) nennen das Auswahlfeld für echte Wahlfragen (z. B. Bausteine einer Stunde, Klassenstufe vor einer Übung), oder die Abläufe erwarten `ui_trefferliste` statt `ui_entscheidung`.
    - **Unterthema per Text** (GV-UI-1 Zug 2 „Optik eine Ebene tiefer“): der Agent ruft zweimal das rohe `browse_collection_tree` und listet die Themen als Text (Trefferliste statt Baum), weil `ui_themenbaum` eine `nodeId` braucht, die er aus der Quittung nicht kennt. Hebel: Werkzeugbeschreibung/Master-Skill „Knoten erst mit `browse_collection_tree` finden, dann `ui_themenbaum(nodeId)`“ — oder ein Argument `thema` (Titel unter dem Fachportal) im Modul.
    - **Anrede**: zwei Fehlschläge `register` (GV-UI-1 Zug 1, GV-LEH-1 Zug 2) — Antwort duzt eine Lehrkraft; vorbestehend, nicht U1.
    - **Stand 2026-11-03:** Werkzeugbeschreibungen (`ui_entscheidung`, `ui_themenbaum`) und Master-Skill-Kurzfassung (`docs/skills/vorgehen-knapp.md`) angepasst — [`aenderungen/2026-11-03-master-skill-ui-module.md`](aenderungen/2026-11-03-master-skill-ui-module.md). In den Knoten übertragen und gemessen: zweiter Lauf unten.
    - **Ausreißer Latenz**: GV-UI-4 Zug 2 52 s (5 Runden, `get_node_collections` allein 24 s).
    - **Zweiter Lauf 2026-11-03 (Agent, nach Übertragung der Kurzfassung in den Knoten)** — Reports `evals/reports/golden-20261103-122516-ms-ui-agent.json`, `…-123158-ms-seed-agent.json`. UI-Abläufe 27/31 hart (87,1 %), Seed-Suite 89/91 (97,8 %). Befunde:
      - **Auswahlfeld kommt** (GV-UI-4 Zug 1: `ui_entscheidung` samt Trefferliste). GV-UI-3 Zug 1 (sucht, fragt nicht) und GV-UI-5 Zug 1 (erklärt, kein Block) weiter ohne — `ui` fällt dort durch.
      - **Begleittext schwach:** neben dem Auswahlfeld stand nur „Bitte wähle unten aus.“ — geduzt gegenüber einer Lehrkraft, ohne Einordnung der Treffer. Seit dem Gesamt-Review regelt die Kurzfassung den Begleittext (über `respond_to_user` in derselben Runde), ebenso die Werkzeugbeschreibung.
      - **`qr` war ein falscher Fehlschlag** (GV-UI-4 Zug 1): unter einer offenen Frage gibt es absichtlich keine Schnellantworten. Seit dem Gesamt-Review gilt `qr` dort als nicht gestellt (`evals/run_golden.py`).
      - **Themenbaum zum Unterthema** (GV-UI-1 Zug 2): `ui` besteht, aber der Agent rief `ui_themenbaum` wieder mit `subject` (Physik, Antwort aus dem Werkzeug-Cache, 17 Knoten) und bat, „Optik“ selbst aufzuklappen; den Optik-Zweig zeigte er nicht. Der Weg „Sammlung mit `search_wlo_collections` finden, dann `nodeId`“ griff nicht — weiter beobachten. (Der Muster-Weg hätte eine Unterthemen-Kennung bis zum Gesamt-Review sogar durch das Fachportal ersetzt, Befund 2.)
      - **Anrede:** GV-ELT-1 Zug 2 und 3 duzen (Erwartung Sie) — echter Fehlschlag. GV-UI-5 Zug 2 (`register`) ist ein Messfehler der Heuristik: „Sie zählt …“, „Sie nennt …“ meinen die Zahl, nicht die Person.
      - **Nächster Schritt:** die im Gesamt-Review geänderte Kurzfassung erneut in den Knoten übertragen (`scripts/check_master_skill.py`), dann UI-Abläufe und Seed-Suite (Agent) erneut — [`aenderungen/2026-11-03-review-u1-gesamt.md`](aenderungen/2026-11-03-review-u1-gesamt.md).
  - Beispiel-Abläufe der UI-Module (`evals/ui-module-flows.yaml`, U1-g, §17 G-7) auch im Studio fahren: dazu müssten sie in den Bereich `eval/gold-flows` (Seed), und die Maschinen-Matrix verlöre die Vergleichbarkeit mit früheren Läufen — oder ein eigener Flow-Satz im Studio. Heute nur Kommandozeile.

## 3 Messungen und Prüfungen (startet der Nutzer)

- **Paket U2 — Bestand oder Entwurf** (`evals/ui-module-flows.yaml`, GV-UI-8 … GV-UI-12): `run_golden.py --flows ../evals/ui-module-flows.yaml --engine agent --only GV-UI-8,GV-UI-9,GV-UI-10,GV-UI-11,GV-UI-12` — erst nach dem Übertragen des Master-Skills in den Knoten. Zeigt, ob die Erkennung trägt (Bestand vs. Entwurf, mehrdeutiger Fall mit Schnellantwort) und wie lange ein Entwurf mit dem echten Modell dauert (Dienst, Ebenen, `ausstehend`).
- **Paket U1-g — Beispiel-Abläufe der UI-Module** (`evals/README.md`, „UI-Module“): `run_golden.py --flows ../evals/ui-module-flows.yaml --engine agent` einmal mit und einmal mit `--ohne-ui-module`, dazu `--only GV-UI-7 --engine pattern`. Erst die Läufe zeigen, ob die Wendungen in `ui_antwort` die Beschriftungen des Modells treffen (`observed.ui_antwort.status`, seit dem Review `gesendet` / `keine_frage` / `keine_passende_option`; `gesendet` heißt nicht angenommen). Hinweis: seit U1-g melden alle Eval-Läufe die Module — Vergleiche mit Läufen davor mischen zwei Bedingungen (die Messbedingungen nennen `ui_module`, der Maschinen-Vergleich warnt).

- **Kette-Plan:** ein Golden-Lauf im Muster-Modus mit den Schnellantworten im Antwort-Aufruf.
  - Ob Inline getroffen hat, zeigt `per_phase` je Zug: Fehlt die Phase `quick_replies`, kamen sie aus dem Antwort-Aufruf.
  - Die neuen Zeit-Zeilen im Debug-Block (`zeit`/`llm`) zeigen je Zug, wo die Zeit liegt.

- **Nachmessung der Agent-Runde 2 (E2):** Golden-Läufe im Agent-Modus mit dem übertragenen Master-Skill.
  - Erfolg laut Runde-2-Plan:
    - Die harte Quote liegt in der Spanne der Muster-Maschine.
    - Kein Fehler kehrt in allen drei Läufen wieder.
    - Die Kosten je Zug liegen unter 0,00303 USD (E-5).
  - Danach über B1–B3 (Anrede) entscheiden.
- **Golden-Läufe nach Paket 7** (beide Maschinen): Geändert haben sich der Muster-Prompt und der Klassifikator (K2 Antwortsprache, K5 M10, P4 Gastgeber-Block, E-E Seitenkontext als Daten), die Agent-Kette (Paket B, Vorabruf vor dem Verlauf), die Denkparameter (L2: Denktiefe und Ausführlichkeit kommen bei gpt-6 erst jetzt an) und die Moderations-Schwelle (K8).
- **GWDG-Modelle und Werkzeuge — Todo außerhalb des Chatbots** (Paket 8, M1; Nutzer 2026-10-09): Vermutlich können nicht alle AcademicCloud-Modelle Werkzeuge aufrufen; das ist je Modell einzeln zu testen. Für die Vorgabe `qwen3-30b-a3b-instruct-2507` (das einzige Modell, das dort je mit 200 antwortete) ist es ungeprüft — jede Probe am 2026-10-09 endete mit 429 (Staging-B-API).
- **E-AC-Probe:** Nimmt die AcademicCloud zwei user-Nachrichten hintereinander an? Zweimal am Ratenlimit der Staging-B-API gescheitert (429, auch `/models`). Der Transport legt sie dort inzwischen zusammen; die Probe sagt nur noch, ob das nötig ist.
- **Golden-Lauf nach Paket 11 J–L** (beide Modi): Der Prompt nennt gesperrte Wissensbereiche nicht
  mehr (Muster), `search_wlo_within_collection` blättert mit `skipCount` und wird abgeglichen (Agent),
  mehrdeutige Fachwerte gehen an den LLM-Rückfall, und das Nachschlagen vor der Suche entfällt (C-1;
  im Muster-Modus gut die Hälfte der Suchzüge). Darauf achten: Filter-Fälle (Fach, Stufe, Typ,
  Zielgruppe, Lizenz), „mehr davon“ in einer Sammlung, Muster ohne Wissensbereiche.
- **Token-Streaming** (seit Paket 7 Vorgabe an): der Proxy-Weg auf Staging und die NVDA-Handprobe stehen aus.
- **T1 im Betrieb:** Die Debug-Zeilen `assess.rag_einbettung` und `respond.rag` zeigen, was die vorgezogene Einbettung spart (lokal gemessen 0,3–1 s je Wissenszug).
- **Einbettung mit Ticket (zweite Betriebsform):** Die Live-Probe steht aus, siehe [`2026-08-12-einbettung-ohne-repo-aenderung.md`](plans/2026-08-12-einbettung-ohne-repo-aenderung.md).
- **Befund Kontext-Ping (2026-10-08):**
  - Im Staging-Log nach der Zeile `offener Vorgang für wlo_add_to_collection verworfen — dieser Zug ist keine Antwort auf die Vorschau` sehen. Sie belegt die Ursache.
  - Nach dem Deploy denselben Ablauf wiederholen: erschließen, in die Sammlung aufnehmen, bestätigen.
  - Nebenbefund Gatekeeper-Skill „Optik“: untersucht in Paket 6 (Phase G) — lokal nicht nachgestellt, der Skill ist öffentlich und per `get_skill` abrufbar. Zum Bestätigen im Staging-Log: `MCP tool get_skill args:` (welche Kennung das Modell übergab) und am MCP-Server `upstream returned non-OK`. Drei Folgebefunde sind behoben (Fehltreffer nicht mehr im Cache, Nachfass-Hinweis auch für den Markdown-Katalog, Schlussnotiz nicht mehr an der letzten Beschreibung).
- **Studio:**
  - Einen Screenreader-Test gab es bisher nicht.
  - Den Start-Knopf des generativen Laufs hat niemand im Browser gesehen. Sein CSS gleicht dem gemessenen Gold-Knopf, und der Kontrast-Wächter deckt ihn ab.

- **Vorgänge und Abläufe (2026-11-06) — Frist eines Vorgangs mit laufendem Auftrag (Plan V-4):** Heute gilt
  auch dann `vorgang_tage` (Vorgabe 3), die b-api hält den Auftrag 30 Tage. Empfehlung: solange der Lauf auf
  einen Auftrag wartet, mindestens bis zum Abholen, höchstens 30 Tage (Aufbewahrung und `beruehren` müssen
  den Stand kennen). Entscheid steht aus; bis dahin geht ein nicht abgeholter Auftrag mit dem Vorgang
  verloren (bei der b-api bleibt er abrufbar).
- **K22 (geklärt 2026-11-07, B-API-Handbuch):** Nein. Ein fremder Schlüssel bekommt 404, einen Rückruf gibt es
  nicht. Es bleibt dabei: Nur ein Zug der Person fragt ab („Stand prüfen“ bzw. `ui_fortschritt`).
  - Ebenfalls geklärt: K16 (Start-Pfad `/api/v1/jobs/flows/{flow}`) und K21 (Abbruch per `DELETE`; der
    Chatbot bricht seit dem Job-Paket 2026-11-08 ersetzte und abgebrochene Aufträge auch bei der B-API ab).
  - Offen bleibt K18, `X-Edu-User-Id`. Am Staging gemessen ist die Kennung der Benutzername (`authority`).
    Ob die B-API sie gegen den Schlüssel prüft, ist offen; bis dahin nur Flows ohne Repository-Scopes.
  - Ohne Abbruch bei der B-API (Nachprüfung Job-Paket 2026-11-08; der Job läuft dort zu Ende und zählt bis
    dahin auf die Grenze von 20 je Schlüssel):
    - ~~Verdrängen in `vorgaenge.anlegen` nimmt einen wartenden Lauf per Kaskade mit.~~ Erledigt in K2a:
      ein Vorgang mit wartendem Auftrag weicht nie.
    - „Arbeitsstand löschen“ liest die Job-IDs vor der Kaskade; ein Auftrag, den ein zweiter Tab genau
      dazwischen festschreibt, fehlt darin.
    - Aufbewahrung und `purge_all` laufen ohne Schlüssel der Person; ein `DELETE` bekäme dort 404.
- **K1b `ui_fortschritt` (2026-11-06):** fertig und reviewt (Notiz
  [`aenderungen/2026-11-06-paket-k1b-fortschritt.md`](aenderungen/2026-11-06-paket-k1b-fortschritt.md)). Offen:
  403 `abgewiesen` zeigt das Modul wie „nicht angemeldet“ (der Client reicht nur den Status durch).
- **Übertragen in den persönlichen Bereich (U3-3a/b, 2026-11-06):** fertig und reviewt, wirkt aber erst,
  wenn (1) im MCP `WLO_BATCH_UPLOAD_ENABLED` an ist (die Werkzeuge sind seit dem MCP-Stand 07.11. verdrahtet,
  inklusive `wlo_list_my_batches`), (2) MA-0 (Messung mit dem
  Testkonto) gelaufen ist und (3) im Studio „Inhalte in WLO ablegen“ eingeschaltet wird (Vorgabe aus).
  Offen im Paket: „Vorgang herunterladen“, Neu-Vorbereiten nach
  abgelaufener Freigabe (Gefahr doppelter Ablage — seit M6 zeigt das Modul neben der Vorschau die letzten
  eigenen Ablagen). T1b erledigt in M6 (`aenderungen/2026-11-07-paket-m6-letzte-ablagen.md`). (`ui-upload.element.ts` ist seit Q4 geteilt.) Bewusst
  angehoben: Budget je nachgeladenem Modul 15 → 20 kB gzip (`ui-upload` 17,9 kB seit dem Review vom 07.11.).

## 4 Beim nächsten Deploy

- **Abläufe im Studio AS-1…AS-3 (2026-11-09):** keine Migration, keine neue Variable. Das Image neu
  bauen (Widget, Studio, Backend in einem `Dockerfile`): Die Bibliothek `ui` hat sich geändert
  (Sprachausgabe löst die Escapes eingesetzter Platzhalter auf). Danach im Browser einmal hart neu
  laden. Wartende Läufe behalten ihre Fassung, denn alle neuen Felder sind `null`. Getippter
  Freitext an Ablaufschritten liegt als Teil im Vorgang bis zu dessen Frist, unabhängig von
  `privacy-config.logging.messages` (siehe Notiz AS-3a). Notizen unter `aenderungen/2026-11-09-paket-as-1…as-3c`.
- **Abläufe im Studio AS-D (2026-11-09):** keine Migration, keine neue Variable; Image neu bauen
  (Studio, Backend). `POST /api/config/ablauf-pruefen` liefert dazu `teile` (Sicht „Daten“).
  **Offen:**
  - der Dienst `ablage_zuordnen` (Plan §5e): Der Teil `ablage` trägt keinen Ordnerpfad je Datei (der
    MCP legt flach ab), und der Ordnerbaum trägt keine Dateien, nur Zahlen je Ordner. Nötig ist ein
    Ordnerpfad oder Index je Datei im Upload und in `ablage`; wartet auf Teamfrage T1.
  - P1 (`plans/2026-11-09-p1-chatbot-umwandlung.md`): Entscheide für AS-T offen (T1 zuerst, dann
    Option A–E, Aufbewahrung der Texte, PPTX), Staging-Messung von `textContent` für private
    Uploads, Messung auf dem vServer.
  - **An das MCP-Team:** ein Endpunkt bzw. Werkzeug für die Bytes einer privaten Datei
    (`eduservlet/download` 403, `GET …/content` 405 mit Basic); `get_skill` lädt jede nodeId ohne
    Größengrenze als Text herunter.

  Notizen unter `aenderungen/2026-11-09-paket-as-da…as-dd`.
- **Restbefunde RB-1 (2026-11-09):** keine Migration, keine neue Variable; Studio- und Backend-Image
  neu (Katalog `ablauf_werkzeuge` an `Schritt.werkzeug`). Entscheid AS-4a Befund 10 = Option 2:
  eine `nodeid` aus den Startdaten der Gastseite darf als ganzes Argument an lesende WLO-Werkzeuge.
  Die Rechtsstufe sieht jetzt 8000 Zeichen. Notiz `aenderungen/2026-11-09-paket-rb1-restbefunde.md`.
- **Restbefunde RB-2/RB-3 (2026-11-09):** keine Migration, keine neue Variable; Image neu (Studio,
  Widget, Backend), im Browser hart neu laden. RB-2: Typnamen in der Sicht „Daten“. RB-3: Aufträge der
  Gastseite warten auf den wiederhergestellten Verlauf; `ChatRequest.from_host` und `ui.from_host`
  im Verlauf halten die Auftrags-Blase über das Neuladen. Querschnitts-Review RB: die Herkunft „Gastseite“ (Rechte aus Option 2)
  wird nur noch positiv festgestellt (`quelle`/`start_quelle`), Notiz `…-paket-rb-querschnitt.md`.
  Browser-Abnahme AS-4 und RB-3 bestanden (Notiz RB-3).
- **AS-5a (2026-11-10):** keine Migration, keine neue Variable; Studio- und Backend-Image neu.
  Je Ablauf mit Auslöser `agent` ein KI-Werkzeug `ablauf-<id>` (Startschema als Parameter), Knopf
  mit `start_quelle: "ki"` (ohne Rechte aus Option 2); `ablauf_vorschlagen` entfällt. **Sperrt:** ein
  gespeicherter Ablauf mit Auslöser `agent` und Startfeldern ohne Beschreibung lässt sich erst nach
  dem Nachtragen wieder speichern/testen (Befund `start_beschreibung`; im Werk keiner). Offen:
  AS-5c (`direkt`). Notiz `aenderungen/2026-11-10-paket-as-5a-…`.
- **AS-5b (2026-11-10):** Backend-Image neu. Muster nennen `ablauf-<id>` in `tools:` (Katalog
  `tools`); dieselben Werkzeuge und Knöpfe wie im Agent-Modus. Notiz `…-paket-as-5b-…`.
  Drei Reviews (AS-5b, Querschnitt AS-5, zweites Review) behoben. Der offene Punkt „Wahl mit ≥ 4
  Chips“ steht jetzt in §1.
- **AS-Ua (2026-11-10):** Backend-Image neu. `ui.ablauf` (Stand des Laufs) und `ui.fester_text` an
  den Antworten, Direktaktion `ablauf_abbrechen` mit Rückfrage. Die Leiste im Widget folgt mit AS-Ub.
  Notiz `aenderungen/2026-11-10-paket-as-ua-leiste-backend.md`.
- **AS-Ub (2026-11-10):** Widget-Bündel neu bauen, im Browser hart neu laden. Ablauf-Leiste über dem
  Eingabefeld; kein KI-Etikett an festen Texten (damit ist die frühere offene Frage aus RB-2/RB-3
  erledigt, U-7). Notiz `…-paket-as-ub-leiste-widget.md`.
- **BU-1/BU-2 (2026-11-10):** Widget-Bündel neu bauen. Neu ist das nachgeladene Bündel
  `ui-strukturentwurf.<hash>.js` unter `/widget/module/` (kommt mit `dist/widget-module/` ins
  Backend-Image wie die übrigen Module). Keine Migration, keine neue Variable. Nach dem Deploy einen
  Strukturentwurf im Widget öffnen und bearbeiten (lädt das Modul nach).
- **BU-3 (2026-11-10):** Widget-Bündel neu bauen; neu ist `ui-debug-panel.<hash>.js` unter
  `/widget/module/`. Smoke: im Widget den Debug-Schalter einschalten, das Panel muss erscheinen.
- **AS-Ud (2026-11-10):** Backend und Widget-Bündel neu bauen. Neue öffentliche Pfade
  `POST /api/ui/vorgaenge/liste` und `/loeschen` (nur angemeldet, IP-Drossel). Keine Migration, keine
  neue Variable. Smoke nach dem Deploy: angemeldet „Meine Vorgänge“ öffnen; einen Vorgang aus einem
  anderen Gespräch löschen. Läuft dort ein Auftrag, endet er bei der b-api (ohne den Schlüssel der
  Person sagt das Widget, dass er weiterläuft). Nach dem Querschnitts-Review (Plan §5k): auch der
  Verlaufsabruf trägt den Zugangsblock (Leiste nach dem Neuladen).
- **Abläufe als Dokumente, AS-0 (2026-11-09):** Migration **`0021`** im `migrate`-Dienst. Sie teilt
  `06-ablaeufe/katalog` in ein Dokument je Ablauf (`06-ablaeufe/<id>`), samt Werksbasis, stillgelegter
  eigener Fassung und Löschvermerk. Danach `boerdi import-config --werksabgleich`, Studio- und
  Backend-Bild neu. Laufende Abläufe laufen weiter (die Fassung hängt an den Schritten). Eine alte
  Sicherung mit `06-ablaeufe/katalog` wird beim Wiederherstellen in Dokumente geteilt, auch ein
  Verzeichnisbaum aus `export-config` beim `import-config`. **Nicht übernommen** werden Kennungen,
  die nur in der stillgelegten eigenen Fassung des Katalogs standen (die Migration nennt sie in
  ihrer Ausgabe; sie bleiben in `config_history` von `06-ablaeufe/katalog`), und die Basis einer
  eigenen Fassung (`eigene_basis`). Notiz
  [`aenderungen/2026-11-09-paket-as-0-ablaeufe-als-dokumente.md`](aenderungen/2026-11-09-paket-as-0-ablaeufe-als-dokumente.md).
- **Kestra-Abläufe K2b/K2a (2026-11-08):** keine Migration, keine neue Variable; Widget-Bündel neu bauen.
  Solange b-api-Aufträge freigeschaltet sind, die Aufbewahrung der Gesprächsverläufe auf **mindestens 8 Tage**
  stellen — sonst kann „Gespräch fortsetzen“ in einen leeren Verlauf führen (Notiz
  [`aenderungen/2026-11-08-paket-k2a-fortsetzen.md`](aenderungen/2026-11-08-paket-k2a-fortsetzen.md)).
- **Stabilität der MCP-Anbindung (2026-11-07):**
  - **Voraussetzung:** der MCP-Server auf dem Stand S1–S7 (ausgerollt am 07.11.). Ein älterer Server geht auch:
    Ohne `/auth/status` fragt der Chatbot das Werkzeug, ohne Replay bleibt der Ausgang offen wie bisher.
  - **Neue Variablen** (alle mit Vorgabe):
    - `MCP_CLIENT_KEY` (Geheimnis), `MCP_BUDGET_RPM`, `MCP_BUDGET_WAIT_S`;
    - `MCP_BREAKER_FAILURES`, `MCP_BREAKER_WINDOW_S`, `MCP_BREAKER_OPEN_S`;
    - `MCP_CONNECT_TIMEOUT_S`, `MCP_BUSY_RETRY_MAX_S`, `AUTH_GRACE_S`.
  - **Ohne Client-Schlüssel `MCP_BUDGET_RPM=280` setzen** (`uebergabe-betrieb.md` §11).
  - **Dem MCP-Team melden:**
    - `TICKET_ALLOWED_ORIGINS` = `CORS_ORIGINS`;
    - `WIDGET_OAUTH_ORIGINS` = die öffentliche Herkunft des Backends.
  - **Image neu bauen** (Widget: Abmelden widerruft, Ticket-Erneuerung nach 12 h). Danach Hard-Reload im Browser.
  - Keine Migration. Die neue Route `POST /api/auth/abmelden` steht in `docs/api/bewusste-vertragszusaetze.md`.

- **MCP-Vertrag (M1–M7, 2026-11-07):**
  - **Reihenfolge:** zuerst der MCP auf dem Stand vom 07.11.2026 — ein älterer kennt `find_content_by_url` und die
    Plan-Werkzeuge nicht und überginge `addToCollectionId` (dann entstünde ein Datensatz ohne Einsortieren).
  - **Master-Skill neu einspielen** (`docs/skills/vorgehen*.md` → WLO-Knoten): Dublette per Adresse, Anlegen mit
    Sammlung, Metadaten belegen, Sammlungsübersicht, Zählung, Pläne.
  - **Werksabgleich** (`import-config --werksabgleich`): Seeds `03-patterns/m08`, `m18`, `m19`, `m20`,
    `05-knowledge/mcp-servers.yaml`, `eval/gold-flows.yaml` (GV-RED-1 erwartet jetzt Vokabular statt
    `wlo_suggest_metadata` und in Zug 3 `wlo_create_content` — den Eval startet der Nutzer).
  - **Image neu bauen** (das Dockerfile baut Widget und nachgeladene Module selbst), danach Hard-Reload im Browser:
    `ui-upload` zeigt die letzten Ablagen (neuer Hash). Sichtbar erst mit `WLO_BATCH_UPLOAD_ENABLED` im MCP und dem
    Studio-Schalter „Inhalte in WLO ablegen“.
  - Keine Migration, keine neue Umgebungsvariable.

- **Vorgänge, Abläufe, Aufträge (2026-11-05/06):** Migrationen `0018` (`vorgaenge`, `vorgang_ablage`) und
  `0019` (`vorgang_auftraege`) laufen im `migrate`-Dienst. Abläufe liegen seit AS-0 (2026-11-09) je als
  Dokument `06-ablaeufe/<id>` (Werksfassung: Ablauf `sammlungsstruktur`, aus; Migration `0021` teilt den
  alten Bereich `06-ablaeufe/katalog` auf) und `privacy-config.logging.vorgang_tage` kommen mit dem Werksabgleich.
  Aufträge bleiben aus, bis `B_API_JOBS_START_PATH` und `B_API_JOBS_FLOWS` gesetzt sind (K16).
- **Migration `0013` (Review PR #18):** Teilindex `ix_quality_logs_text_offen` für den Text-Schritt der Aufbewahrung; wird `CONCURRENTLY` gebaut (sperrt das Schreiben nicht) und läuft im `migrate`-Dienst mit `alembic upgrade head`.
- **Paket 16 — Plattform-Wissen neu einlesen:** der RAG-Seed `Plattformwissen.jsonl` folgt jetzt dem Domänen-Dokument 2.0 (13 Abschnitte). Nur diesen Bereich ersetzen: die Datei allein in ein Verzeichnis legen und `boerdi import-rag --seed <verz> --force` (leert nur die Bereiche dieses Seeds; Einbettung von 13 Abschnitten). Ohne den Schritt bleibt in bestehenden Datenbanken die Fassung 1.0.
- **Paket 12 — Werk und eigene Fassung:** Migration `0011` (läuft im `migrate`-Dienst), der
  `migrate`-Befehl heißt jetzt `import-config --werksabgleich` (`compose.prod.yml`). Beim ersten
  Start nach dem Deploy hebt er Bereiche, deren letzte Fassung ein Import schrieb, auf die
  Werksfassung — die fünf Bereiche aus Paket 11 L kommen so ohne Handimport an, sofern sie im
  Studio unverändert sind. Angepasste zeigt das Studio unter Sicherung → „Werk und eigene Fassung“.

- **Paket 11:**
  - Keine neue Umgebung, keine Migration, kein Konfig-Import. Widget und Studio baut das Image selbst.
  - Studio: Akzentfarbe `#1b64d9`; unter Wissen → MCP-Server „Werkzeuge übernehmen“ nach „Server prüfen“ (nur lesende Werkzeuge weiterer Server werden angeboten, als `<kennung>__<werkzeug>`); Werkzeugliste mit Gruppe „Extern“.
  - Neues Kommando `boerdi rag-einbettung-wechseln [--probe | --fortsetzen]` (am `backend`-Dienst), Ablauf in `deploy/README.md` „Einbettungsmodell wechseln“.
  - Für das MCP-Team: [`mcp-und-anmeldung.md`](mcp-und-anmeldung.md).
  - **Reranker:** Vorgabe jetzt **aus**; eingeschaltet (`RAG_RERANKER_ENABLED=true`) bezieht das Backend das Modell selbst ins neue Volume `reranker_models` (Compose angepasst, `/models` jetzt beschreibbar). Die Schalter standen bis dahin nicht im Compose und erreichten den Container nie. Live meldet heute `model-missing` → nach dem Deploy `off`.
  - Mit `CORS_ALLOW_ALL=false` bietet das Widget die WLO-Anmeldung nur noch Seiten aus `CORS_ORIGINS` (und Erweiterungen) an; mit der Vorgabe `true` unverändert.
- **Paket 10:**
  - Neue Umgebung `CLASSIFY_TIMEOUT_S` (Vorgabe 20 s, gemessen p99 6,5 s), `DB_POOL_SIZE`/`DB_MAX_OVERFLOW` (5/10 wie bisher) — in `deploy/.env.example` und `compose.prod.yml`. `stop_grace_period` 65 s (siehe Paket 9).
  - **Echtheitsprüfung der Anmeldung:** jeder Zug mit persönlichem Block fragt einmal `wlo_auth_status` (Cache je Block 5 min). Ist der MCP-Server nicht erreichbar, gilt der Zug als anonym (enge Agent-Deckel, kein Schreibangebot). Ein abgewiesener Block fällt für den Zug weg; die Antwort trägt `auth_invalid`, das Widget bietet die Anmeldung neu an. Eine Abnahme hängt an der Person, nicht mehr am Block (ein neuer Ticket-Tausch verwirft sie nicht mehr).
  - Studio-Proxy: ändernde Anfragen von fremden Seiten (`Sec-Fetch-Site`/`Origin`) enden mit 403.
  - Bot-Markdown: keine Bilder, Medien oder Stile mehr; jeder Link mit `target` bekommt `noopener noreferrer`.
  - Zustimmung zu einer Vorschau: die Erlaubnisliste (kurze Sätze aus Zustimmungs- und harmlosen Beiwörtern, „Zum Aufnehmen bestätigen“ zählt) entscheidet sofort; andere Sätze ohne Vetowort prüft ein kurzer LLM-Aufruf (Phase `zustimmung`, Frist 3 s, kostet einen kleinen Aufruf je freiem „ja“). „ok, danke“ und „Ja, gleich“ fragen weiter nach. Der Knopf „Ja, so ausführen“ bleibt der Normalweg.
  - **`classify-overrides`** — seit Paket 12 zieht `migrate` (Werksabgleich) den Bereich selbst nach, sofern er im Studio unverändert ist; sonst wie folgt importieren (`import-config`): Kurations-Umleitung `curation_reroute` (Muster-Modus: Auftrag „in meine Sammlung aufnehmen“ → M18, mit Webadresse M20), neue I09-Trigger und Few-Shots. Ohne Import bleibt die Umleitung aus (`migrate` zieht nur fehlende Bereiche nach). Nur diesen Bereich nachziehen: `deploy/README.md`, Abschnitt „Einen einzelnen Bereich aus dem Abbild nachziehen“. Neue Logzeile `Kurations-Auftrag: … umgeleitet`.
  - Krisen-Wendungen: weitere Formen erkannt (andere Wortstellung, Absicht „Ich überlege, mit dem Leben Schluss zu machen“).
  - Umwandlung: Textdeckel 50 Mio. Zeichen je Datei.
  - Ein „Ja“ zu einer Vorschau unter einer anderen bzw. hier nicht geltenden Anmeldung (neuer Tab, abgelaufen, Ticket noch nicht getauscht) bekommt jetzt einen festen Hinweis mit Anmelde-Chip statt einer neuen Vorschau. Mit `ticket` warten frühe Züge bis zu 5 s auf den Tausch. Die Vorschau-Box nennt die Frist (10 Minuten). Neue Logzeile zur Diagnose: `Anmeldung nicht prüfbar (…)`.
  - **Widget-Bündel neu bauen** (Auftrag während des Kontext-Pings, Anmeldefenster im Klick, Fokus/IME, CRLF im Strom, Markdown, `auth_invalid`, Verlaufsnachfrage ohne `after_id`). Das Studio ist unverändert.
- **Paket 9:**
  - Migration `0010` (Indizes auf `messages.created_at` und `memory.created_at` für den Löschlauf) — `alembic upgrade head`, der Dienst `migrate` erledigt das beim Start.
  - `b-api-openai` mit `gpt-6-luna` läuft jetzt über `/openai/responses` — vorher scheiterte dort jeder Werkzeugaufruf (Review CRITICAL 1). Live geprüft am 2026-10-09 (Werkzeugaufruf mit und ohne Strom).
  - Neue Umgebung `RAG_CONVERSION_TIMEOUT_S` (120) und `RAG_CONVERSION_MAX_MB` (1024; bis 2026-10 `RAG_UMWANDLUNG_FRIST_S`/`_MAX_MB`): Uploads und URL-Importe werden in einem eigenen Kindprozess umgewandelt (ZIP-Bombe, PDF-Seiten, Speicher, Frist). Stehen in `deploy/.env.example` und `compose.prod.yml`.
  - `session_id` im Chat nur noch `[A-Za-z0-9_-]{1,128}`, sonst 422 (das Widget schickt `bb-<uuid>`). `page_context` ist am Eingang gedeckelt (Feldlänge, Einträge, Tiefe). Eigene Einbettungen mit anderen Kennungen vorher prüfen.
  - Moderation mit eigenen Plätzen (4); die Frist (8 s) gilt seit Paket 10 für Warten und Aufruf zusammen. Scheitert sie, geht die Nachricht ungeprüft weiter und das Log sagt „moderation skipped“.
  - Aufbewahrung: auch der Gesprächsstand ruhender Sitzungen (Entities, Signale, Tour) wird nach der Frist der Verläufe geleert; die Sitzung und ihre Kosten bleiben (V7, umkehrbar). Fristen-Vorgaben des Modells jetzt 90/180 wie die Seeds.
  - Beim Herunterfahren wartet das Backend bis 25 s auf nachlaufende Züge — erst nach den 30 s von uvicorn; `stop_grace_period` in `compose.prod.yml` deshalb seit Paket 10 65 s (vorher 40 s, zu knapp).
  - Kosten: Probeläufe von „Auftrag testen“ im Studio buchen als `studio-probe` und zählen nicht als Produktion.
  - **Widget-Bündel neu bauen** (Verlaufsnachfrage mit echter Frist und Abbruch, „beschäftigt“/„veraltet“, Druckfenster); CORS gibt dafür `Retry-After` frei. Studio neu bauen (Aufbewahrung, Sicherungs-Panels, Kosten, Texte).
- **Paket 8:**
  - Vorgabe-Modell `gpt-6-luna` für `openai` und `b-api-openai` (vorher `gpt-5.6-luna`). Es wirkt nur, wo `LLM_CHAT_MODEL` leer ist; die Schnellstart-Anleitung setzt es ausdrücklich (`LLM_CHAT_MODEL=gpt-6-luna`). Auf der AcademicCloud: Chat `qwen3-30b-a3b-instruct-2507`, Einbettung `text-embedding-3-small` über den OpenAI-Pfad der b-api.
  - Parallelität `b-api-openai` 20 (vorher 2); eine gesetzte `LLM_MAX_CONCURRENCY` gewinnt.
  - **Aufbewahrung greift:** Der erste Lauf, 5 Minuten nach dem Start, löscht endgültig **Chatnachrichten und Sitzungsgedächtnis älter als 30 Tage** (Vorgabe, auch ohne Eintrag in der gespeicherten Konfiguration), Sicherheits-Einträge älter als ihre Frist (90 Tage) und Qualitäts-Einträge (180 Tage) — seit Paket 9 sind das auch die Vorgaben des Modells, nicht nur der Seeds. Wer ältere behalten will, setzt die Frist vorher auf 0 (Studio: „Datenschutz“ bzw. „Identität & Schutz“). Was fällig ist, zeigt das Panel „Aufbewahrung“. Die Sitzungen und ihre Verbrauchszahlen bleiben. Beide Protokolle halten die ersten 500 Zeichen je Nachricht länger als die Nachrichten selbst — das Qualitätsprotokoll 180 Tage, das Sicherheitsprotokoll 90 Tage und dazu die IP (riskante, gedrosselte oder mit `log_all_turns` alle Züge). Angleichen, falls das nicht gewollt ist.
  - Krisen-Wendungen im Regex-Gate (23 Muster, eingebaut): Treffer gehen auf das Krisen-Muster bzw. die Krisen-Antwort des Agent-Endpunkts.
  - HSTS (ein Tag) und die CSP der Studio-Seite (durchgesetzt) — `HSTS_MAX_AGE`, `STUDIO_CSP` in der `.env`, leer = Vorgabe. Abnahme in `deploy/README.md`. Steht das Studio danach leer oder ohne Stil da: `STUDIO_CSP=report` und den Konsolen-Verstoß melden.
  - Seeds: `01-base/safety-config.yaml` nur ein Kommentar; `01-base/privacy-config.yaml` trägt `retention_days: 30` — dieselbe Zahl gilt als Vorgabe des Modells auch ohne Import.
- **Paket 7:**
  - Migrationen `0007` (die toten Auslöser-Bereiche löschen), `0008` (Tabelle `session_locks`) und `0009` (`usage_events.session_id` nullbar, Spalte `quelle`) — `alembic upgrade head`, der Dienst `migrate` erledigt das beim Start.
  - Geänderte Seeds (wirken nur in nicht gespeicherten Bereichen): `01-base/engine.yaml` (Agent, Block `betrieb`), `01-base/safety-config.yaml` (`self_harm` 0,25), `01-base/pricing.yaml` (seit 2026-10-18 USD mit Listenpreisen), `01-base/guide-mode.yaml`, `05-knowledge/mcp-servers.yaml`, `03-patterns/m10-ki-inhalt-generierung.md`, `eval/gold-flows.yaml` (GV-RED-1 auf Abruf). Neu: `01-base/rag-retrieval.yaml` (leer = Vorgaben des Codes; legt der Dienst `migrate` an).
  - Das Image wird um rund 80 MB größer (`markitdown`-Extras für PDF und Office).
  - Umgebung: siehe `deploy/.env.example` (Parallelität je Anbieter, durchgereichte Schalter; leer gilt als ungesetzt). Eine gesetzte Variable schlägt die Studio-Schalter (Fast-Modus, Token-Streaming, Agent-Schnellantworten).
  - Studio, Agent & Maschine → Betrieb: Agent-Schnellantworten erst nach dem Übertragen des Master-Skill-Abschnitts „Schnellantworten“ einschalten. Das Gastkonto-Schreiben bleibt aus, bis es jemand bewusst einschaltet.
  - Seit dem Review trägt der `connected`-Rahmen des Chat-Stroms `history` und `after_id`, und ohne gespeicherten Verlauf bricht ein aufgelegter Zug wieder ab. Ein Widget aus dem Browser-Cache, das die Angaben nicht kennt, holt die Antwort weiter aus dem Verlauf; nach einem Hard-Reload gilt der neue Weg.
- **Migrationen `0004` bis `0006`** — `alembic upgrade head` ausführen; der Dienst `migrate` in `compose.prod.yml` erledigt das beim Start:
  - `0004`: `usage_events.engine`, nullbar, reine Katalogänderung.
  - `0005`: drei Indizes auf Sitzungs-Log, Qualitäts-Log und Konfig-Historie.
  - `0006` (Paket 4, E2): höchstens ein laufender Eval-Lauf. Überzählige `running`-Reste gehen dabei bis auf den jüngsten auf `failed`.
- **Vorgabe `BACKEND_REPLICAS` ist jetzt 1** (Paket 4, L4). Wer bisher ohne Eintrag lief, hatte drei Replikas und hat nach dem Deploy eine. Seit Paket 7 (P1) hält die Sitzungssperre über alle Kopien; mehr als eine Replik ist damit möglich — Entscheid beim Deploy (`docs/cluster-checkliste.md`).
- **Geänderte Seeds** wirken nur in Bereichen, die nicht gespeichert sind:
  - Betroffen sind `01-base/engine.yaml`, `02-domain/domain-rules.md`, `03-patterns/m01-krisen-empathie.md`, `03-patterns/m02-bedrohungs-refusal.md`, `04-personas/elt.md`, `04-personas/ler.md`, `05-knowledge/rag-config.yaml` und `eval/gold-flows.yaml`.
  - Gespeicherte Bereiche im Studio abgleichen. Sicher betroffen ist die Rolle auf „Agent & Maschine“, wo sie schon gespeichert wurde.
- **Golden-Seeds** nach dem Deploy auf Staging importieren.
- **Master-Skill:** nach jedem Übertragen `cd backend && uv run python scripts/check_master_skill.py` ausführen.
  - Die Rückgabe 0 heißt: alle Regeln erfüllt. 1 heißt: mindestens eine verletzt. 2 heißt: nicht abrufbar.
- **Paket 18 (18C/D bis 18F, main `924662a`):** Image neu bauen (Backend und Widget); Migration `0016` (Trace-ID je Zug, Paket 18C/D Phase 1), falls noch nicht gelaufen; das Plugin-Bündel neu holen (Widget liest nur noch `ui`); `STUDIO_API_KEY` für Golden- und Eval-Läufe setzen (der Diagnoseteil kommt nur noch mit Freigabe). **Vor dem Update `RATE_LIMIT_CHAT` prüfen:** ein ungültiger Wert verhindert jetzt den Start, leer = 120/minute. Optional die Zähler `boerdi_llm_schluessel_abgelehnt_total`, `boerdi_llm_platz_frist_total` und die Alarmregeln `BoerdiLlmSchluesselAbgelehnt`, `BoerdiLlmAusgelastet` aus `deploy/helm/values.example.yaml` übernehmen; `LLM_SLOT_WAIT_S` (Vorgabe 30).

## 5 Aufräumen

- **Zeitraum-Grenzen in Browser-Zeit** (Review Paket 16, D-5): Kosten und Nutzung bauen `from`/`to` aus dem Kalendertag des Browsers, Tage und Raster rechnet der Server in Europe/Berlin. Außerhalb deutscher Zeit kommt am Rand ein angeschnittener Tag dazu. Hebel: Grenzen als Berliner Mitternacht bauen (`Intl`-Versatz).
- ~~**Zeitabhängiger Test**~~ erledigt in Paket 20 (B3): wartet jetzt auf den zweiten Lauf. War: `tests/test_aufbewahrung_takt.py::test_der_takt_laeuft_weiter_auch_nach_einem_fehler` (50-ms-Fenster, 5-ms-Takt) kippte im vollen Lauf unter Parallellast (Paket 16, 2026-10-18), allein grün. Fester machen: auf eine Bedingung warten (zweiter Lauf) statt fest 50 ms schlafen.
- ~~**Uhrenabhängiger Test**~~ **erledigt 10.11.** (Toleranz), ebenso die zwei Kippler darunter (Zeitfenster vor
  `_JAN`, Merker vor dem Test löschen). War (gesehen 2026-11-10 im vollen Lauf zu AS-8a):
  `tests/test_anmeldung_status.py::test_eine_bestaetigung_gilt_hoechstens_bis_zur_frist` kippte mit
  `60.00000023841858 <= 60`, allein grün. `datetime.now` (Test) und die Uhr in `_gueltig_s` laufen
  unter Windows um Bruchteile auseinander. Fester machen: eine Toleranz (`<= 60 + 1e-3`) oder eine
  feste Uhr im Test.
- **Vorschau-Sitzungen zählen als Betrieb** (Querschnitts-Review AS-8, vorbestehend): Sitzungen der
  Studio-Vorschau — auch Probe-Sitzungen mit `entities._probe` — tragen eine gewöhnliche
  Widget-Kennung und zählen in `services/session_origin` als `production` (Kosten, Nutzung,
  Qualität). Hebel: Probe-Sitzungen über `_probe` als eigene Herkunft (`studio`) zählen.
- **Zwei weitere Kippler im vollen Lauf** (gesehen 2026-11-10, zweiter Lauf zu AS-8a, je allein
  grün):
  - `tests/test_usage_analytics.py::test_die_sitzungsliste_haelt_sich_an_den_zeitraum` sah fremde
    Sitzungen `k4-…` aus einem anderen Test in derselben Test-DB. Fester machen: eigene Kennungen
    filtern oder vorher aufräumen.
  - `tests/test_url_safety.py::test_tropfende_kopfzeilen_werden_zur_frist_abgeschnitten` hängt an
    einer Zeitfrist unter Last.
  - Widget: `projects/ui/src/session/anmelde-frist.spec.ts` („steht nach dem Abmelden …“) sah im
    vollen `ng test ui` einmal einen Abmelde-Merker aus einer anderen Spec; allein und im nächsten
    vollen Lauf grün. Fester machen: den Merker im `beforeEach` löschen.
- **Dateien über der 300-Zeilen-Regel** (Audit F-8), aus diesen Runden:
  - Paket 6 hat geteilt: `services/rag/ingest.py` (→ `umwandeln.py`), Studio `schema-form/schema-form.scss` (Teildateien je Baustein, CSS byte-gleich), `views/curated-views.ts` und `i18n/catalogue/curated.ts` (nach Seitengruppen), `i18n/catalogue/area-editor.ts` (`groupSection.*` eigener Teil), `views/eval-run-detail.component.ts` (Gold-Zug-Tabelle als `eval-gold-turns`) und `schema-form/schema-field.component.ts` (Listen- und Map-Regeln in `list-items.ts`, `map-entries.ts`; die Vorlage steht mit 300 an der Grenze). Dabei vor dem Überschreiten bewahrt: `api/config_guards.py` (Fehler-Antworten nach `api/config_antworten.py`), `api/rag.py` (`api/rag_umwandlung.py`), `api/config.py` (Löschen nach `api/config_documents.py`), `views/group-section.component.ts` (`group-documents.ts`, `feld-reiter.ts`).
  - Paket 7: `graph/nodes/respond_agent.py` (537; Paket B und E-C, überwiegend Begründungs-Kommentar; Review B-3 +3), `services/response_prompt_builder.py` (324; P4 +6, E-E +6, Review B-5 +2), `services/classify_prompt.py` (315; vorher 330), `services/tool_loop_messages.py` (373, Fidelity-Port; D, E-E, T1, Review B-5 +4), `services/page_context.py` (815; vorher 972 — der tote Regel-Zweig ist weg), Widget `shell/lifecycle.ts` (326; vorher 302, T2 und Review C-5 — die Kontext-Ping-Abläufe wären ein eigener Baustein, ein Backend-Test liest aber `PING_COVERS_BACKEND_KINDS` aus genau dieser Datei).
  - Bisher nicht geführt, im Lauf der Pakete darüber gewachsen: `services/db_sessions.py` (339; beim ersten Einchecken 258), Widget `stream/chat-api.ts` (456; beim ersten Einchecken 286 — im Review C-3 wurde der Verlaufs-Abruf nach `stream/history-transport.ts` gelöst, statt weiter anzubauen), Widget `i18n/de.ts` (308; ein flacher Katalog, Paket 7 +5), `settings.py` (550; schon vorher 528, Paket 8 +22 für HSTS und Studio-CSP — eine flache Liste der Umgebungsvariablen), ui `print/print-utils.ts` (397; schon vorher 395 — Paket 8 hat das Verdrahten der Druckfenster nach `print-fenster.ts` gelegt statt anzubauen).
  - Erledigt im Review: `services/llm.py` (305 → 297, B-7: die Nachrichtenform je Anbieter liegt in `services/llm_nachrichten.py`).
  - Backend: `graph/nodes/respond_agent.py` (508 vor Paket 7; 2026-10-01 +22 für den Agent-Schnellantwort-Weg, +10 für Paket 2, 2026-10-03 +9 für das Token-Streaming), `services/agent_loop.py` (635; +16 Token-Streaming, Paket 4 B1 +116 für Frist und Quittungen, Review +12), `services/config_store.py` (321; Paket 4 D1/D4/D5, Paket 4b A4 +2, Paket 4c A2 +5 — Cache-Frische, `put_many`, Konfliktschutz; Review Paket 6 +5 für das bedingte Löschen; der bedingte Schreib- und Löschweg und die Fehlerabbildung liegen in `services/config_conflict.py`), `services/write_approval.py` (372; vorher 304, Paket 2 +12 für `merke_abnahme`, Paket 4 A1 +36 für das Aufrufer-Kennzeichen, Befund 2026-10-08 +20 für Hintergrund-Züge — überwiegend Docstrings), `graph/nodes/context_greeting.py` (493; schon vorher 476 und hier nicht geführt, Befund 2026-10-08 +16 — stumme Fehlerwege des Pings; Paket 7 T2 +1, die Entdopplung liegt in `domain/gruss_vermerk.py`), `services/llm_streaming.py` (302; vorher 266, Token-Streaming T1/T2), `domain/pattern_engine.py` (385; schon vorher 374 und hier nicht geführt, Paket 4c Review +11 — Fidelity-Port, Laden und Wählen der Muster in einer Datei). Bisher hier nicht geführt, schon vorher darüber: `services/guide_qr_injector.py` (695; Paket 6 B1 +5), `services/mcp/parsers/skill_registry.py` (462; Paket 6 G2 +13), `domain/tool_result_redaction.py` (483; Paket 6 G3 +6), `api/config_elements.py` (318; Paket 6 B5 +3), `services/mcp/client.py` (473; Paket 6 G1 +1).
  - Ältere Fidelity-Port-Dateien, die das Token-Streaming um wenige Zeilen verlängert hat: `graph/nodes/respond.py` (528), `services/tool_loop.py` (973), `domain/write_confirm.py` (448; Paket 2 +13, Befund 2026-10-08 +1), Widget `shell/chat-shell.component.ts` (862), `chat-shell.component.html` (323). Die neue Logik liegt in eigenen Modulen (`domain/stream_gate`, `domain/stream_preview`, `domain/tool_pflicht`, `services/token_stream`, `graph/nodes/respond_strom`).
  - CI: `.github/workflows/image.yml` (386; Paket 4 L3 samt Review, überwiegend Begründungs-Kommentar).
- Der Abnahme-Zug steht im Debug- und Qualitätsprotokoll auch im Agent-Modus als `M18` (Runde-2-Plan, N-5; kosmetisch). In Paket 6 geprüft: Die Kennzeichnung hängt an einer Stelle (`write_approval._PATTERN_ID`), die Maschine steht im Vorlauf aber nicht fest — `preflight` bekommt `engine` nicht, und der Debug-Block des Abnahme-Zugs hat kein `engine`. Eine Korrektur bräuchte drei Stellen.
- **Reiter-Namen der Muster fest deutsch** (`views/pattern-field-tabs.ts`, `views/feld-reiter.ts`): „Identität“, „Tools & Wissen“ … und der Satz „Reiter „…““ stehen auch in der englischen Oberfläche. Älter als Paket 6 (A7), dort nur verschoben.
- ~~**Blockierendes `getaddrinfo` in der Restore-Prüfung**~~ erledigt in Paket 20 (B1): alle Adressprüfungen laufen per `asyncio.to_thread`. War: (`api/config_guards.py`): Für jeden weiteren MCP-Server eines hochgeladenen ZIPs löst die Prüfung den Namen im Ereignis-Loop auf. Selten, aber ein langsamer DNS hält dabei den ganzen Prozess an.
- **E2E-Kippler `frontend/e2e/auth-button.spec.ts:95`** (Tab-Reihenfolge, 2026-10-31 einmal rot, während die Backend-Suite parallel lief; isoliert 3× grün). Nicht in Paket 20: erst nachstellen (Vorgehen in der Erinnerung „E2E-Kippler“: alte Reihenfolge rot, neue grün), dann ändern.
- **`runCardAction` bei gewechselter Sitzung** (`frontend/projects/ui/src/controllers/collection-actions.ts`,
  gesehen im Review K1b): kehrt bei `veraltet()` zurück, ohne `setLoading(false)` — der Laden-Zustand bleibt
  stehen, bis der nächste Zug ihn setzt. Älter als K1b (Frontend-Split); prüfen, ob der Sitzungswechsel ihn
  ohnehin zurücksetzt.
- **Frontend-Tests kippen unter Last.**
  - 2026-10-31 (Paket 20): `studio/views/agent-tools.component.spec.ts` „verweist bei Policy-Sperren auf die Seite des offenen Arbeitsbereichs“ einmal rot im vollen Lauf, einzeln 3× und im zweiten vollen Lauf grün. Verdacht: die gewählte Ansicht (`StudioAnsicht`) eines früheren Tests wirkt nach (`isolate: false`).
  - Im vollen Lauf am 2026-09-29 fielen 5 Studio-Dateien um (`i18n/en.spec.ts`, `agent-skills`, `eval-trends`, `loadtest`, `rag-ingest`) und `ui/print/print-utils.spec.ts`; einzeln und im Wiederholungslauf grün.
  - Audit 2026-09-29: `print-utils.spec.ts` läuft jetzt mit fester Uhr, `studio/core/download.spec.ts` stellt die veränderten Globals zurück (`isolate: false`). Die übrigen Kipper ließen sich nicht reproduzieren; bei erneutem Auftreten Datei und Fehlermeldung festhalten.
- Der Klassifikator läuft über `instructor` statt über `llm.chat_completion` und liest im Fehlerpfad nur `choices[0]` (`services/classify.py:123`).
  - Auf dem Responses-Weg liefe ein Text mit Aufruf dort ins Leere. Der Aufruf ist aber erzwungen, und ein Ausfall ist nicht beobachtet. Das ist ein Restrisiko, kein Befund.

- **Rest aus dem ReDoS-Befund (Paket 4, Review):** Der Motor mit Zeitgrenze (`domain/regel_regex`, Paket 6 B1) könnte auch `pattern` in Ergebnis-Schemata prüfen; heute sind Muster dort nur ein Hinweis an das Modell (A3, Review R-2). Eine Idee, kein Befund.
- **Aus dem zweiten Review von Paket 4b (2026-10-08):** Die drei Code-Befunde sind in Paket 4c erledigt (URL-Import, Wert ohne JSON, Ansage „kein Werkzeug“); die Skill-Suche der Testinstanz ist in Paket 7 entschieden (S5).
- **Studio-Startpaket 1,10 MB** (Build 2026-10-09 nach Paket 7, noch ohne Warnung; nach Paket 6 1,09 MB, 2026-10-03 nach Paket 4 L1 1,08 MB). **Seit dem Review von Paket 7 meldet der Build die Warnung: 162 Byte über 1,1 MB** (die berichtigten Studio-Texte C-7…C-11), **seit Paket 8 6,1 kB darüber** (Texte des Aufbewahrungs-Panels, de/en). **Seit Paket 13 (Phase F, 2026-10-17) 38,7 kB darüber** (1,14 MB: Ansicht-Umschalter, Auswertung v2 mit Matrizen, Ablauf-Karten, Vergleich und Verlauf, Texte de/en). **Seit Paket 14 (Arbeitsbereiche, 2026-10-17, mit Review-Fixes) 54,7 kB darüber** (1,15 MB: Agent-Seiten, Anrede-Tabelle, Materialformate mit Markdown-Vorschau, Texte de/en). Bis zur Fehlergrenze 1,2 MB bleiben rund 45 kB. **Paket 15 (Phase 0, 2026-10-17): 826 kB** — das Studio zog über die Sammeldatei `@boerdi/ui` das ganze Widget ins Startpaket; direkte Importe aus `@boerdi/ui/i18n/*` halbieren es fast. Der Hebel unten ist damit vorerst nicht nötig. Nächster Hebel, falls nötig: die Evaluation, die Agent-Seiten und Materialformate per `loadComponent` nachladen statt im Startpaket. Der Fehler kommt bei 1,2 MB; die CI wertet die Warnung nicht als Fehler. Angular 22.2 weist den gemeinsamen Chunk (`@angular/core` u. a.) richtig als initial aus; 22.1 nannte ihn „lazy“, geladen wurde er schon immer beim Start.
  - Größter Posten: beide Sprach-Kataloge des Studios, 434 kB, eager (`i18n/de.ts`, `i18n/en.ts`).
  - Das Budget ist an den echten Stand angepasst (Warnung 1,1 MB, Fehler 1,2 MB). Der Schnitt „`en` erst beim Umschalten laden“ hieße, jeden Katalogteil auf zwei Dateien zu verteilen — gegen die bewusste Regel „beide Sprachen beieinander“ (`catalogue-part.ts`). Entscheid 2026-10-09: so lassen, solange das Budget hält. **Nutzer, Nachfrage zu Paket 8:** das Studio wird selten aufgerufen — etwas über der Warnschwelle ist kein Problem.

- **Einstellungen ohne Leser** (gefunden 2026-10-01 beim Bau der Konfigurations-Grafiken, Stand `1f069e9`). Das Studio bietet sie an, der Code liest sie nicht:
  - (`retention_days` liest seit Paket 8 der Aufbewahrungs-Lauf; `agent.safety`, `confidence_adjustments`, `default_enabled` des Lotsen und `inline_result_grouping` im Muster-Prompt sind in Paket 7 gestrichen bzw. repariert.)
  - `01-base/display-rules`: `quick_replies.inline_fallback_enabled` (der Lader gibt es weiter, niemand wertet es aus).
  - Umgebung: `RERANK_URL` und `TEXT_EXTRACTION_URL` stehen nur in `settings.py`.
  - Der ALT-Zweig `cards_enabled` im Muster-Prompt bleibt ruhend: kein Client sendet das Feld. Daran hängt auch der UI-Box-Status, den Paket 7 (D) an die Werkzeug-Nachricht gelegt hat.

- **Paket 14, aus dem Review (2026-10-17), nicht dringend:** `views/group-section.component.ts` hat 312 Zeilen (Grenze ~300) — Anlegen/Kopieren/Löschen ließe sich als eigener Helfer herausziehen. (Dass Aliase und Vorrang im Panel „Materialtypen“ nach dem Speichern ihrer Abschnitte veraltet blieben, ist seit dem zweiten Review von PR #18 behoben.)

- **Aus dem zweiten Review von PR #18 (2026-10-18), älter als die Pakete 13–16, nicht angefasst:**
  - ~~erledigt in Paket 20 (A1): nur Sitzung/Muster/Intent befreien von `confirm`, die Frage nennt den Umfang.~~ War: `api/quality.py` `clear_quality_logs`: `scope=production` zählt als Filter und umgeht damit `confirm` — es löscht fast die ganze Tabelle; `engine=pattern` tut seit Paket 16 dasselbe (gewollt, dokumentiert). Im Studio nennt die Rückfrage (`quality-logs` `bulkQuestion`) einen anderen Umfang als `all` nicht.
  - Teilweise erledigt in Paket 20 (A3): die MCP-Server-Liste legt ohne Version nur noch an (`create`); die Bereichs-Schreiber taten das schon. Offen bleibt nur ein Server, der gar keine Version meldet (`version` fehlt → bedingungslos, so in D5 gewollt). War: „Trotzdem speichern“ nach einer 409 ohne Version (`version: null`) schreibt ohne Bedingung, in jedem Schreiber (`AreaDocEditor`, Server-Liste, Anrede, Materialtypen). So in Paket 4 D5 festgelegt; fehlt `X-Config-Version`, wird daraus ein blindes Überschreiben.
  - `views/backup.component.html`: die Karten in den Reitern tragen `h2` wie der Seitentitel (`check:a11y` lässt es durch).
  - `mcp-registry-store.ts` `save()`: scheitert das Neuladen nach dem Speichern, steht „Gespeichert.“ neben dem Ladefehler.
  - Widget `chat-shell.component.ts` `focusInput`: der `setTimeout` wird beim Zerstören nicht abgeräumt.
  - ~~erledigt in Paket 20 (A2): gespeichert ohne Query und Anker.~~ War: `data.page` und `debug.context.page` halten den Pfad der Host-Seite 180 Tage. Schickt eine Einbettung je Query-Strings mit, blieben auch Suchbegriffe; Hebel: die Query in `log_quality_event` abschneiden.

- **Veraltete Kommentare im Seed** (Doku-Abgleich 2026-10-18, nicht angefasst, weil eine Seed-Änderung als neue Werksfassung zählen kann): `backend/seeds/05-knowledge/rag-config.yaml` Z. 11 nennt nur M04 und M15 als RAG-Muster (dazu kam M10); `backend/seeds/05-knowledge/mcp-servers.yaml` Z. 9 nennt „System → MCP-Server“ (heute Gemeinsam → „Werkzeuge“). Im Code-Kommentar von `views/curated-pages-betrieb.ts` heißt die Agent-Seite noch „Rolle & Grenzen“ (Katalog: „Rolle & Schutz“). Beim nächsten Seed-Paket mitnehmen.
- **Architektur-Grafiken:** 3 unbekannte Viewer-Schlüssel und 66 englische Viewer-Texte im gemeinsamen `translations`-Block aller sechs Grafiken (archify-Warnung, kein Fehler) — gemeinsam angleichen, wenn die Grafiken das nächste Mal neu erzeugt werden.

- ~~**Master-Skill: Erstabruf nicht gebündelt**~~ erledigt in Paket 20 (B2): gleichzeitige Erstzüge teilen einen Abruf. War: (Review 2026-10-18, Befund 5): Direkt nach einem Neustart, solange der erste Takt-Abruf noch läuft (bis 23 s), holt jeder Zug ohne Stand den Text selbst — N gleichzeitige Erstzüge, N MCP-Sitzungen. Das gab es schon beim alten Ablauf-Verfahren. Hebel: den laufenden Abruf je Kennung merken und abwarten (Single-Flight).

- **Fokus nach dem Speichern** (studioweit, WCAG 2.4.3; gesehen im Review U1-f): In „Werkzeuge“ (`agent-tools.component.html`), „Materialformate“ (`material-typen.component.html`) und „UI-Module“ (`ui-module.component.html`) sind „Speichern“ und „Verwerfen“ während des Speicherns und danach `disabled` (gebunden an „speichert“ bzw. „nichts geändert“); der Fokus fällt dabei auf `body`, Tastatur- und Screenreader-Nutzer stehen danach am Seitenanfang. Hebel: den Fokus nach dem Speichern bewusst setzen (Statuszeile mit `tabindex="-1"` oder Abschnittstitel) oder die Knöpfe mit `aria-disabled` statt `disabled` führen. Einmal für alle Panels lösen.
- **Paket U1, Review U1-f — gleiche Lücke wie #3 an anderen Schreibern:** Abschnitte mit `felder` (nur ein Ausschnitt sichtbar: `01-base/engine` auf „Betrieb“ und im Agent-Bereich, `01-base/device-config` auf „Anzeige“) und die Anrede-Tabelle (`views/anrede.component.ts`) senden beim „Trotzdem speichern“ die verborgenen Teile im geladenen Stand und drehen eine Änderung der anderen Seite zurück. Für `ohneFelder` ist das seit Review U1-f behoben (`AreaDocEditor.save` mit `vomServer`); für `felder` wäre es die Umkehrung (Serverstand plus sichtbare Pfade aus dem Entwurf). Plan §16 „Offen (U1-f)“.
- **Paket U1, kleinere Reste** (Plan §15/§16 „Offen“):
  - Kein Studio-E2E mit gemocktem Backend; die Sichtprüfung der Seite „UI-Module“ war einmalig.
  - `npm run module:neu` legt den Manifest-Import in `views/ui-modul-vorschau.component.spec.ts` nicht an (der Test verlangt ihn für jedes Modul).
  - Vorschau-Bühne `lang="de"`: im englischen Studio stehen die englischen Bedienwörter der Module darin (bewusst, Review U1-f #5).
  - Der Studio-Probelauf meldet keine Module (U1-d1) — die Schalter wirken dort nicht sichtbar. (Die Evaluation meldet sie seit U1-g.)
  - `structuredContent` für Werkzeuge ohne JSON-Text verwirft der MCP-Client weiter (U1-e, E-2); ein Seitenkanal wäre ein eigener Schritt.
  - `views/group-section.component.ts` steht jetzt bei 318 Zeilen (Review U1-f +1).
- **Paket U1, Gesamt-Review Frontend (2026-11-03), bewusst nicht geändert**
  ([`aenderungen/2026-11-03-review-u1-gesamt.md`](aenderungen/2026-11-03-review-u1-gesamt.md), „Frontend“):
  - `shell/send-message.ts`: `runSendMessage` ruft `ctx.clearInput()` auch, wenn der Text von
    außen kommt (Schnellantwort, Modul-Antwort, Auftrag der Gastseite) — ein angefangener Entwurf
    im Eingabefeld geht dabei verloren. Leeren nur, wenn das Eingabefeld der Absender war.
  - Gefüllter Knopf „Antworten“ (`ui-entscheidung__senden`, `primary`/`on-primary`): gesperrt nur
    über `opacity: .5`; Kontrast im gesperrten Zustand und im dunklen Thema nicht gemessen
    (gesperrte Bedienelemente sind von WCAG 1.4.3 ausgenommen, der Hinweis bleibt als Prüfpunkt).
  - `shell/chat-shell.component.ts` (rund 1110 Zeilen, dokumentierte Ausnahme): `modulTreffer`/
    `modulAntworten` nicht in eine `modul-naht.ts` gezogen — die Naht bräuchte eine eigene
    Schnittstelle so groß wie der verschobene Code.
  - `controllers/collection-actions.ts` `showMoreCards` (flaches Kachelraster der Shell) scrollt
    weiter `smooth` ohne Rücksicht auf `prefers-reduced-motion`; im Modul `ui_trefferliste` behoben.
  - Build-Warnung NG8102 in `ui-bloecke.component.ts` (`d.block.text ?? ''`, `text` ist laut Typ
    Pflicht, alter Verlauf kann es weglassen) — bestand vorher, die Absicherung bleibt.
- **Paket U1-g, Reste aus dem Review** (Plan §17 „Offen (U1-g)“):
  - Ein Gold-Zug kann einen Knoten im Themenbaum nur getippt öffnen (die Quittung nennt dem Agenten keine Knoten); später ein Zug-Schlüssel `aktion` für Direktaktionen.
  - Ob der Server eine Auswahlfeld-Antwort annahm, zeigt die Chat-Antwort nicht (`gesendet`); dafür bräuchte es ein neues Debug-Feld.
  - Studio-Vergleich (`eval-compare`) und Messbedingungen nennen `ui_module`/`ui_module_wirksam` im Gruppentext nicht; die Gruppen trennen die Läufe trotzdem.
  - `services/eval/runner.py` 703 Zeilen (ALT-Abbild, über der Schwelle).
- **„coroutine … was never awaited“ in älteren Start-Tests:** `tests/test_eval_router.py::_patch_guard_and_spawn` schließt nur die äußere Koroutine (`mit_herzschlag`), die innere `_execute_…_run` bleibt offen — im vollen Lauf 2026-11-03: `test_eval_router.py` (4 Tests), `test_eval_pg.py` (1); dazu, anderer Ursache, `test_startup_warmup.py` (2 Tests, je 4). In `test_eval_ui_module.py` behoben (Attrappe `_ohne_start`, Review U1-g #14); gleiche Abhilfe für die älteren Tests: `mit_herzschlag` mit ersetzen und die innere Koroutine schließen.
- ~~**Paket U1 — vier Postgres-Tests veraltet**~~ erledigt 2026-11-03 ([`aenderungen/2026-11-03-paket-u1-db-tests.md`](aenderungen/2026-11-03-paket-u1-db-tests.md)): alle vier Tests veraltet, der Code entsprach dem Plan; ganze Suite mit Postgres grün (7786 bestanden, 4 übersprungen).

## 6 Zurückgestellte Plan-Teile

- **AS-5c `direkt` (Plan 2026-11-09 §5g, A5-5):** Start eines Ablaufs durch die KI ohne Knopf — erst
  mit Treiber-Ausgabe im selben Zug und eigener Bremse gegen Schleifen; bis dahin schlägt die KI
  immer per Knopf vor.

- **MCP-Vertrag (2026-11-07), bewusst nicht gebaut oder verschoben:**
  - `resolve_wlo_filters` als interne Filterauflösung: unsere Argumentauflösung macht dasselbe vor jeder Suche; eine
    Umstellung ändert jede Suche und ihre Zeiten — eigener, gemessener Schritt.
  - `get_node_details` mit `nodeIds` (deckt `get_nodes_details` ab).
  - `services/page_duplicate.py` (Dublettenprüfung beim Seitengruß) auf `find_content_by_url` umstellen.
  - `browse_collection_tree` Tiefe 3 im Muster-Weg strukturell kürzen (heute JSON hinter dem 4 000-Zeichen-Deckel;
    `truncated` am Ende geht verloren — älter, mit M4 größer).
  - `search_wlo_collections` und `search_wlo_within_collection` in `SPERRE_PERSOENLICH` aufnehmen (älter).
  - Pläne: Eingang „In WLO anlegen“ aus dem Strukturentwurf; Fortsetzen einer früheren Stapel-Ablage aus der Liste
    „letzte Ablagen“; Pläne über `/api/agent` (`write_mode=execute`) nur als Vorschau.
  - Seltener Randfall: „Plan fortsetzen“ vor dem Anlaufen eines langsamen ersten Abschnitts → `plan_expired`, der
    später anlaufende Plan bleibt bis zu seiner Frist ohne Knopf.
- **Aus dem Review vom 2026-11-07 (älter als M1–M7, nur eingetragen):**
  - `services/page_duplicate.py`: die Seitenadresse geht als Volltext-`query` an `search_wlo_content`; der Server
    nimmt höchstens 200 Zeichen — bei längeren Adressen bleibt die Prüfung „unklar“ und der Seitengruß bietet nie
    „aufnehmen“ an. Mit der Umstellung auf `find_content_by_url` erledigt.
  - `SearchWloArgs.query` ohne Längengrenze (Server: 200 → der ganze Aufruf scheitert, Kürzen wäre besser);
    `search_wlo_all`, `get_topic_page_content`, `get_wlo_content_text` ohne Argument-Modell.
  - Der Server hängt an `get_collection_contents`/`get_node_details`/`search_wlo_within_collection` die Skill-Liste
    und die Anweisung der Redaktion an — im Agent-Weg ungerahmt (`get_skill_registry` wird gerahmt).
  - `SPERRE_PERSOENLICH`: auch `get_wikipedia_summary` (externer Dienst) fehlt.
  - `services/write_approval.py`: fachliche Ablehnungen (`invalid_input`, `exists`) laufen als `logger.error`.
  - `services/tool_loop.py`: legt das Modell im Bestätigungszug zuerst eine abweichende Vorschau an und führt danach
    die abgenommene aus, löscht `pop("_pending_write")` auch den neuen Merkposten (Randfall).
  - Studio-Vorschau zeigt im Upload-Modul keine Liste der letzten Ablagen (keine Antwort mit `letzte`).

- **B1–B3 (Anrede)** folgen nach der Nachmessung (Runde-2-Plan, Paket B).
- ST-4c, ST-3d und die Architektur-Referenz sind in Paket 6 gebaut.
- **Verlaufsfenster blockweise bzw. positionsunabhängig kürzen** (Rest von C1): Nutzer 2026-10-09 — erstmal lassen, viel Korrekturbedarf bei wenig Mehrwert. Erklärung und Messwerte im Paket-8-Plan, Abschnitt C.
- **Rest von P5-7** (Paket 8, P — nicht jetzt, Gründe im Plan): Docker-Socket-Proxy, Sicherung auf einem zweiten Rechner, eigene Studio-Sitzungen statt des festen Cookie-Tokens, CORS zu (braucht die Liste der echten Einbettungen), eine CSP für die Demo-Seiten (tragen Inline-Skripte).
- **Paket 15, später (Nutzer-Entscheid 2026-10-17 bzw. bewusst nicht gebaut):** freie Persona-Gespräche in der Evaluation (eigenes Paket); Werkzeug-Regeln mit Anliegen-Bedingung auch im Agent-Modus (der Agent erkennt keine Anliegen — heute greifen dort nur Regeln ohne Bedingung, das Studio sagt es am Regelwerk); MCP-Sitzung über Züge wiederverwenden und den Master-Skill beim Start vorwärmen (Lasttest-Befund: erste Suche 22 s, `docs/mcp-und-anmeldung.md` §6); Kontext-Aktionen als Tabelle je Seitentyp (Pivot) statt der generischen Liste.
- **Aus dem Review von Paket 15 (älter, nicht dringend):** `settings.eval_chat_url` liest niemand — `services/eval/run_store.py` nimmt `EVAL_CHAT_URL` per `os.getenv`, die Vorgabe (8100) steht damit doppelt. Beim nächsten Griff an den Eval-Start auf die Settings umstellen.
- **Aus Review-Runde 2 von Paket 15 (2026-10-18), älter als Paket 15 — nur eingetragen:**
  - Tour: `WebsiteTourBlock.home_path`/`content_hub`/`contact_hub` haben im Modell die Vorgabe `""`, `domain/tour.py` setzt aber `/home/`, `/bildungsinhalte/`, `/mitmachen/` ein. Seit A3 zeigt das Studio für einen fehlenden Schlüssel `""` mit Plakette „Vorgabe“. Der Seed setzt alle drei, sichtbar erst nach dem Löschen eines Schlüssels. Der A3-Wächter prüft Schema gegen Modell, nicht Modell gegen Lader.
  - `schema-form/json-value.component.ts` (`commit`): „Kein gültiges JSON: …“ fest deutsch — im englischen Studio deutsch. Katalogschlüssel mit `{detail}`.
  - Lasttest-Karte: Stufenspalten (p50/p95/max) und `rps` als Rohzahlen ohne `StudioFormat` (die neue Zeile je Kategorie formatiert seit Runde 2).
  - Anrede-Tabelle (Paket 14): leeres `<td>` als Kopf der Aktionsspalte; `display:flex` direkt auf `<td>`; je Zeile ein `role="status"`.
  - `AsyncData`: scheitert ein Abruf nach einem Arbeitsbereich-Wechsel, bleibt die Summe der anderen Maschine neben dem Fehler stehen (Kosten).
  - Gold-Start: werden nach einer Flow-Änderung alle gewählten Kennungen ungültig, ist der Start-Knopf ohne Erklärung grau.
  - Werkzeuge: die Sperre `policy` verlinkt auf „Identität & Schutz“ (Muster-Seite) — im Agent-Arbeitsbereich steht das Regelwerk auf „Rolle & Grenzen“ (`agent-tools.ts`, `lockLink`).
- **Aus Paket 18, bewusst nicht jetzt:** Circuit-Breaker für einen toten Endpunkt (kostet nur im Fehlerfall Zeit); die Rechtsprüfung sieht nur die ersten 8000 Zeichen einer Nachricht (bis RB-1: 2000); „Testnachricht“ auf Englisch ergibt weiter `quiz` („Test“ heißt auch Klassenarbeit); Zähler für Warteschlange und DB-Pool, Gesamtfrist für Musterzüge (Plan 18 „später“). Bewusst gelassen in 18E: der Eval-Judge übernimmt den Anbietertext in `JudgeError` (synthetische Gespräche), einige Konsolenzeilen des Widgets geben das Fehlerobjekt weiter (seit 18D ohne Inhalt). Ungeklärt: warum die GitHub-Runner seit 18E-2 die ersten Agent-Runden langsamer rechnen — der betroffene Test hat jetzt Spielraum (Plan-Log 18E/18F).
