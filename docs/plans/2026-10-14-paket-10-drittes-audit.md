# Paket 10 — Drittes Audit (Codestand 09.10.) prüfen und beheben

**Stand:** 2026-10-14 · **Quellen:** [`../audits/2026-10-10-fehlerprotokoll.md`](../audits/2026-10-10-fehlerprotokoll.md),
[`../audits/2026-10-10-kurzaudit-auth-mcp-schreiben.md`](../audits/2026-10-10-kurzaudit-auth-mcp-schreiben.md),
[`../audits/2026-10-10-verbesserungsprotokoll.md`](../audits/2026-10-10-verbesserungsprotokoll.md).

Der Prüfer hat nur gelesen und nichts ausgeführt. Jeder Befund wurde deshalb am aktuellen Quelltext
nachgeprüft (Spalte „Prüfung“), bevor etwas geändert wird. Vorgehen wie in Paket 9: Test zuerst, Dateien
≤ 300 Zeilen, Texte de/en, Widerspruch mit Begründung, Log unten.

**Einordnung:** *beheben* · *Entscheidung* (Nutzer) · *messen* (erst Zahlen) · *optional* (zutreffend,
geringe Wirkung) · *trägt nicht*.

**Nutzer-Entscheid 2026-10-14:** `?bsid=` behält Vorrang vor Cookie und localStorage (H-1).

## 1 Befunde

### Fehlerprotokoll

| # | Prüfung | Einordnung | Stand |
|---|---|---|---|
| H-1 `bsid`-Übernahme + offener Verlauf | bestätigt (`session-id.ts` Stufe A, `GET /sessions/{id}/messages` öffentlich) | Entscheidung gefallen: Vorrang bleibt; Restrisiko in `entscheidungen-offen.md` | [x] |
| H-2 Startauftrag verworfen | bestätigt (`runSendMessage` kehrt bei `isLoading` still zurück; Erstaufruf wartet auf den Kontext-Ping) | Warteschlange in der Shell + Spec | [x] |
| H-3 OAuth-Fenster nach drei `await` | bestätigt (`mcp-oauth.signIn`) | `about:blank` synchron, Adresse danach, jeder Ausstieg schließt + Specs | [x] |
| M-1 Commit-Fehler ohne Rollback | bestätigt (`save_message`/`update_session` committen, Aufrufer schlucken) | beheben zentral in beiden Helfern + pg-Test | [x] |
| M-2 Studio-Proxy ohne CSRF-Zweitschutz | bestätigt (nur `SameSite=Strict`) | beheben: `Sec-Fetch-Site`/`Origin` für ändernde Methoden | [x] |
| M-3 HNSW + Bereichsfilter | gemessen: Planer nimmt bei 906 Abschnitten den B-Baum auf `area` + exakte Sortierung, auch ohne Seq-/Bitmap-Scan; 3/3 Treffer im kleinsten Bereich (10) | trägt heute nicht; bei Wachstum `hnsw.iterative_scan` (pgvector 0.8.5) | — |
| M-4 Meta-Cache veraltet | bestätigt (Ablauf/Neusetzen lässt alte Metas stehen) | beheben + Test | [x] |
| M-5 Klassifikator ohne Frist | bestätigt (nur 75 s Transport + Wiederholungen; Aufrufer fällt bei Fehler schon auf Vorgabe zurück) | beheben: Frist um den Aufruf, Einstellung | [x] |
| M-6 `rel`/`target` aus Modelltext | bestätigt (`rel="opener"` überlebt) | beheben + Spec | [x] |
| M-7 Bilder im Bot-Markdown | bestätigt; schwerer als beschrieben: Bild-URL kann Gesprächsinhalt ohne Klick nach außen tragen. Kein Seed/Backend erzeugt Markdown-Bilder | beheben: Nachladendes verbieten + Spec | [x] |
| M-8 DB-Pool fest | bestätigt (SQLAlchemy-Vorgabe 5+10) | beheben: Einstellungen, Vorgaben unverändert, Doku | [x] |
| M-9 Widget kaum getestet | zutreffend (4 Specs; die Logik liegt in `ui`) | Specs zu H-2, H-3, L-9, A-3 dazu; Ausbau optional | [x] |
| L-1 Vokabel-Fehler dauerhaft gecacht | bestätigt | beheben | [x] |
| L-2 Label-Cache einmal je Prozess | zutreffend, Vokabulare ändern sich selten, Deploy lädt neu | optional | — |
| L-3 `get_always_on_rag_context` | bestätigt: ohne Aufrufer | beheben: entfernen | [x] |
| L-4 Rumpf-Grenze am rohen Pfad | bestätigt (hinter Präfix 16 statt 2 MiB) | `route_path` geteilt (`api/scope_pfad.py`) + Test | [x] |
| L-5 erster XFF-Eintrag | zutreffend, mit traefik-Standard nicht ausnutzbar | Betriebsdoku `deploy/README.md` | [x] |
| L-6 f-String-SQL aus Konstanten | kein Request-Wert | optional | — |
| L-7 SSE nur `\n\n`, kein Decoder-Flush | bestätigt (theoretisch) | beheben (billig) | [x] |
| L-8 doppelte Screenreader-Ansagen | ohne Screenreader-Test nicht belastbar | optional (Test durch Menschen) | — |
| L-9 Fokus zurückgerissen, Enter bei IME | bestätigt (kein `isComposing`) | Fokus nur aus dem Chat/von nirgends, nicht auf Touch; IME + Spec | [x] |
| L-10 Aufräumen beim Entfernen | teilweise: Verlaufsnachfrage bricht seit Paket 9 ab; Strom-Abbruch würde den POST-Rückfall auslösen | optional (eigener Entwurf) | — |
| L-11 MutationObserver ohne Drossel | zutreffend, geringe Wirkung | optional | — |
| L-12 M16 wartet die spekulative Suche ab | bestätigt | beheben + Test | [x] |
| L-13 Lease-Verlust nur geloggt | dokumentiert | optional | — |
| Drift: CLAUDE.md „Angular 21“, verwaiste `.pyc` | bestätigt (`@angular/core ^22.2.1`; `.pyc` gitignored, ohne Quelle) | Angular 22 eingetragen, `.pyc` gelöscht | [x] |

