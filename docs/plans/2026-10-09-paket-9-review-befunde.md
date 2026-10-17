# Paket 9: Befunde aus dem Review von Paket 7 und 8 beheben (2026-10-09)

**Stand 2026-10-09: in Arbeit.** Auftrag (Nutzer): „better coding workflow skill nutzen und alle
befunde beheben“ — gemeint ist der Review-Bericht vom selben Tag (3 CRITICAL, 9 MAJOR, 26 MINOR,
NITs, dazu die vorbestehenden Punkte). Regeln wie immer: je Befund zuerst am Quelltext nachprüfen,
Test zuerst rot, Dateien ≤300 Zeilen, Texte de/en; Commits, Upload, Deploy und Golden-/Lastläufe
macht der Nutzer. B-API nur sparsam proben.

Die Nummern folgen dem Review-Bericht. Vorbestehende Punkte heißen V1…V8.

## 1 Befunde und Stand

### CRITICAL

- [x] **1** b-api-openai + gpt-6-luna: Werkzeugaufrufe scheitern (`llm.route`).
- [x] **2** `_schatten` blockiert die Ereignisschleife; Seitenkontext ohne Längengrenze.
- [x] **3** `KeyError` bei „İ“ (U+0130) in `entschaerfe_endmarken`.

### MAJOR

- [x] **4** Ablehnungen („Freigabe verweigert“) zählen als Zustimmung (`is_affirmation`), samt V1.
- [x] **5** „Exakt“ wiederherstellen löscht feste Bereiche und M01/M02.
- [x] **6** Dokument-Umwandlung ohne Zeit-, Speicher- und Parallelgrenze, samt V4.
- [x] **7** Antwort aus dem Verlauf verliert `prepared_write`.
- [x] **8** Moderation wartet auf einen Anbieter-Platz und lässt unter Last durch.
- [x] **9** Gepolsterte Endmarken kommen unverändert durch.
- [x] **10** Seitendaten ungerahmt im Systemprompt des Klassifikators; Cache-Verlust.
- [x] **11** Verborgene Werkzeuge erreichen das Modell (Vorabruf, Medientyp-Zweig).
- [x] **12** Krisen-Wendungen ohne Selbstbezug (Werther, Rauchen, Ruhestand …).

### MINOR

- [x] 13 Retention-Text („löscht nur ‚Gespräche löschen‘“) falsch.
- [x] 14 Lease-Schlüssel teilt sich den Raum mit ungeprüften Sitzungskennungen, samt V3.
- [x] 15 Fristen-Vorgaben 30 Tage im Modell gegen 90/180 in den Seeds; roher Wert `"30"`.
- [x] 16 Überblick zählt nur beim Öffnen; „Jetzt bereinigen“ löscht schon mit neuer Frist.
- [x] 17 Angular-Fehler 911 nach Verlassen während eines Laufs.
- [x] 18 Eigener Lader statt `AsyncData` im Retention-Panel.
- [x] 19 Kein Index auf `created_at` für `messages`/`memory`.
- [x] 20 AcademicCloud: Einbettungen gehen über die b-api an OpenAI (Doku/Entscheid).
- [x] 21 `mcp_herkunft`: Zugangsdaten im Bündel, IPv6/Unterstrich fallen aus der CSP.
- [x] 22 Druckfenster: Listener und Timer in der öffnenden Seite.
- [x] 23 Verlaufsnachfrage: Fristen zählen nur Pausen; Abrufe ohne Timeout.
- [x] 24 Späte Antwort nach Zerstören/Neustart läuft noch in `_onResult`.
- [x] 25 „beschäftigt“ legt auch Chips/Gastseiten-Aufträge ins Eingabefeld, ohne Grenze.
- [x] 26 `Retry-After` per CORS nicht lesbar; 0 gilt als „fehlt“; zu großer Wert beendet sofort.
- [x] 27 Gast-Schreiben gilt mit anonymem Zug-Block als erlaubt.
- [x] 28 Nachlaufender Zug: keine Fehlerblase gespeichert.
- [x] 29 Herunterfahren wartet nicht auf nachlaufende Züge.
- [x] 30 Datenbankfehler beim Sperren → HTTP 500.
- [x] 31 Studio-Auftragstester zählt als Produktion.
- [x] 32 Wiederherstellen: gestrichene Bereiche und `pruefe_kennung` ungeprüft.
- [x] 33 `RagAbruf` nimmt lockere Typen an, der Leser verwirft sie.
- [x] 34 Medientyp hängt die Suche an Muster ohne Werkzeuge.
- [x] 35 Hinweis „Umgebungsvariable gilt“ über dem Gastkonto-Schalter.
- [x] 36 Kostenansicht liest `source` nicht.
- [x] 37 Deutsche Hilfsnachrichten in Nutzerrolle steuern die Antwortsprache.
- [x] 38 Betriebsdoku nennt das automatische Löschen nicht.

