# Fehlerprotokoll — Code-Audit boerdi-chat (Backend + Widget)

**Datum:** 2026-10-10 · **Modus:** nur lesend (kein Code geändert, keine Tests ausgeführt)
**Tiefe:** Standard+ (alle Bereiche überflogen, Hochrisiko-Module zeilenweise: Auth/Studio-Proxy,
Chat-Endpunkt/SSE, Sitzungssperre, Zug-Graph, MCP-Client/Cache, RAG-Retrieval, Safety-Normalisierung,
Widget-Markdown/Stream/Session/OAuth). Vorgänger: [`2026-09-29-audit.md`](2026-09-29-audit.md),
[`2026-10-03-audit-extern.md`](2026-10-03-audit-extern.md). Bereits bekannte Punkte aus
[`../offene-befunde-und-todo.md`](../offene-befunde-und-todo.md) sind mit **(bekannt)** markiert.

**Umfang:** Backend `src` ≈ 56 k Zeilen (332 Dateien), Widget + `ui`-Lib ≈ 24 k Zeilen TS,
Studio ≈ 53 k Zeilen (nur Sicherheits-Grep). Altsystem und MCP-Server nicht im Umfang.

**Scanner:** `ruff check` (Projektregeln) sauber; erweiterte Regeln (`B,ASYNC,S,PERF,BLE`) liefern
≈ 270 Treffer — überwiegend `BLE001` (bewusste breite `except`, 207×), 27× `S608` in
`quality_analytics.py`/`config_store.py`/`eval/queries.py` (f-String-SQL; Interpolation nur aus
Code-Konstanten, kein Request-Wert gefunden → kein Befund, aber Wartungsrisiko, siehe L-6),
10× `S110` (`try/except/pass`). `pip-audit`/`npm audit`/Testsuite wurden **nicht** ausgeführt
(laufen in der CI).

**Legende:** Schwere *Hoch / Mittel / Niedrig* · **[verifiziert]** = an der Quelle nachgelesen ·
**[zu verifizieren]** = plausibel, braucht Messung/Laufzeitprüfung.

---

## Bewertung je Dimension (0–10)

| Dimension | Note | Kurzbegründung |
|---|---|---|
| Architektur | 7 | Klarer Graph, ContextVars statt Globals; einzelne Riesen-Dateien (300-Z.-Regel) |
| Sicherheit | 6 | Gates fail-closed, DOMPurify; aber `bsid`-Übernahme, kein CSRF-Zweitschutz, Bilder/`rel` |
| Logik/Korrektheit | 7 | Viele Kantenfälle bewusst behandelt; Rollback-Lücken, Meta-Cache, Startauftrag |
| Datenbank | 7 | Indizes passend, Lease-Lock solide; HNSW-Filter, Pool nicht konfigurierbar |
| Performance | 6 | Gute Parallelisierung in `assess`; serielle MCP-/RAG-Aufrufe, kein Keep-alive |
| API | 8 | Konsistente Router-Guards, Rumpf-Grenze, SSE robust |
| Frontend | 6 | Saubere Komponenten; a11y-Ansagen, Fokus, Popup-Blocker, Aufräumen |
| Tests | 6 | Backend/ui/studio stark; Widget-Projekt dünn, Golden-Flows manuell |
| Wartbarkeit | 6 | Sehr gut kommentiert; 1000-Zeilen-Dateien, 207 breite `except` |
| Abhängigkeiten | 8 | Lizenz- und Audit-Gate in CI |
| Dokumentation | 8 | Ausführlich; kleine Drift (Angular-Version) |
| Deployment | 8 | Non-root, Healthcheck, Graceful Shutdown; Docker-Socket am traefik (bekannt) |
| **Gesamt** | **≈ 69/100** | (Vorgänger-Audit 2026-09-29: 64/100) |

---

## Übersicht