### Kurzaudit Anmeldung und Schreibwege

| # | Prüfung | Einordnung | Stand |
|---|---|---|---|
| A-1 Erfundener Block hebt Deckel auf | bestätigt (`has_personal_auth` = Formprüfung) | V-1: `wlo_auth_status` je Zug, Cache je Fingerabdruck | [x] |
| A-2 Block im `sessionStorage` der Gastseite | bestätigt, dokumentierte Abwägung | Entscheidung (mit MCP-Team) | — |
| A-3 Ungültiger Block: kein Signal, Doppelaufruf | bestätigt (401 → `transport` → Wiederholung) | Art `auth` ohne Wiederholung, Block fällt weg, `auth_invalid` ans Widget | [x] |
| A-4 Abmelden widerruft nicht | bestätigt; der Satz ist schon genau („aus diesem Tab entfernt“) | Widerruf → Entscheidung mit MCP-Team; Text trägt nicht | — |
| A-5 = H-3 | — | mit H-3 | [x] |
| A-6 Freitext-Zustimmung | bestätigt; K1 (2026-10-09) wollte „Freigabe!“ als Zustimmung | Entscheid 2026-10-15: Liste + LLM-Prüfung | ✅ |
| A-7 Vorschau im öffentlichen Verlauf | bestätigt; hängt an H-1 | Entscheidung | — |
| A-8 Schreib-Argumente auf INFO | bestätigt | beheben | [x] |
| A-9 `allow_curation` per Vorgabe | zutreffend, aber **bewusst so** (Paket 7, S4: bei `/api/agent` entscheidet der Aufrufer; ohne Person nur Vorschau, `agent_write`) | Entscheidung (Vertrag); nicht geändert | — |
| A-10 Persistenz ohne Rollback | bestätigt | mit M-1 + WARNING | [x] |
| S-1 neuer Block zwischen Vorschau und „Ja“ | **belegt**: der MCP-Server verschlüsselt jeden Block mit zufälligem Schlüssel/IV (`access-token.ts`) | Abnahme an die bestätigte Person (`aufrufer_kennung`) | [x] |
| S-2 Repository-Sitzung abgelaufen | belegt (`prepared-write.ts`, `esguest`) | entschieden 2026-10-15 (Nutzer): kein Knopf — Anmeldung läuft über den Widget-Knopf und den MCP-Server; neu denken, wenn sich die Kette ändert | — |
| S-3 neuer Tab | belegt (Block je Tab im `sessionStorage`) | Hinweis + Anmelde-Chip beim „Ja“ (`abnahme_hinweis`) | [x] |
| S-4 Ticket-Tausch nicht fertig | belegt (nichts hielt das Senden an) | Züge warten auf den Tausch, höchstens 5 s | [x] |
| S-5 „Ja“ nicht erkannt | belegt, mit Paket 10 eher strenger | über A-6 | ✅ |
| S-6 Zwischenzug / Frist | belegt (600 s; sichtbarer Gruß verwirft — Regel aus Audit 2026-09-29) | Frist in der Box [x]; Gruß unterdrücken: entschieden 2026-10-15 (Nutzer) — bleibt so, dokumentiert | [x] |
| S-7 falsches Muster | belegt für den Muster-Modus (nur M18/M20) | Klassifikator + Nachsteuerung; Golden-Flow (Nutzer) | ✅ |
| S-8 = A-3 | — | mit A-3 | [x] |
| S-9 (neu durch Paket 10) | MCP bei der Echtheitsprüfung nicht erreichbar → Zug anonym (30 s) | Diagnosezeile `Anmeldung nicht prüfbar (…)`; Hinweis wie S-3 | [x] |