### NIT und vorbestehend

- [x] NITs (Liste im Review-Bericht): Snapshots-Knopf, Preis-Hinweis, veraltete Kommentare,
      Doku-Abweichungen, Kleinkram, Dateigrößen.
- [x] V1 `is_affirmation`: „Do not proceed“, „Bestätigung verweigert“ (mit 4).
- [x] V2 `query_knowledge` vor Sperr-/Erlaubnisprüfung, `area` ungeprüft.
- [x] V3 `ChatRequest.session_id`/`page_context` ohne Längen-/Formprüfung (mit 2 und 14).
- [x] V4 ZIP-Bombe über markitdown (mit 6).
- [x] V5 YAML-Aliasse beim Wiederherstellen; ungültiges UTF-8 → 500.
- [x] V6 Inhalte der Wissensbasis ungerahmt im Prompt.
- [x] V7 `sessions.entities` überdauern die Gesprächsfrist.
- [x] V8 Sicherungs-Panels ohne Fokusführung.

## 2 Log

### 1 · b-api-openai + gpt-6-luna (CRITICAL)

- `llm.route`: `responses_api`-Modelle gehen jetzt auch bei `b-api-openai` über `openai/responses/`
  (`/openai/responses` der b-api); die AcademicCloud bekommt in `param_rules` die klassischen Regeln
  und bleibt auf `chat/completions` (Nutzer-Vorgabe 2026-09-26). Kommentar in `ParamRules` angepasst.
- Tests zuerst rot: `test_llm.py` (b-api → Responses, AcademicCloud bleibt, Doppel-Schlüssel),
  `test_llm_kennlinie.py` (Fang-Server: Pfad `/openai/responses`, `reasoning`/`text` im Body,
  `X-API-KEY` und Bearer kommen an; AcademicCloud auf `/academiccloud/chat/completions`),
  `test_llm_responses.py` (Responses-Fälle für beide OpenAI-Wege). Zwei Tests des alten Verhaltens
  (stille Umleitung bei gpt-5.6 hinter der b-api) sind durch die neuen ersetzt.
- Probe Staging-B-API, Weg der App, je ein Aufruf: `chat_completion` mit Werkzeug → Werkzeugaufruf;
  `_stream_completion` mit `respond_to_user` → gestreamt, Werkzeug rekonstruiert.

### 2, 3, 9 · Endmarken und Schattenfassung (CRITICAL, MAJOR)

- `domain/untrusted_text.py`: Die Lesart wird je VERSCHIEDENEM Zeichen gerechnet (`_lesarten`), die
  Schattenfassung per `"".join(map(tabelle.get, text, text))` gebaut — `str.translate` ist mit
  mehrzeichigen Lesarten selbst langsam (300 000 × U+FDFA: 2,9 s gegen 0,05 s, gemessen). Die Lage
  im Original (`bisect` über aufsummierte Längen) nur, wenn es einen Treffer gibt und Längen sich
  ändern. Gemessen: 300 000 × U+FDFA samt Marken 0,10 s (vorher 1,9 s), 200 000 verschiedene Zeichen
  0,22 s, 200 000 Zeichen Deutsch 2 ms.
- Trenner ungedeckelt ohne Klammern, possessiv: `(?:[^\w\[\]]|_)*+` — linear, weil jede Klammer
  nur bis zur nächsten prüft. Die Marke kommt aus der benannten Gruppe (`m.lastgroup`), nicht aus dem
  Text: „SEİTENKONTEXT“ (U+0130) warf `KeyError`. Die Liste `_UNSICHTBAR` entfällt — alle Format-
  Zeichen (Cf) fallen in `_lesarten`.
- Tests zuerst rot (`test_untrusted_text.py`): türkisches I, sechs gepolsterte Marken, Klammern im
  Fließtext bleiben, drei Laufzeitfälle (U+FDFA, weiche Trennung, 20 000 CJK-Zeichen).

### 2 (Eingang), 14, V3 · Sitzungskennung und Seitenkontext am Eingang