| # | Schwere | Bereich | Titel |
|---|---|---|---|
| H-1 | Hoch | Widget/Datenschutz | Sitzungsübernahme über `?bsid=` + offener Verlaufs-Endpunkt |
| H-2 | Hoch | Widget | Startauftrag der Gastseite wird beim Laden still verworfen |
| H-3 | Hoch | Widget | OAuth-Anmeldefenster erst nach drei `await` → Popup-Blocker |
| M-1 | Mittel | Backend/DB | Geschluckte Commit-Fehler ohne `rollback()` auf frühen Ausgängen |
| M-2 | Mittel | Studio/Security | Kein Origin-/Fetch-Metadata-Check am cookie-gesicherten Studio-Proxy |
| M-3 | Mittel | RAG | HNSW-Index + Bereichsfilter kann Treffer kleiner Bereiche verlieren |
| M-4 | Mittel | MCP-Cache | Meta-Cache liefert veraltete Filter-Metas nach TTL-Ablauf |
| M-5 | Mittel | Latenz/Robustheit | Klassifikator ohne enge Frist auf dem kritischen Pfad |
| M-6 | Mittel | Widget/Security | `rel`/`target` aus Modelltext werden nicht erzwungen (Tabnabbing) |
| M-7 | Mittel | Widget/Datenschutz | Externe Bilder im Bot-Markdown erlaubt (Tracking-Pixel) |
| M-8 | Mittel | DB/Betrieb | DB-Pool nicht konfigurierbar (5+10 je Replik) |
| M-9 | Mittel | Tests | Widget-Projekt kaum unit-getestet |
| L-1 … L-13 | Niedrig | diverse | siehe unten |

---

## Hoch