### Verbesserungsprotokoll

Nur Vorschläge; der Prüfer verlangt selbst Messungen vorher. Mit Befunden deckungsgleich und deshalb
hier umgesetzt: A-1 (= M-5), A-4 (= L-12), P-7 (= M-8). Bewertung der übrigen im Log.

### Paket-9-Prüfer (2026-10-14)

Ein frischer Prüfer hat die Paket-9-Änderungen gelesen und reine Funktionen mit Proben aufgerufen
(keine Tests, kein Netz). Jeder Befund wird hier am Quelltext nachgeprüft.

| # | Befund | Prüfung | Stand |
|---|---|---|---|
| P9-1 (kritisch) | `tool_loop`: die Bereichsprüfung von `query_knowledge` überschreibt `_angeboten` — danach gilt jede Suche als „nicht im Katalog“ | bestätigt (Test rot: beide Suchen verworfen) | [x] |
| P9-2 | `is_affirmation`: Absagen („Freigabe abgesagt“, „ok, vergiss es“, „yes but …“) gelten als Zustimmung | bestätigt (alle 12 Proben) | Erlaubnisliste statt Verbotsliste | [x] |
| P9-3 | Krisen-Wendungen: Wortstellung, Abstand über 40 Zeichen, Absichtsverben; ein `_ANLASS`-Wort unterdrückt jeden Abschied | Fälle 1–5 bestätigt; Abschied mit Anlass in anderem Satz: Satzgrenze schlüge bei der Paket-8-Gegenprobe mit Punkt an | 1–5 behoben; Abschied → Entscheidung | [x] |
| P9-4 | Moderation: Warten auf einen freien Platz ohne Frist | bestätigt | eine Frist über Warten und Aufruf | [x] |
| P9-5 | Sicherheitsmuster ohne Kennung speicher- und wiederherstellbar (auch über BOM) | bestätigt (Lader überspringt, BOM leert Frontmatter) | behoben | [x] |
| P9-6 | `entschaerfe_endmarken` nicht idempotent (`[[ENDE …]]`) | bestätigt | höchstens 3 Durchgänge, dann jede eckige Klammer rund (linear) | [x] |
| P9-7 | Verlaufsnachfrage ohne `after_id` kann ein altes `prepared_write` noch einmal ausführen | bestätigt | ohne sichere Zuordnung keine Antwort mit Änderung | [x] |
| P9-8 | Seitenkontext: `json.dumps` vor dem Entschärfen — ein Tab trennt die Marke | bestätigt | jeden Text vor `json.dumps` entschärfen | [x] |
| P9-9 | Übrige Doppelgänger (É, Kapitälchen, Hangul-Füllzeichen) | bestätigt | NFKD ohne Akzente, Tabelle ergänzt | [x] |
| P9-10 | Im Studio verborgene Werkzeuge stehen in `blocked_tools` → Sicherheitszweig statt Katalog-Abweisung | bestätigt; dazu: zwei Auswahl-Zweige reichen `TOOL_DEFINITIONS` ungefiltert | Katalog der Schleife ohne Verborgenes, Schleife nur mit Sicherheitssperren | [x] |
| P9-11 | Nebenwege ohne Sperrprüfung: `search_wlo_content` in der Auswahl, Aufteilung von `search_wlo_all` | (a) bestätigt; (b) war über `_assemble_messages` gedeckt, mit P9-10 nötig | beide behoben | [x] |
| P9-12 | Aufbewahrung `_stand_leeren`: äußeres UPDATE ohne Zeit- und Inhaltsbedingung | bestätigt (pg nachgestellt: frischer `_pending_write` geleert) | Bedingungen auch außen | [x] |
| P9-13 | Herunterfahren: 30 s uvicorn + 25 s + 5 s gegen `stop_grace_period` 40 s | bestätigt (nacheinander, nicht parallel) | `stop_grace_period` 65 s + Wächter | [x] |
| P9-14 | Umwandlung: Ausgabe des Kindprozesses ungedeckelt, `/Count` der Datei vertraut | Rückgabe bestätigt; `/Count` trägt nicht (nur Vorprüfung, Frist und Speichergrenze schützen) | Textdeckel 50 Mio. Zeichen | [x] |
| NIT | Doku `aufbewahrung.py`; `result` vor späterem Transportfehler; `area` als Liste; `prozess.start()` wirft | alle bestätigt | behoben (Wurf: Docstring ehrlich, 500 ist richtig) | [x] |