- `ChatRequest.session_id` folgt `schemas.SITZUNGSKENNUNG` (`[A-Za-z0-9_-]{1,128}`) — dieselbe Form
  wie an der offenen Lesestelle; dort jetzt `fullmatch` (vorher ließ `$` einen Zeilenumbruch am Ende
  durch, Test `abc%0A`). Die Lease `__lauf:aufbewahrung` liegt damit außerhalb aller Chat-Kennungen
  (Test in `test_aufbewahrung_takt.py`).
- `domain/seitenkontext_eingang.py` (neu, zuerst unter `api/`): `Environment.page_context` wird am Eingang gedeckelt, nicht
  abgewiesen — Texte 500 Zeichen, `page_url` 2 048, `page_text` Budget + 1 (EK10b bleibt; `_trim_text`
  zeigt das Kürzen weiter mit „…“), Listen und Objekte 50 Einträge, Tiefe 2.
- Tests zuerst rot: `test_schemas.py` (echte Kennungen gehen durch, sieben falsche nicht; Deckel;
  gewöhnlicher Seitenkontext bleibt wortgleich), `test_sessions_router.py` (`abc%0A`).

### 4, V1 · Ablehnungen sind keine Zustimmung (MAJOR)

- `domain/write_confirm.py`: `_VORBEHALT` um Verneinen und Aufschieben ergänzt (`not`, `don`, `never`,
  `nie`, `noch`, `später` …), dazu `_ABLEHNUNG` als Wortanfänge, weil sie sich beugen (`verweiger`,
  `abgelehn`, `widerruf`, `fehl`, `storn`, `aussteh`, `deny`, `reject`, `refus` …).
- **Nicht übernommen:** „das Substantiv ‚Freigabe‘ nur mit positivem Marker“. Ein vorhandener Test
  hält die Nutzer-Entscheidung K1 fest („Freigabe!“ allein ist Zustimmung); die Ablehnungen aus dem
  Review fängt der Vorbehalt.
- Test zuerst rot: 18 Sätze (`test_eine_ablehnung_ist_keine_zustimmung`), die bisherigen
  Zustimmungen bleiben grün (184 Tests in vier Modulen).

### 12 · Krisen-Wendungen nur mit Selbstbezug (MAJOR)

- `services/safety/krisen_wendungen.py`: „nie wieder aufwachen“ nur mit „ich will/möchte/würde/
  wünsche …“, als „aufwache“ oder als Zweck („damit man …“); „Schluss machen, endgültig“ nur mit
  „ich will/werde/mache …“ direkt davor; „mit dem Leben Schluss“ nur mit „ich …“ oder „meinem“.
  Abschiede (Verabschiedung, Abschiedsbrief) zählen nur ohne Anlass in derselben Nachricht
  (`_ANLASS`: Ruhestand, Rente, Kolleg…, Team, Ferien, Urlaub …).
- Test zuerst rot: acht Gegenproben (Werther, Rauchen, Ruhestand, Abschiedsbrief für die Kollegen,
  Dornröschen, Narkose, Sommerferien) und drei neue Andeutungen; alle 28 gemessenen bleiben erkannt.

### 5, 32, V5 · Schutz und Kennungen beim Wiederherstellen

- `api/config_kennungen.py` (neu): eine Regel für Studio, Löschen und Wiederherstellen — Hilfen aus
  `config_documents` dorthin verschoben, `pruefe_kennung` nutzt jetzt `kennungs_einwand` (keine
  zweite Kopie der Regeln). `loeschbar`: weder fester Bereich noch Sicherheitsmuster (M01/M02,
  `crisis_pattern`/`threat_pattern` des gelebten UND des wiederhergestellten Stands).
- `config_snapshots._apply_config`: „exakt“ löscht nur `loeschbar`e Bereiche; die Kennungen der
  Sicherung werden gegen den entstehenden Stand geprüft (400, nichts geschrieben).
- Gestrichene Bereiche (`domain/config_models.GESTRICHENE_BEREICHE`: create-/edit-triggers) lässt
  `is_restorable_area_key` nicht mehr zu — keine alte Sicherung legt sie wieder an.
- V5: `snapshots.parse_config_zip` liest ohne YAML-Aliasse (`seed_io.lade_ohne_alias`, auch im
  Frontmatter) und meldet kein UTF-8/kaputtes YAML/Aliasse als `SicherungUngueltig` → 400
  `snapshots.invalidFile` (de/en) statt 500. Der Seed-Import im Bild bleibt beim gewohnten Lader.