### H-1 Sitzungsübernahme über `?bsid=` (Session-Fixation) — [verifiziert, Ausnutzbarkeit zu verifizieren]
- **Ort:** [`session-id.ts:47-58`](../../frontend/projects/ui/src/session/session-id.ts#L47-L58),
  [`sessions.py:257-272`](../../backend/src/boerdi/api/sessions.py#L257-L272) (öffentlich, ohne Auth).
- **Problem:** Jede formal gültige `bsid` aus der URL wird ohne weitere Prüfung übernommen
  und in localStorage/Cookie geschrieben (Stufe A hat Vorrang vor Cookie und localStorage). Der Verlauf
  einer Sitzung ist über `GET /api/sessions/{id}/messages` für jeden lesbar, der die ID kennt (bewusst, ALT-Parität).
- **Auswirkung:** Ein Angreifer verschickt einen Link `…?bsid=bb-<seine-id>` auf eine Seite mit
  Widget. Das Opfer chattet in der Sitzung des Angreifers weiter, und der Angreifer liest den Verlauf mit,
  womöglich personenbezogene Inhalte (DSGVO-relevant).
- **Fix:** Handoff nur über ein kurzlebiges, einmal verwendbares, serverseitig signiertes Ticket
  (z. B. 60 s, wird beim Einlösen verbraucht). Alternativ den Verlauf an ein zweites Geheimnis binden,
  das nie in der URL steht. Mindestens: eine fremde `bsid` nicht übernehmen, wenn lokal schon eine
  Sitzung mit Verlauf existiert.

### H-2 Startauftrag (`startTask` / `setHostInstruction trigger:'now'`) wird still verworfen — [verifiziert im Code, Reihenfolge zu verifizieren]
- **Ort:** [`widget.component.ts:432-445`](../../frontend/projects/widget/src/app/widget/widget.component.ts#L432-L445)
  → [`chat-shell.component.ts:489-499`](../../frontend/projects/ui/src/shell/chat-shell.component.ts#L489-L499)
  → [`send-message.ts:124-125`](../../frontend/projects/ui/src/shell/send-message.ts#L124-L125).
- **Problem:** `runSendMessage` kehrt bei `ctx.isLoading()` kommentarlos zurück. Beim Erstaufruf setzen
  Kontext-Ping bzw. Tour-Tick das Ladeflag synchron (`context-greeting.controller.ts:85`). Läuft der
  Effect, der den wartenden Auftrag abgibt, danach, geht der Auftrag verloren, und das Promise wird
  trotzdem normal erfüllt.
- **Auswirkung:** Einbettungen („leg mit dieser Sammlung los“) starten sporadisch nicht, und die Gastseite
  merkt es nicht.
- **Fix:** Aufträge in eine Warteschlange legen und nach Ende des Ladens abarbeiten. Zusätzlich eine Spec
  „Kontext-Ping läuft → `startTask` → Auftrag wird gesendet“.

### H-3 OAuth-Anmeldefenster nach mehreren `await` geöffnet — [verifiziert]
- **Ort:** [`mcp-oauth.ts:191-216`](../../frontend/projects/ui/src/session/mcp-oauth.ts#L191-L216).
- **Problem:** `window.open` steht erst hinter `await discoverEndpoints`, `await registerClient` und
  `await codeChallenge`. Bis dahin ist die Nutzergeste (transient activation) oft verbraucht. Der Kommentar in
  [`chat-shell.component.ts:452-456`](../../frontend/projects/ui/src/shell/chat-shell.component.ts#L452-L456)
  nimmt das Gegenteil an.
- **Auswirkung:** Vor allem in Safari/Firefox und bei langsamem Netz endet die Anmeldung in `popup-blocked`.
- **Fix:** Synchron im Klick `window.open('about:blank', …)` aufrufen, nach den `await`s
  `fenster.location.href = url` setzen und das Fenster bei einem Fehler schließen.

---

## Mittel

### M-1 Commit-Fehler geschluckt, Sitzung bleibt im Fehlerzustand — [verifiziert]
- **Ort:** [`tour.py:189-202`](../../backend/src/boerdi/graph/nodes/tour.py#L189-L202),
  [`context_greeting.py:446-457`](../../backend/src/boerdi/graph/nodes/context_greeting.py#L446-L457),
  [`preflight.py:164-170`](../../backend/src/boerdi/graph/nodes/preflight.py#L164-L170);
  `save_message`/`update_session` committen selbst ohne Rollback
  ([`db_sessions.py:85-139`](../../backend/src/boerdi/services/db_sessions.py#L85-L139)).
- **Problem:** Dieselbe F-1-Klasse, die in `_log_turn_safety` und `finalize_message` schon behoben ist. Der
  `except` loggt nur. Die geteilte `AsyncSession` bleibt in „needs rollback“, und jede weitere Nutzung
  im selben Request (zweites `save_message`, `_record_usage` in
  [`chat.py:113`](../../backend/src/boerdi/api/chat.py#L113)) scheitert mit `PendingRollbackError`.
- **Auswirkung:** Kostenbuchung und Verlaufszeilen gehen still verloren.
- **Fix:** In jedem dieser `except`-Zweige `await session.rollback()` (selbst wieder in `try`). Besser zentral:
  `save_message`/`update_session` rollen bei einem Fehler selbst zurück, wie `finalize_message`.

### M-2 Studio-Proxy ohne CSRF-Zweitschutz — [verifiziert; Ausnutzbarkeit zu verifizieren]
- **Ort:** [`studio_proxy.py:151-171`](../../backend/src/boerdi/api/studio_proxy.py#L151-L171),
  Cookie in [`studio_bff.py:72-80`](../../backend/src/boerdi/api/studio_bff.py#L72-L80).
- **Problem:** Der Proxy fügt bei gültigem Cookie den Admin-Schlüssel ein, prüft aber weder `Origin` noch
  `Sec-Fetch-Site`. Der Schutz hängt allein an `SameSite=Strict`. Das hilft nicht gegen Seiten derselben
  *Site*: Subdomains, `*.nip.io`, falls nip.io nicht auf der Public Suffix List steht (zu verifizieren),
  und Skripte auf demselben Origin (Demo-Seiten ohne CSP, bekannt §6).
- **Auswirkung:** Ein Multipart-POST ohne Preflight (Konfig-Restore, RAG-Upload) liefe mit Admin-Rechten.
- **Fix:** Für Methoden außer GET/HEAD/OPTIONS `Sec-Fetch-Site: same-origin` oder einen passenden
  `Origin` verlangen (sonst 403) und zusätzlich einen eigenen Header erzwingen, der einen Preflight auslöst.

### M-3 HNSW + `WHERE area = …` kann Treffer verlieren — [zu verifizieren]
- **Ort:** [`retrieval.py:132-146`](../../backend/src/boerdi/services/rag/retrieval.py#L132-L146),
  Index [`0001_schema.py:141-145`](../../backend/alembic/versions/0001_schema.py#L141-L145).
- **Problem:** Nimmt der Planer `idx_rag_embedding`, filtert pgvector **nach** dem Index-Scan
  (`hnsw.ef_search` Vorgabe 40). Bei kleinen Bereichen in großer Tabelle kommen weniger als `top_k` Zeilen
  zurück oder gar keine. Im Code ist weder `ef_search` noch `iterative_scan` gesetzt.
- **Auswirkung:** „Kein Wissen gefunden“, obwohl passende Abschnitte existieren; das wird mit wachsendem
  Bestand schlimmer.
- **Fix:** Erst `EXPLAIN ANALYZE` auf Produktivdaten. Dann ab pgvector 0.8 `SET LOCAL hnsw.iterative_scan =
  relaxed_order` bzw. `ef_search` erhöhen, oder Teil-Indizes je Bereich anlegen.

### M-4 MCP-Meta-Cache liefert veraltete Filter-Metas — [verifiziert]
- **Ort:** [`tool_cache.py:167-170`](../../backend/src/boerdi/services/mcp/tool_cache.py#L167-L170)
  (Ablauf entfernt nur `_TOOL_CACHE`), [`client.py:465-472`](../../backend/src/boerdi/services/mcp/client.py#L465-L472)
  (Metas werden nur bei nicht-leerem Ergebnis überschrieben).
- **Problem:** Nach dem TTL-Ablauf bleibt der alte Meta-Eintrag stehen. Liefert der neue Aufruf keine
  `_queryMeta`, gibt der nächste Cache-Treffer die alten Metas zur neuen Antwort aus.
- **Auswirkung:** Falsche Such-CTA-URL bzw. falsche Facetten-Chips.
- **Fix:** Wert und Metas in einem Tupel speichern, oder bei Ablauf und in `_cache_set` immer
  `_TOOL_META_CACHE.pop(key)` aufrufen.

### M-5 Klassifikator ohne enge Frist — [verifiziert]
- **Ort:** [`classify.py:116-124`](../../backend/src/boerdi/services/classify.py#L116-L124); Timeout
  kommt aus `llm_read_timeout` = 75 s ([`settings.py:118`](../../backend/src/boerdi/settings.py#L118)),
  dazu `max_retries=2` (instructor) plus SDK-Retries.
- **Problem:** Die Klassifikation blockiert jeden Zug (`assess`). Hängt der Anbieter, wartet der Zug im
  schlimmsten Fall mehrere Minuten, bevor `_salvage` bzw. die Vorgaben greifen. Das Widget gibt nach 100 s
  ohne benanntes Event auf ([`stream-client.ts:125-135`](../../frontend/projects/ui/src/stream/stream-client.ts#L125-L135)).
- **Fix:** `asyncio.timeout(...)` (z. B. 8–10 s, konfigurierbar) um `_acreate`; bei Ablauf
  Schema-Vorgaben bzw. die Heuristik nutzen und den Fall als Qualitäts-Event zählen.

### M-6 `rel`/`target` aus dem Modelltext nicht erzwungen — [verifiziert]
- **Ort:** [`markdown-renderer.ts:184-186`](../../frontend/projects/ui/src/markdown/markdown-renderer.ts#L184-L186),
  `ADD_ATTR: ['target','rel']` in Z. 156-159.
- **Problem:** `rel` wird nur gesetzt, wenn keines vorhanden ist. Ein vom Modell oder über Tool-Text
  eingeschleustes `rel="opener"` bleibt stehen. Bei vertrauenswürdigen Hosts bleibt ein mitgeliefertes
  `target="_blank"` ganz ohne `rel`.
- **Fix:** Sobald `target` gesetzt ist, `rel="noopener noreferrer"` immer erzwingen. Oder fremde
  `target`/`rel` verwerfen und selbst vergeben.

### M-7 Externe Bilder im Bot-Markdown — [verifiziert]
- **Ort:** [`markdown-renderer.ts:156-159`](../../frontend/projects/ui/src/markdown/markdown-renderer.ts#L156-L159).
- **Problem:** DOMPurify mit `html`-Profil lässt `<img src="https://…">` bzw. `![](…)` durch. Eine
  Prompt-Injection über MCP- oder Seitentext kann so Tracking-Pixel einschleusen.
- **Fix:** `FORBID_TAGS: ['img']` setzen oder Bilder per Hook nur von vertrauenswürdigen Hosts zulassen.

### M-8 DB-Pool nicht konfigurierbar — [verifiziert; Wirkung zu verifizieren]
- **Ort:** [`db/session.py:19-30`](../../backend/src/boerdi/db/session.py#L19-L30).
- **Problem:** `create_async_engine` läuft mit SQLAlchemy-Vorgaben (5 + 10 Overflow, 30 s Wartezeit). Ein
  Zug hält seine Session über die ganze Laufzeit, inklusive LLM-Aufrufe; die LLM-Parallelität liegt bei 20.
- **Auswirkung:** Ab etwa 15 parallelen Zügen je Replik warten weitere Züge auf eine Verbindung, und
  `TimeoutError` wird als Fehlerblase sichtbar.
- **Fix:** `DB_POOL_SIZE`/`DB_MAX_OVERFLOW`/`pool_pre_ping` als Settings; Lasttest mit 30 parallelen Zügen.

### M-9 Widget kaum unit-getestet — [verifiziert]
- **Ort:** `frontend/projects/widget` (4 Specs) gegenüber `ui` (79) und `studio` (120).
- **Auswirkung:** Befunde wie H-2 und H-3 (Reihenfolge, Nutzergeste) fallen im Test nicht auf.
- **Fix:** Specs für Start → Auftrag → Ping, Abbruch/Stale, `Retry-After` und OAuth (Fenster synchron).

---

## Niedrig

| # | Ort | Problem | Fix |
|---|---|---|---|
| L-1 | [`arg_resolvers.py:501-504`](../../backend/src/boerdi/services/mcp/arg_resolvers.py#L501-L504) | Ein vorübergehender LLM-Fehler beim Vokabular-Abgleich wird prozesslebenslang als „kein Treffer“ gecacht. | Im `except` nicht cachen. |
| L-2 | [`arg_resolvers.py:280`](../../backend/src/boerdi/services/mcp/arg_resolvers.py#L280) | Label→URI-Cache wird nur einmal pro Prozess geladen. | Ladezeitpunkt merken, nach TTL neu laden. |
| L-3 | [`retrieval.py:305-316`](../../backend/src/boerdi/services/rag/retrieval.py#L305-L316) | `get_always_on_rag_context` ignoriert `get_retrieval_settings` (min_score 0,25, kein Zeichendeckel); Nutzung zu prüfen. | Einstellungen nutzen oder Funktion löschen. |
| L-4 | [`body_limit.py:75`](../../backend/src/boerdi/api/body_limit.py#L75) | Grenze am rohen Pfad inkl. `root_path`; hinter einem Pfad-Präfix gälten 16 statt 2 MiB. Heute ohne Wirkung. | `_route_path` aus `studio_proxy` nutzen. |
| L-5 | [`ratelimit.py:37-46`](../../backend/src/boerdi/api/ratelimit.py#L37-L46) | Bei `TRUST_FORWARDED_FOR` gilt der **erste** XFF-Eintrag. Mit dem traefik-Standard (fremde `X-Forwarded-*` werden ersetzt) nicht ausnutzbar; mit einem CDN/Proxy davor, der Einträge anhängt, wären Login-Drossel und Chat-Limit umgehbar. | Rechten Eintrag minus N vertrauter Hops nehmen; in `deploy/README.md` festhalten. |
| L-6 | `quality_analytics.py` u. a. (27× `S608`) | SQL per f-String aus Konstanten; heute kein Request-Wert. | Gebundene Parameter / SQLAlchemy Core oder begründetes `noqa`. |
| L-7 | [`stream-client.ts:213-219`](../../frontend/projects/ui/src/stream/stream-client.ts#L213-L219) | Der SSE-Parser trennt nur an `\n\n`; ein Proxy mit `\r\n` bräche den Stream. Am Ende kein `decoder.decode()` zum Leeren. | `\r\n?` vorher zu `\n` normalisieren. |
| L-8 | `chat-shell.component.html:20,58-60,77` | Doppelte Screenreader-Ansagen (Phasenlabel im `role=log` plus Status). | Ladeblase `aria-hidden`, ein Statuskanal. |
| L-9 | `chat-shell.component.ts:571-573, 671-676` | `focusInput()` reißt den Fokus zurück (mobil öffnet sich die Tastatur); Enter sendet während der IME-Komposition. | Fokus nur zurückholen, wenn er im Widget lag; `isComposing` prüfen. |
| L-10 | `chat-shell.component.ts:866-871` | Beim Entfernen bleiben Timer, OAuth-Listener (bis 5 min) und der Stream (bis 100 s) aktiv. | Ein `AbortController` je Shell. |
| L-11 | `single-instance.ts:51-52` | MutationObserver mit `subtree:true` auf `body` ruft bei jeder Mutation `querySelectorAll` auf. | Entprellen oder nur in `connectedCallback` prüfen. |
| L-12 | [`respond.py:152-180`](../../backend/src/boerdi/graph/nodes/respond.py#L152-L180), Z. 294 | Bei `winner_id == "M16"` wird die spekulative Suche voll abgewartet und dann verworfen. | `M16` in `spec_blocked` aufnehmen. |
| L-13 | [`sitzungssperre.py`](../../backend/src/boerdi/services/sitzungssperre.py) | Bei Verlust der Lease (`rowcount==0`) wird nur geloggt; der Zug läuft weiter, und zwei Züge können parallel laufen (dokumentiert). | Zug-Abbruch-Signal setzen oder `persist` am Ende gegen die Lease prüfen. |

**Doku-/Konstitutions-Drift (Niedrig):**
- `CLAUDE.md` nennt „Angular-21-Webkomponente“; tatsächlich `@angular/core ^22.2.1`.
- Verstöße gegen die ≤300-Zeilen-Regel (bekannt, Todo §5): u. a. `tool_loop.py` (1066 Z.),
  `chat-shell.component.ts` (≈ 897 Z.).
- Verwaiste `evals/__pycache__/engine_matrix_metrics.cpython-312.pyc` ohne Quelldatei.
- Diagnose-Log „Kandidat für gather-Parallelisierung“ in
  [`tool_loop.py:366-386`](../../backend/src/boerdi/services/tool_loop.py#L366-L386): keine Auswertung, keine Entscheidung.
- 10× `try/except/pass` (`S110`), z. B. `respond.py:173`, `cards/links.py:59,66`: Fehler ohne
  jede Spur. Mindestens `logger.debug(..., exc_info=True)`.

**Bekannt und weiterhin offen:** festes HMAC-Cookie-Token ohne Ablauf (§6; zusätzlich ermöglicht ein
gestohlenes Cookie einen Offline-Wörterbuchangriff aufs Passwort, da ohne Salt/KDF), CORS standardmäßig
offen (§6), keine CSP für Demo-Seiten (§6), Docker-Socket am traefik, DNS-Rebinding-TOCTOU in
`url_safety.py`, persistierte Nutzernachricht vor der Drosselung (ALT-Parität), Verlauf per Session-ID
als Bearer.

---

## Ohne Befund geprüft
- Fail-closed Admin-/Studio-Gates, `compare_digest` mit ASCII-Guard; alle Admin-Router tragen
  `require_studio_key`/`require_agent_caller` auf Router-Ebene; Cookie-Flags korrekt.
- Rumpf-Grenze auch bei chunked; SSE (reservierter Endplatz, Disconnect, Nachläufer beim Shutdown);
  Sitzungssperre (Owner-Lease, Verlängerung, Freigabe nur des eigenen Eintrags).
- `assess`-`gather`: nur der Memory-Zweig nutzt die DB-Session.
- ContextVars für Request-Hints, Query-Metas, Prepared Writes und Zugangsblock (kein Übersprechen).
- MCP: Cache-Schlüssel mit Aufrufer-Fingerprint, Token nur an den primären Server, Schreib-Bestätigung
  an den Aufrufer gebunden und vor dem Aufruf verbraucht, Token im Log geschwärzt, Frist inklusive Verbindungsaufbau.
- Safety: NFKC + Entfernen von Format-Zeichen (Zero-Width) vor dem Regex; Moderation fail-open mit
  eigener Frist (dokumentierte Entscheidung, Regex-Boden bleibt).
- OAuth-Callback: `e.source`- und `state`-Prüfung korrekt; PKCE.
- Config-NOTIFY-Listener: Reconnect mit Backoff und Cache-Reload nach dem Reconnect.
- Aufbewahrung: Löschen in Stapeln mit eigenem Commit je Stapel.
- Studio-SPA: kein `innerHTML`/`bypassSecurityTrust`/`eval`.
- Container: `USER boerdi`, `HEALTHCHECK`, `stop_grace_period` > graceful timeout; Secrets per `:?`.

## Nicht abgedeckt (ehrlich benannt)
Keine Testläufe, kein Live-/Lasttest, keine Golden-Flows, kein `EXPLAIN` gegen echte Daten, kein
Screenreader-Test. Nur teilweise gelesen: `turn_persist.py`, `turn_assembly.py`, `agent_loop.py`,
`llm_streaming.py`, `page_context.py`, `guide_qr_injector.py`, `eval/*`, `loadtest.py`, Studio-Views.

## Priorisierte Reihenfolge zum Beheben
1. **Sofort (klein, hohe Wirkung):** M-1 Rollbacks, M-4 Meta-Cache, M-6 `rel`, M-7 Bilder, L-12 M16,
   L-1 Fehler nicht cachen.
2. **Kurzfristig:** H-2 Auftrags-Warteschlange, H-3 Popup synchron, M-2 Origin-Gate, M-5 Klassifikator-Frist,
   M-8 Pool-Settings.
3. **Mit Design-Entscheid:** H-1 `bsid`-Ticket bzw. Verlaufsgeheimnis, M-3 nach `EXPLAIN`.
4. **Laufend:** M-9 Widget-Specs, 300-Zeilen-Ratchet, `S110`/`S608` abbauen.