## 2 Log

### Backend, erster Block (M-1, M-2, M-4, M-5, M-8, L-1, L-3, L-12, A-8, A-10)

- **M-1, A-10** `db_sessions.save_message`/`update_session` rollen bei einem Fehler selbst zurück
  (`_zurueckrollen`, dieselbe Regel wie `finalize_message`) und reichen ihn weiter; die Aufrufer, die ihn
  schlucken, lassen die Sitzung damit benutzbar. pg-Test mit Fremdschlüssel- und Typfehler
  (Rot vorher: `PendingRollbackError`). `write_approval._persist` loggt den Fehler auf WARNING.
- **M-2** `studio_proxy._fremde_seite`: ändernde Anfragen (nicht GET/HEAD/OPTIONS) mit `Sec-Fetch-Site`
  ≠ `same-origin` oder — ohne Fetch-Metadaten — mit fremdem `Origin` enden mit 403; ohne beide Kopfzeilen
  kein Browser, also durch. Ein Skript auf demselben Ursprung lässt sich so nicht erkennen (dafür die
  CSP der Demo-Seiten, Befundliste §6). Tests in `test_studio_proxy_ursprung.py`.
- **M-4** `tool_cache`: Ablauf und Neusetzen entfernen die Metas des alten Werts.
- **M-5** `classify`: eigene Frist um den Aufruf (`CLASSIFY_TIMEOUT_S`, Vorgabe 20 s, Untergrenze 1 s),
  danach `TimeoutError` → `assess` nimmt die Vorgabe-Klassifikation. Gemessen an 84 Dev-Zügen: Median
  2,9 s, p99 6,5 s, Max 7,4 s — die vorgeschlagenen 8–10 s wären zu knapp gewesen.
- **M-8** `DB_POOL_SIZE`/`DB_MAX_OVERFLOW` (Vorgaben 5/10 wie bisher), `.env.example`, Compose.
- **L-1** Ein LLM-Fehler beim Vokabelabgleich wird nicht mehr als „kein Treffer“ gemerkt (der alte Test
  hielt genau dieses Verhalten fest und ist entsprechend umgestellt).
- **L-3** `get_always_on_rag_context` und `config_loader.get_always_on_rag_areas` entfernt — ohne
  Aufrufer; „always“ wirkt über `route_head` und `rag/vorab`.
- **L-12** M16 bricht die spekulative Suche ab statt sie abzuwarten (Test mit hängender Suche).
- **A-8** Kurations-Werkzeuge: auf INFO nur Schlüssel und Längen, die Werte auf DEBUG.

### Widget, erster Block (M-6, M-7, L-7)

- **M-6, M-7** `markdown-renderer`: Nachladendes ist im Bot-Markdown verboten (`img`, SVG-`image`,
  Medien, `style`; Attribute `style`, `background`, `poster`, `srcset`) — eine Bild-URL konnte
  Gesprächsinhalt ohne Klick nach außen tragen. Jeder Link mit `target` bekommt `noopener noreferrer`,
  auch gegen ein mitgeliefertes `rel`.
- **L-7** `stream-client`: `\r\n` und `\r` gelten als Zeilenende (auch über Stückgrenzen), am Ende
  wird der Decoder geleert.

### Paket-9-Prüfer (P9-1 … P9-14)