- Tests zuerst rot: `test_config_kennungen.py` (9, ohne Datenbank), drei Endpunkt-Tests mit Datenbank,
  vier Fälle in `test_snapshots_service.py`.

### 8 · Moderation unter Last (MAJOR)

- `services/llm_parallel.py`: eigene Plätze der Moderation (`MODERATION_PARALLEL` = 4,
  `moderations_semaphore()`), nicht mehr am Anbieter-Deckel — dort wartete sie hinter Antwort-Strömen,
  bis ihre 8-s-Frist ablief. Hinter der b-api kann sie den Deckel um höchstens vier überschreiten; ein
  429 lässt dann diese eine Prüfung aus, nicht alle (Begründung im Modulkopf). Das ersetzt die
  Entscheidung aus Paket 7 (L5), die Moderation an den Deckel zu stellen.
- `services/safety/moderation.py`: Frist nur auf dem Aufruf; das Log nennt die Art
  („moderation skipped, message passes unchecked: TimeoutError: …“) statt „moderation failed: “.
- Tests zuerst rot (`test_safety_stages.py`): Platz am Anbieter belegt → Moderation läuft; höchstens
  `MODERATION_PARALLEL` zugleich; der Grund steht im Log. Der Test des alten Designs ist ersetzt.

### 11, 34 · Verborgene und gesperrte Werkzeuge auf allen Wegen (MAJOR, MINOR)

- Agent-Vorabruf: `agent_tools.angebotene_mcp_werkzeuge` (aus `build_agent_tools` gelöst, derselbe
  Filter); `respond_agent._vorab_aufrufe` holt `get_skill_registry` nur, wenn der Lauf es angeboten
  bekommt.
- Muster-Weg: `respond.py` bildet `gesperrt` = Sicherheits-Sperre + verborgene Werkzeuge und nutzt es
  für den spekulativen Vorabruf, seine Extras und die Werkzeugschleife.
- Medientyp-Zweig (`response_tool_selection`): die Inhaltssuche ersetzt nur, was er gestrichen hat
  (34: keine Suche mehr für M01, M03, M04, M11, M15), und kommt aus dem nennbaren Katalog
  (`_nameable_tools`, ohne verborgene) statt aus `TOOL_DEFINITIONS`.
- Offene Schreibvorgänge: `write_approval._nicht_einloesbar` — ohne Schreibrecht, Werkzeug verborgen
  oder Einbettung nur lesend → verworfen, auch in der Datenbank.
- Tests zuerst rot: `test_respond_agent.py` (verborgen/gesperrt → kein Vorabruf),
  `test_respond_node.py` (verborgen → spekulativ verworfen, in `blocked_tools`),
  `test_response_tool_selection.py` (drei Fälle), `test_write_approval.py` (verborgen, nur lesen).
- Nebenbei: Die Eingangsgrenzen des Seitenkontexts liegen jetzt in `domain/seitenkontext_eingang.py`
  (samt `TEXT_PROMPT_BUDGET`; `page_context` liest sie dort) — aus `api/` bildeten sie einen
  Importkreis über den MCP-Client.

### 10 · Klassifikator: Systemteil ohne Seite und Zug (MAJOR)

- `services/classify_prompt.py`: `build_classify_system_prompt()` ist rein statisch (plus ein Satz zum
  Turn-Kontext); `build_classify_turn_context(...)` liefert State, Entities, Persona, Turn, Gerät und
  Canvas — die Entities ohne die Werte der Seite (`domain/seitenkontext_eingang.SEITEN_ENTITIES`,
  dieselbe Liste kopiert `page_context_enrich`).
- `services/classify.py`: Kette = Systemteil, gerahmte Seite (jetzt mit „Seitenkontext (Rohdaten)“:
  Pfad, Seitenart, Kennungen, Suchbegriff — `klassifikator_rohdaten`, über `seiten_daten(rohdaten=…)`),
  Verlauf, Turn-Kontext, Frage. Systemteil, Seite und Verlauf bleiben ein Präfix, das der Cache trifft.
- Tests: `test_classify_prompt.py` (statischer Systemteil; Turn-Kontext ohne Seitenwerte; zwei Seiten
  und zwei Züge ergeben denselben Systemtext), `test_classify.py` (Reihenfolge; Rohdaten gerahmt, eine
  Endmarke entschärft).

### 7 · Die vorbereitete Änderung aus dem Verlauf (MAJOR)