- **P9-1 (kritisch)** `tool_loop`: die Bereichsprüfung von `query_knowledge` hieß `_angeboten` und
  überschrieb den Werkzeug-Katalog des Zuges — danach war jede Suche „nicht im Katalog“ (eingeführt mit
  V2). Umbenannt; Test mit Wissensabfrage und Suche in derselben und der nächsten Runde. Dazu: ein
  Bereich als Liste wirft keinen `TypeError` mehr.
- **P9-2** `zustimmung`: jedes Wort muss zur Zustimmung gehören oder ein harmloses Beiwort sein
  (Erlaubnisliste); die Verbotslisten entfallen. Geprüft gegen die Bestätigungsformeln des MCP-Servers
  („Zum <Verb> bitte bestätigen.“, live 2026-10-08 „Zum Aufnehmen bestätigen“) — sonst entstünde die
  Schleife vor K1 neu. „Zum Ablehnen …“ bleibt eine zweite Frage (Vorgang und Absage zugleich), ebenso
  „ok, danke“, „Ok, alles gut“, „Ja, gleich“. Zwei Tests nahmen „Ja, zeig mir mehr Videos“ als
  Zustimmung — das ist jetzt ein neuer Auftrag; sie nehmen „Ja, gerne“.
- **P9-3** `krisen_wendungen`: beide Wortstellungen („Manchmal möchte ich …“, nicht die Frage am
  Satzanfang), Fenster 60 Zeichen ohne Nebensatz über Dritte (warum/ob/wie/dass/er/sie/man) — damit
  auch der bestehende Fehlalarm „Ich würde gern wissen, warum Dornröschen nie wieder aufwachen
  sollte“ weg —, Absichtsverben nur mit „zu machen“, Zeitwörter zwischen „ich werde“ und „mit dem Leben
  Schluss“. Abschied mit Anlass in einem anderen Satz: nicht geändert, Entscheidung beim Nutzer
  (`entscheidungen-offen.md`).
- **P9-4** Moderation: `asyncio.timeout` über Warten auf einen der eigenen Plätze und Aufruf.
- **P9-5** Ein Sicherheitsmuster behält seine Kennung auch, wenn sie geleert wird oder fehlt
  (`kennungs_einwand`, `pruefe_kennung`); Sicherungen werden mit `utf-8-sig` gelesen.
- **P9-6** Entschärfen idempotent: höchstens drei Durchgänge (ein zweiter nur, wenn eckige Klammern
  übrig sind), danach jede eckige Klammer rund. Der Teil liegt jetzt in `domain/endmarken.py`
  (`untrusted_text` war über 300 Zeilen).
- **P9-7** Ohne `after_id` übernimmt die Verlaufsnachfrage keine Antwort mit Änderung — der Hinweis
  „veraltet“ statt einer fremden Antwort, die „wird ausgeführt“ sagt (strenger als vorgeschlagen).
  Dazu: ein schon empfangenes `result` geht einem späteren Verbindungsabbruch vor.
- **P9-8** Rohdaten des Klassifikators: jeder Text vor `json.dumps` entschärft.
- **P9-9** Lesart NFKD ohne Kombinationszeichen; Kapitälchen, т н к м, Hangul-Füllzeichen.
- **P9-10/11** Die Werkzeugschleife bekommt nur die Sperren der Sicherheit, ihr Katalog schließt
  Verborgenes aus (ein Aufruf: `NICHT_ANGEBOTEN`, kein `error`). Vorab Geholtes — auch die Aufteilung
  von `search_wlo_all` — prüft der Knoten gegen Sperre und Verborgenes; der Nachschub der
  Inhaltssuche beim Medientyp prüft die Sperre.
- **P9-12** `_stand_leeren`: Zeit- und Inhaltsbedingung auch im äußeren `WHERE` (pg-Test mit zwei
  Verbindungen, Warten über `pg_stat_activity`).
- **P9-13** `stop_grace_period` 65 s; Wächter rechnet uvicorn + Nachlauf + Abbruch + Aufräumen.
- **P9-14** Textdeckel 50 Mio. Zeichen im Kindprozess (`text_zu_lang`, de/en).

### Widget, zweiter Block (H-2, H-3, L-9)

- **H-2** `chat-shell`: ein Auftrag der Gastseite während eines laufenden Zugs (beim Erstaufruf meist der
  Kontext-Ping) wartet in einer Schlange; der Effekt `_nachDemLaden` startet ihn nach dem Laden, vor einem
  zurückgestellten Seitengruß. Das Promise erfüllt sich erst mit seinem Zug; beim Entfernen des Widgets
  werden wartende Promises erfüllt statt zu hängen.
- **H-3** `mcp-oauth.signIn`: das Fenster öffnet sich mit `about:blank` im Takt des Klicks, die Adresse
  kommt nach Discovery, Registrierung und Prüfsumme; jeder Ausstieg schließt es (`finally`).
- **L-9** Enter während einer IME-Komposition sendet nicht (`isComposing`, `keyCode` 229). Nach einem Zug
  kommt der Fokus nur zurück, wenn er im Chat lag oder nirgends — nicht von der Gastseite weg, und auf
  Touch-Geräten nur aus dem Chat heraus (`shell/fokus-nach-dem-zug.ts`; im Shadow DOM über
  `getRootNode`). Das Öffnen des Panels fokussiert weiter.

### Anmeldung (A-1, S-1, A-3) — V-1 und V-3 aus dem Kurzaudit

- `services/mcp/anmeldung.py` (neu): jeder Zug mit persönlich aussehendem Block fragt einmal
  `wlo_auth_status` am primären Server (Frist 5 s), Ergebnis je Fingerabdruck 5 min (Person) bzw. 30 s
  (sonst). Person = `mode: user` und `authenticated: true`; ihre Kennung ist ein Streuwert der
  `authority`. Abgewiesen (401/403 oder `authenticated: false`) → der Block fällt für den Rest des Zuges
  weg, der Zug läuft anonym weiter. Keine Antwort → keine Person, der Block bleibt.
- `auth.has_personal_auth()` gilt nur mit dieser Bestätigung (A-1: Deckel, `execute`, Schreibangebot).
  `aufrufer_kennung()` bindet Abnahmen an die Person statt an den Block (S-1); `caller_fingerprint` bleibt
  für den Werkzeug-Cache.
- Ein Stand-Objekt je Zug (`auth._ZugStand`), weil LangGraph jeden Knoten als eigene Task fährt: eine
  Abweisung mitten im Zug gilt für alle späteren Knoten und den Endpunkt (Test über Task-Grenzen).
- Transport: 401/403 aus der Ausnahmegruppe des SDK → Art `auth`; der Client wiederholt sie nicht und
  meldet sie (`markiere_abgelehnt`, nur für den Block des Zuges, nicht den der Anlage). In der Abnahme
  zählt `auth` wie `tool`: nichts geschrieben.
- `api/turn_auth.uebernimm_zugang` an allen vier Einstiegen (`/api/chat`, `/chat/stream`, `/api/agent`,
  `/agent/stream`). `ChatResponse.auth_invalid` (Vertragszusatz, genau ein Blatt; gemessen per Erzeugung
  ohne das Feld) → das Widget räumt den Block, der Knopf zeigt „Anmelden“, ein Satz sagt warum (de/en).
- Tests: `conftest` ersetzt nur die Netzgrenze (`anmeldung._fragen`: wohlgeformter Block = Person,
  Kennung = Fingerabdruck — die Bedeutung vor Paket 10); `test_mcp_anmeldung.py` holt die echte Abfrage
  zurück. 15 bestehende Tests umgestellt: Block direkt gesetzt → `helfer_anmeldung.als_person`;
  gepatchte Naht `caller_fingerprint` → `aufrufer_kennung`.
- `auth.py` über 300 Zeilen → die httpx-Fabrik liegt jetzt in `mcp/http_fabrik.py`.

### Rest (L-4, L-5, Drift, M-3)

- **L-4** `api/scope_pfad.route_path` teilen sich Studio-Proxy und Rumpf-Grenze.
- **L-5** `deploy/README.md`, Abschnitt „Vor einem CDN oder weiteren Proxy“.
- **Drift** `CLAUDE.md` Angular 22; verwaiste `evals/__pycache__/engine_matrix_metrics…pyc` gelöscht.
- **M-3** gemessen (lesend, Dev-DB): pgvector 0.8.5; 8 Bereiche mit 10–246 Abschnitten (906 gesamt). Der
  Planer nimmt für `area = …` + `ORDER BY embedding <=> …` den B-Baum `idx_rag_area` und sortiert exakt —
  auch mit `enable_seqscan`/`enable_bitmapscan` aus; Abfrage aus einem fremden Bereich gegen den kleinsten
  (10) liefert 3 von 3. Der HNSW-Filterverlust tritt heute nicht auf; bei starkem Wachstum neu messen,
  dann `SET hnsw.iterative_scan = relaxed_order` (seit pgvector 0.8).