- `domain/prepared_write.py`: `VERLAUF_SCHLUESSEL` (`debug._prepared_write`) und `fuer_den_verlauf`.
- `services/turn_persist.py`: die Anfrage wird VOR dem ersten Speichern ermittelt und steht schon dort
  (ein Abruf zwischen den beiden Schreibvorgängen fände sie sonst nicht); `write_approval._persist`
  speichert sie beim Einlösen mit.
- Widget `shell/antwort-aus-verlauf.ts`: `antwortAusVerlaufHolen` gibt sie als `prepared_write` zurück
  (Form geprüft; was die Seite absetzen darf, prüft die Erlaubnisliste beim Ausführen, E4). Die
  Wiederherstellung beim Laden (`history-restore.ts`) liest den Eintrag nicht — die Änderung liefe
  sonst erneut.
- Tests zuerst rot (Backend 2, Widget 1 — Rot im Widget nachträglich durch Herausnehmen der Zeile
  belegt), dazu eine Gegenprobe für verbogene Einträge.

### 6, V4 · Umwandlung im eigenen Prozess (MAJOR)

- `services/rag/umwandeln_kind.py` (neu): ein Kindprozess je Umwandlung (`spawn`), einer zugleich je
  Prozess; nach `RAG_UMWANDLUNG_FRIST_S` (120) beendet. Unter Linux `RLIMIT_DATA`
  (`RAG_UMWANDLUNG_MAX_MB`, 1024, 0 = aus) und `oom_score_adj` 1000 — wird der Speicher knapp, nimmt
  der Kernel den Kindprozess, nicht den Chat. Vorprüfung im Kind: ZIP-Container (DOCX, PPTX, XLSX,
  EPUB, ZIP) nach entpackter Größe (200 MB) und Einträgen (5 000), PDF nach Seiten (1 000, `/Count`
  des Seitenbaums).
- `services/rag/umwandeln.py`: synchroner Kern `wandle_datei`/`wandle_rumpf` (Logik wie bisher, dazu
  die Vorprüfung), die asynchronen Hüllen nehmen einen Ausführer (Vorgabe Kindprozess; die Tests der
  Logik laufen im eigenen Prozess). `umwandeln_fehler.py` trägt Fehlertyp und Einordnung.
- Router: vier neue Arten mit Satz de/en (`ingest.unpackedTooLarge`, `tooManyPages`,
  `convertTooSlow`, `convertTooBig`). Deploy: beide Schalter in `compose.prod.yml` und `.env.example`.
- **Nicht übernommen:** eine eigene, kleinere Upload-Grenze für Office und PDF. Mit Trennung,
  Speicher- und Seitengrenze schützte sie nichts mehr, sie wiese nur gültige Dateien früher ab.
- Gemessen: markitdown laden kostet im Kindprozess rund 1,7 s je Umwandlung.
- Tests: `test_rag_umwandeln_kind.py` (8: Vorprüfung ZIP/Einträge/PDF, Frist beendet den Prozess,
  Fehler im Kind, echte Umwandlung, einer zugleich); die Format-Tests (Word, PDF, PowerPoint, Excel)
  laufen jetzt über den Kindprozess.

### V2 · `query_knowledge` nur in angebotenen Bereichen

- `tool_loop`: gesperrt (`blocked_tools`) → abgewiesen; der Bereich muss im `enum` des angebotenen
  Werkzeugs stehen (`response_tool_selection.wissensbereiche`). Die bewusste Ausnahme aus Paket 4 (A2)
  bleibt: ohne Angebot ist es rufbar, dann aber nur in den konfigurierten Bereichen (`rag_bereiche`
  = Schlüssel der RAG-Konfiguration, von `generate` gereicht), nicht in jedem der Datenbank.
- Tests zuerst rot: nicht angebotener Bereich, Sperre; der A2-Test prüft jetzt auch die Grenze.

### MINOR, Backend (15, 19, 21, 27–31, 33, 37)

- **15** `aufbewahrung._tage` liest die Frist über das Modell (`"30"` → 30, fehlendes Feld → Vorgabe des
  Modells); `_Tage` weist Wahrheitswerte ab (lax gelesen wäre `true` ein Tag). Modellvorgaben wie im
  Auslieferungsstand: Sicherheit 90, Qualität 180 (Gespräche 30). Studio-Fixture neu erzeugt.
- **19** Migration `0010_gespraeche_nach_alter`: `idx_messages_created`, `idx_memory_created`
  (`IF NOT EXISTS`); Test in `test_db_migration.py` (Rot ohne die Migration belegt).
- **21** `mcp_herkunft` aus Host und Port statt `netloc` (keine Zugangsdaten im Widget-Bündel, IPv6 in
  Klammern, ungültiger Port → leer). IPv6-Literale und Unterstriche kennt die Host-Grammatik der CSP
  nicht — die Quelle fällt weiter weg, aber `studio_csp` warnt jetzt beim Start.
- **27** `schreiben_erlaubt`: das Gastkonto nur mit dem Block der Anlage
  (`auth.handelt_mit_dem_block_der_anlage`) — ein anonymer Zug-Block ging ihm vor.
- **28, 30** `api/chat._fehlerblase` für beide Wege: der Strom speichert die Blase jetzt auch (der
  Nachläufer hinterließ eine Frage ohne Antwort), und am POST wird ein Fehler der Sperre selbst zur Blase
  statt 500 (Rollback vor dem Speichern, Hintergrund-Pings stumm wie bisher).
- **29** `sse.nachlaeufer_abwarten` (höchstens 25 s, `stop_grace_period` 40 s) im Lebenszyklus vor dem
  Aufräumen; was dann noch läuft, wird mit Warnung abgebrochen.
- **31** Die Studio-Proxy-Middleware merkt sich den Weg im Scope (`studio_proxy.ueber_studio`); der
  Agent-Endpunkt bucht Probeläufe als `studio-probe` (`session_origin.STUDIO_QUELLE`), und der
  Produktionsfilter der Kosten (`scope_clause(..., quelle)`) schließt sie aus. Der Studio-Schlüssel
  allein taugt nicht als Merkmal: Server-zu-Server-Aufrufer nutzen ihn auch.
- **33** `RagAbruf` streng (`"20"`, `20.0`, `True`, `"0.5"` → 422), der Leser weist Wahrheitswerte ab.
- **37** `prompt_language.SPRACHE_DER_PERSON` am Ende der drei eigenen Hinweise in Nutzerrolle
  (Abschlussbitte des Agenten, Korrektur der Werkzeugschleife, Zusammenfassung am Iterationsdeckel).
- Vertrag: `ChatRequest.session_id` trägt jetzt ein `pattern` — in `bewusste-vertragszusaetze.md`
  eingetragen, dazu die NITs dort (Retention-Zeile, `connected`/`session_busy`, Token-Streaming an).

### V6, V7, 20, 38 · Wissensbasis gerahmt, Gesprächsstand, Betriebsdoku

- **V6** `untrusted_text.frame_wissen` (eigener Rahmen „aus der Wissensbasis“, Endmarke wie beim
  WLO-Bestand): Vorabruf im Muster-Weg (der Vermerk „Bereits durchsuchte Bereiche“ bleibt außerhalb),
  `query_knowledge` (Fehlanzeige bleibt ungerahmt), `wissen_suchen` (Rahmen zählt in `MAX_ZEICHEN`).
- **V7** `aufbewahrung`: neuer Bereich `session_state` — Entities, Signale und Tour-Stand einer Sitzung,
  die länger als die Frist der Verläufe ruht (`updated_at`), werden in Stapeln geleert; Sitzung und
  Kosten bleiben. Überblick und Lauf zählen ihn mit. Entscheidung im Sinn der 30-Tage-Frist, umkehrbar
  (`entscheidungen-offen.md`).
- **20** als offene Entscheidung mit Empfehlung (a) in `entscheidungen-offen.md`, beschrieben in
  `deploy/README.md`.
- **38** `deploy/README.md` „Was der Server von selbst löscht“ (Fristen, Sitzungen bleiben, Sicherungen
  halten Gelöschtes bis `BACKUP_KEEP_DAYS`), Verweis im Schnellstart.

### 22–26 · Widget: Druckfenster und Verlaufsnachfrage

- **22** `print-fenster`: Timer und `print` sind die des Druckfensters (`w.setTimeout`, `w.print`),
  nicht die der öffnenden Seite — navigiert sie weiter, druckt das Fenster trotzdem, und der Knopf
  bleibt lebendig. Zwei Tests (Uhr des Fensters, Knopf ruft `w.print`).
- **23** `antwortAusVerlauf` zählt die Uhr (`max(Pausen, jetzt − Start)`), nicht nur die Pausen; jeder
  Abruf hat eine eigene Frist (`ABRUF_FRIST_MS` 15 s, eigener `AbortController`).
- **24** Nach jedem Abruf (auch im Fehlerzweig) wird geprüft, ob der Zug noch zählt; die Shell hält je
  Nachfrage einen `AbortController` und bricht alle in `ngOnDestroy` ab — der laufende `fetch` endet
  mit, eine späte Antwort erreicht `_onResult` nicht mehr.