### Verbesserungsprotokoll — Bewertung

- **Umgesetzt (deckungsgleich mit Befunden):** A-1 (= M-5, Frist 20 s statt 8–10 s, gemessen), A-4
  (= L-12), P-7 (= M-8).
- **Erst messen** (der Prüfer verlangt das selbst): A-2 Cache-Trefferquote je Anbieter, A-3 httpx-Pool,
  A-5/A-6/A-7 Parallelisierung im Seitenkontext und Agent-Zug, A-8 Einbettungs-LRU, A-9 Rerank-Kürzung
  (Qualität per A/B), A-10 Persist bündeln, P-1 MCP-Aufrufe per `gather` (das Diagnose-Log nennt die
  Kandidaten), P-2 Single-Flight, P-3 RAG in einer SQL (bei 8 Bereichen klein), P-4 Ingest im Stapel,
  P-5 CE-Gate parallel. P-6 (Vorabruf neben der Klassifikation) mit Risiko laut `prefetch.py`.
- **Schon da oder bewusst anders:** A-11 — ein Strom ohne Zuhörer rechnet seit Paket 7 (P2) absichtlich
  zu Ende, damit die Antwort im Verlauf ankommt; F-2 = H-1-Option; F-6 Facetten-Chips aus `_queryMeta`
  gibt es (`turn_persist`).
- **Qualität und Funktionen:** Q-1 (Golden in CI) und Q-2 (Judge-Trend) berühren Läufe, die der Nutzer
  startet; Q-3 (RAG-Recall) wäre der Maßstab für M-3 bei Wachstum und für A-9; Q-5, Q-7, Q-9 passen zu
  den bekannten Todos (§5); F-1, F-3 … F-9 sind Produktentscheidungen.

### Nachtrag: spekulative Auth-Befunde (S-2 … S-9, 2026-10-15)

Alle acht am Code nachgeprüft (zuvor nur S-1 und S-8). Belegt als Mechanismus sind alle; welcher die
gemeldeten Fälle verursachte, klären erst Logs (Diagnose-Tabelle im Kurzaudit, ergänzt um S-9).

- **S-1/S-3/S-4/S-9 sichtbar machen** (`services/abnahme_hinweis.py`): stimmt jemand einer Vorschau zu,
  die unter einer anderen bzw. hier nicht geltenden Anmeldung entstand, setzt `discard_stale_approval`
  einen Merker, und der Vorlauf antwortet mit einem festen Satz (`write.callerChanged`, de/en) samt
  Anmelde-Chip, statt das „ja“ ohne Zusammenhang ans Modell zu geben (Ursache der gemeldeten
  Vorschau-Schleife). Gegenprobe: ein anderes Anliegen läuft normal.
- **S-4** `ChatApiClient.warteAufAnmeldung`: mit `ticket` warten `stream`/`post` bis zum Ende des Tauschs
  (`session/ticket-login.anmeldeSperre`, höchstens 5 s — eine Anlage ohne Anmeldung hält so nur einmal
  auf); die Shell setzt die Sperre schon vor der Anmelde-Adresse.
- **S-6(a)** Die Vorschau-Box nennt die Frist (`inline.writePreview.frist`, aus `TOKEN_TTL_SECONDS`).
- **Nicht umgesetzt:** S-6(b) Gruß bei offener Abnahme unterdrücken — widerspricht der Regel aus dem
  Audit 2026-09-29 (ein „ja“ nach einem Seitenwechsel könnte das neue Material meinen, ausgeführt würde das
  alte) → `entscheidungen-offen.md`. S-2 Knopf: keine belegte Anmelde-Adresse des Repositoriums, die
  Meldung sagt bereits, was zu tun ist. S-5 → A-6. S-7 → Klassifikator-Regeln und Golden-Flow (Nutzer).
- **Diagnosezeile S-9:** `Anmeldung nicht prüfbar (transport|timeout)` — der MCP-Server antwortete bei der
  Echtheitsprüfung nicht; der Zug galt bis zu 30 s als anonym.

## Nachtrag 2026-10-15 (2): A-6 und S-7 nach Nutzer-Entscheid

Entscheide: A-6 „Liste + LLM-Prüfung“, S-7 „Klassifikator + Nachsteuerung“ (beide Empfehlungen).