- **25** Nur eine getippte Frage (gesendet aus dem Feld, ohne Aktion) kehrt bei „beschäftigt“ ins
  Eingabefeld zurück — kein Chip, kein Auftrag der Gastseite (der stünde sonst ungekürzt da). Der
  bestehende C-6-Test lief über den Chip-Weg und prüft jetzt den getippten.
- **26** CORS gibt `Retry-After` frei (`expose_headers`, Test in `test_security_headers.py`);
  `Retry-After: 0` heißt „sofort“ (ein fehlender Kopf bleibt „fehlt“); ein langer Wert wartet bis zum
  Ende der Frist und fragt dann noch einmal, statt sofort aufzugeben.

### 13, 16–18, 31, 35, 36, V7, V8 · Studio

- **13** `retention.lead` (de/en) nennt beide Wege, auf denen Sitzungen samt Verbrauch verschwinden
  („Sessions“ einzeln, „Gespräche löschen“ gesammelt), und den geleerten Gesprächsstand (V7).
- **16** „Bereinigen …“ zählt neu (`overview.reload()`); bis die Zahl da ist, steht „werden gezählt“
  und „Jetzt bereinigen“ ist gesperrt. Die Rückfrage nennt die Zahl je Bereich (`retention.confirm`
  mit `{list}`), sagt „gerade nichts fällig“ oder fällt bei einer gescheiterten Zählung auf den
  allgemeinen Satz zurück.
- **17** Kein Fokus und kein Neuladen mehr in einer zerstörten Ansicht (NG0911 mit dem alten Code per
  Wegwerf-Spec belegt). Dieselbe Falle saß in `privacy-purge` (Nebenfund, gleiche Ursache) — behoben.
- **18** Das Panel nutzt `AsyncData` (Generationsschutz, Fehlertext folgt dem Sprachwechsel).
- **V7 (Studio)** `RetentionLog` und `LOG_ORDER` kennen `session_state`, de/en-Texte für Zeile und
  Zählung.
- **Nebenfund** `_Tage` aus #15 schrieb `"ge": 0` statt `"minimum": 0` ins Schema (Grenze hinter dem
  `BeforeValidator`) — das Studio kannte die Untergrenze nicht, die Fixture übersetzte nicht mehr.
  Reihenfolge getauscht, Wächter `test_keine_grenze_bleibt_als_rohes_stichwort_im_schema` über alle
  Bereichs-Schemas, Fixture neu erzeugt.
- **35** Der Abschnittshinweis „Betrieb“ verspricht den Vorrang nur noch Schaltern, die unter
  „Umgebung:“ eine Variable nennen; das Gastkonto sagt „keine Umgebungsvariable“ (Test in
  `fields.spec.ts`).
- **31, 36** Kostenansicht: Zeilen ohne Sitzung heißen nach `source` („Agent-API“ oder „Studio:
  „Auftrag testen““), der Listenschlüssel trägt die Quelle (zwei Zeilen ohne Sitzung teilten sich
  sonst einen). Produktionsfilter-Text und `origin-scope.ts` nennen die Probeläufe des Studios.
- **V8** Neuer Helfer `core/inject-focus.ts` (Fokus nach dem Rendern, Rückfallkette, nichts in
  zerstörten Ansichten) — genutzt von Aufbewahrung, „Gespräche löschen“ und den vier
  Sicherungs-Panels: Rückfrage → „Abbrechen“, danach zurück auf den auslösenden Knopf; fehlt er
  (gelöschte Zeile) oder ist er gesperrt (nichts mehr abzugleichen), die Panel-Überschrift
  (`tabindex="-1"`). Eine neue Datei schließt die Rückfrage, ohne den Fokus aus der Dateiwahl zu
  ziehen.
- **Nebenfund** Snapshot- und Auslieferungsstand-Panel trugen beide `id="sp-title"` auf derselben Seite
  — das `aria-labelledby` des zweiten benannte es falsch. Jetzt `seed-title`; Wächter-Test „keine
  Kennung doppelt“ auf der Sicherungsseite.
- **NIT** „Ja, wiederherstellen“ (Snapshots) ist bei „exakt“ als gefährlich markiert.

### NITs

- **Snapshots** „Ja, wiederherstellen“ ist bei „exakt“ als gefährlich markiert (Studio-Block oben).
- **Preis-Hinweis** des generativen Laufs nur noch mit Betrag (`priced`, `priceBand`); ohne Preis
  widersprach „Schätzung … bepreist nach der Preistafel“ dem Satz „Keine Kostenschätzung“.
- **Veraltete Kommentare** nachgezogen: `curated-pages-betrieb` (drei Fristen), `area_effects`
  (Löschlauf liest `retention_days`), `config_loader/engine` (auch die Betriebsschalter),
  `classify`/`classify_prompt` (Nachrichtenfolge seit #10), `seitenkontext_prompt` („Wirft nicht“ mit
  Begründung), `werkzeug_freigabe` („kein Pfad“ gilt seit #11), `sse` (Verhalten seit Paket 7),
  `session_locks` (Endpunkt nutzt `sitzung_sperren`, `_spawn_background` in `obs/tasks`),
  `compose.prod.yml` und die Skizze in `architektur.md` (Sperre über alle Repliken, Vorgabe 1).
- **Doku**: Befundliste (Schnellstart setzt das Modell ausdrücklich; beide Protokolle halten 500
  Zeichen, das Sicherheitsprotokoll auch die IP — ebenso in `deploy/README.md`), `evals/README`
  (keine Zählung mehr, die Listen haben je 28 Sätze), M10 („alle Bereiche“ — der Seed hat acht;
  geparste Daten unverändert, also keine Abweichung im Auslieferungsstand).
- **Englisch im Satz**: `UnsafeUrlError` trägt `grund`/`host`; Import, MCP-Erkundung und MCP-Speichern
  bilden den Satz in der Sprache des Studios (`url.notAllowed`, `url.unknownHost`,
  `config_guards.url_einwand`). Ein unbekannter Name ist kein „nicht erlaubt“ mehr. Technische
  Details in Klammern (`ingest.convertFailed`, `ingest.fetchFailed`) bleiben roh — eine beliebige
  Ausnahme lässt sich nicht übersetzen.
- **`mess_responses_cache`**: ohne Mitschnitt an `/responses` ein klarer Abbruch (Rückgabe 2) statt
  `IndexError`.
- **Handschlag** liest nur noch `max(id)` (`db_sessions.last_message_id`, Index `messages(session_id,
  id)`) statt der ganzen letzten Nachricht; pg-Test.
- **`session_busy`** steht auf INFO statt WARNING (erwartbar); andere Fehlerergebnisse bleiben WARNING.
- **`gruss_vermerk`**: die Einträge einer Seite werden je Sprache gebildet statt am Trenner zerlegt —
  „|lang:“ in Adresse oder Suchbegriff ließ den Eintrag der alten Sprache stehen
  (`tests/test_gruss_vermerk.py`).
- **Prompt-Vorschau** zählt die Werkzeuge wie für eine Person ohne Anmeldung (`schreiben_erlaubt`),
  und das Studio sagt es dazu.
- **`runSendMessage`** in Wege zerlegt (`antwortHolen`, `nachStromFehler`, `ausDemVerlauf`,
  `perPost`, `hinweis`), verhaltensgleich; **„veraltet“** legt die getippte Frage zurück wie
  „beschäftigt“; im Stream-Client geht ein **erhaltener Fehlerrahmen** einem Abbruch danach vor.
- **Dateigrößen**: `write_confirm.py` 477 → 340 (Zustimmung → `domain/zustimmung.py`, Anzeige →
  `domain/write_anzeige.py`), `respond_agent.py` 542 → 445 (Abschluss → `services/agent_abschluss.py`,
  Vorabruf-Planung → `agent_prefetch.vorab_aufrufe`), `print-utils.ts` 397 → 258 (Lernpfad →
  `print-lernpfad.ts`). **Nicht geteilt, mit Grund:** `write_approval.py` (412) ist eine
  Verantwortung — Verwerfen und Einlösen derselben Abnahme —, und sein Kopf legt die Außenkanten für
  die Tests bewusst auf dieses Modul; die Länge ist Dokumentation. `response_prompt_builder.py` (324)
  baut den Systemteil in ALT-Byte-Treue; `_tools_layer` hätte nur in das schon 338 Zeilen lange
  `response_prompt_tools_text` gepasst. Der Rest von `respond_agent` ist die eine Knotenfunktion —
  vorbestehende Strukturschuld wie im Audit (F-8, Nutzer: nach dem Cutover).
- **Nebenfund** `print-gates.spec`: die Fenster-Attrappe kannte nach #22 weder `setTimeout` noch
  `print` — vier Tests waren rot, bis die Attrappe hatte, was jedes Fenster hat.