- **A-6** (`services/zustimmung_pruefen.py`, neu): `stimmt_zu(nachricht, werkzeug)` = Erlaubnisliste →
  Veto (`domain/zustimmung.hat_veto`: Verneinungen, Absagen, Änderungswünsche als Wörter und Wortanfänge,
  Fragezeichen) → LLM (Temperatur 0, `max_tokens` 5, Frist 3 s, Phase `zustimmung`, Nachricht auf
  300 Zeichen gekappt; nur die Antwort `zustimmung` zählt, jeder Fehler = nein). Geprüft wird einmal je
  Zug in `write_approval.discard_stale_approval` und nur bei offenem Vorgang ohne Direkt-Aktion;
  das Urteil liegt im Zugschlüssel `_zustimmung`, `redeem_write_approval` und der Werkzeugweg in
  `tool_loop` lesen es über `zugestimmt()` (ohne Urteil: die Liste). Der Chip-Filter in `turn_persist`
  bleibt bei der Liste. `conftest` ersetzt den Modellaufruf durch „nein“ (alte Bedeutung).
  Tests: `test_zustimmung_pruefen.py` (35), `test_write_approval.py::TestFreieZustimmung` (5),
  `test_agent_schreib_abnahme.py::test_eine_freie_zustimmung_…` (Ende zu Ende, Gegenprobe rot ohne Urteil).
  Live-Probe gegen OpenAI (gpt-6-luna, 18 Sätze): 17 wie erwartet; „ja, und such mir dann noch Videos“
  gilt als Zustimmung (Grenze, in `entscheidungen-offen.md`).
- **S-7** (`domain/kuration_umleitung.py`, neu; Schritt 3c in `graph/nodes/route`): nur Muster-Maschine,
  nur ohne Erzwingung durch Sicherheits-Gate oder Klärer und nur, wenn der Klassifikator nicht schon
  M18/M20 wählte. Auftragsverb (ganze Wörter) + Gegenstand (Wortanfänge) oder Webadresse, erstes Wort
  kein Fragewort → M18, mit Adresse M20; Logzeile `Kurations-Auftrag: … umgeleitet`. Wortlisten in
  `seeds/01-base/classify-overrides.yaml` → `curation_reroute` (Modell `CurationReroute`, Lader reicht
  den Block durch, Schema-Fixture neu erzeugt). Dazu Intent-Trigger `i09_curation_verbs`, drei
  Few-Shots und ein Satz in der Konfliktregel. Tests: `test_kuration_umleitung.py` (17, gegen die
  ausgelieferte Liste), `test_route_node.py` (2).
- **Deploy:** `classify-overrides` importieren (`import-config`), sonst bleibt die Umleitung leer und die
  neuen Few-Shots fehlen.

## Nachtrag 2026-10-15 (3): S-7-Wortlisten geschärft, Deploy-Weg belegt

- Wortlisten (`seeds/01-base/classify-overrides.yaml` → `curation_reroute`): Verben um übernehmen, packen,
  kopieren, verlinken, hochladen, veröffentlichen, ändern/aktualisieren, umbenennen (+ englisch) erweitert;
  Gegenstände um Metadaten, Themenseite, Redaktionstext; **„treffer“ entfernt** („Nimm die Videos aus den
  Treffern raus“ ist ein Filter); Fragewörter um wohin, wer, wozu, womit, darf, muss, brauche (Fragen
  nach Recht und Konto). Few-Shot „Erstelle eine neue Sammlung Optik“ → I09/M18 („erstelle“ steht
  bewusst nicht in der Verbliste, sonst landete „Erstelle ein Arbeitsblatt für meine Sammlung“ in M18).
  Tests zuerst: 12 neue Fälle rot, danach `test_kuration_umleitung.py` 30 grün.
- Deploy: `migrate` zieht nur fehlende Bereiche nach — ein vorhandenes `classify-overrides` kommt nie
  von selbst an. Weg für ein laufendes System in `deploy/README.md` („Einen einzelnen Bereich aus dem
  Abbild nachziehen“, `import-config --from` auf einen Teilbaum). Gegen eine Wegwerf-DB belegt: alter
  Stand importiert, Studio-Änderung an `welcome-config` simuliert, Teilimport → `imported 1 areas`,
  `curation_reroute` da, Studio-Änderung erhalten. Der `docker compose … sh -c`-Befehl selbst lief nicht
  (kein Image lokal).

