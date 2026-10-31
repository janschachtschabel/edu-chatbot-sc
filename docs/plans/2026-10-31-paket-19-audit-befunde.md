# Paket 19: Befunde aus dem Audit 2026-10-31 beheben

**Anlass:** `docs/audits/2026-10-31-audit.md` (Stand `main` `f485f8e`): 0 kritisch, 5 hoch, 16 mittel,
~40 niedrig. Nutzer-Auftrag 2026-10-31: „alle Befunde beheben — plane dies nach eigenem Ermessen“.

## Entscheide (Nutzer, 2026-10-31)

| ID | Entscheid |
|---|---|
| P19-E1 (M-7) | **Kein öffentlicher Löschweg.** Verläufe bleiben für die Nachvollziehbarkeit bei Verstößen erhalten; „Neues Gespräch“ erzeugt nur eine neue ID. Die Speicherung wird im Studio gesteuert (Aufbewahrung). Das Widget legt die ID aber nicht mehr ab, wo `persist-session="false"` es verbietet (H-4). |
| P19-E2 (H-3) | **Mindestlänge 12 Zeichen** für `STUDIO_PASSWORD` und `STUDIO_API_KEY` (Nutzer: „mind. 10 bis 16“). Kürzer → Studio bzw. Schlüssel bleibt verschlossen, mit klarer Meldung beim Start und in der 503-Antwort. `BOERDI_ALLOW_OPEN_ADMIN` bleibt unverändert. |
| P19-E3 (M-4) | **Zug-Grenzen im Studio einstellbar, getrennt nach anonym und angemeldet.** Vorgabe: beide gleich und wie heute (`RATE_LIMIT_CHAT`, je Route). „Angemeldet“ gilt nur, wenn die Anmeldung vom MCP bestätigt ist (Zwischenspeicher von `services/mcp/anmeldung`), sonst zählt der Zug als anonym — ein gefälschter Block bekommt nie die Grenze der Angemeldeten. |
| P19-E4 (N-8) | **Sicherheitsprotokolle 30 Tage** (bisher 90) als Vorgabe in Seed und Modell, im Studio änderbar wie bisher. |

## Eigene Entscheide (Claude)

- **N-9:** Mindestlänge der Kennung (≥ 16 Zeichen) nur am öffentlichen Lese-Endpunkt
  `GET /api/sessions/{id}/messages` — dort wirkt die Kennung als Schlüssel. `POST /api/chat` bleibt
  offen (eine kurze Kennung schreibt nur in ihre eigene Sitzung). Lasttest-Kennungen mit `uuid4().hex`.
- **M-4 / IPv6:** Schlüssel der Drosselung fasst IPv6 auf das /64-Netz zusammen (Fehlerbehebung, ändert
  die Vorgabe-Grenzen nicht).
- **M-6:** Gespeicherte Nachricht auf 20 000 Zeichen gekappt (mit Kürzungsmarke); der Prompt-Weg
  (Entscheid 2026-08-18, kein Deckel) bleibt unberührt.
- **H-1:** Traefik-Zugriffslog bleibt an, aber ohne Pfad, Query, Kopfzeilen (nur Status, Methode, Dauer,
  Router); IP bleibt (wie im Datenbedarf 18C/D in Kauf genommen).
- **„Unklar“-Ausgang** (M-2, M-9): Fehlschlag ≠ eindeutige Antwort. Bei unklarer Zustimmung bleibt der
  Vorgang stehen, die Person bekommt die „ausgelastet“-Blase mit Bestätigungs-Chip.

## Schnitt (parallel, je Teil eigene Dateien; geteilte Dateien nur per Edit, nie überschreiben)

| Teil | Inhalt | Befunde |
|---|---|---|
| 19-1 Datenschutz Betrieb | Traefik-Felder, OTel `http.route` + kein `traceparent` an Fremde, `store=False`, 422-Handler, Logzeilen nid/Wikipedia, Seitenadresse ohne Query (Backend), Sicherheitsprotokolle 30 Tage, Backup-Hinweis, Herunterfahren-Mindestfrist | H-1, H-2, N-2, N-5, N-3, N-4, M-8 (Backend), P19-E4/N-8, N-7 (Doku), N-25 |
| 19-2 Zugang + Studio | Fehlversuch-Zähler Cookie/Schlüssel, Mindestlänge, Zug-Grenzen anonym/angemeldet im Studio, IPv6-/64, reservierte Präfixe, gespeicherte Länge, Kennung am Lese-Endpunkt, Anmelde-Cache LRU, Sprachfelder + 4xx, Studio-Transkript beim Wechsel, Aufbewahrungs-Panel-Hinweis Sicherungen | H-3, M-4, M-5, M-6, N-9, N-10, M-16, N-39, N-7 (Panel) |
| 19-3 Widget | Sitzungs-ID nur bei `persist`, Formulare sperren, Mikrofon, Sitzungswache beim Wiederherstellen und Gruß, POST-Fristen, Stale-Frist, Host-Callback, Weitere laden, `target`, OAuth-Protokoll + geschlossenes Fenster, Mikrofon verweigert, Streaming-Drossel, Seitenadresse/Query/Referrer, `query-meta` nur per Attribut | H-4, M-12, M-13, M-14, M-15, N-18, N-32–N-38, N-40, M-8 (Widget), N-1, N-6 |
| 19-4 DB + Last | Verbindung vor dem LLM frei, eigene Sperr-Engine, DB-Fristen, Config-Abgleich (Nachladen, Versionsabgleich, LISTEN-Ping, `/ready`), Cache nach Größe, Strom `aclose`, Discover-Frist, Sperre im `try`, `_resync`-Referenz, Umwandlung abschirmen | H-5, M-10, M-1, M-11, N-26–N-29, N-31 |
| 19-5 Logik | Zustimmung „unklar“, Schnellantworten unter der Blase, Dublette „unklar“, BOM/Leerraum im strengen Kopf, Lernpfad-Reset, `null`-Schalter, `LlmAusgelastet` im Strom, Retry-Chip unter Direktaktion, Skalare in Entitäten, verwaister Spec-Task | M-2, M-3, M-9, N-19–N-24, N-30 |
| 19-6 Ausnahmen + Log-Hygiene | `handleError`, Studio-`detail`, Hintergrundjob-Fehler, `save_message`-Verlust, MCP-/Anbieter-/Moderations-Zeilen gedrosselt und ohne Traceback | N-11–N-17 |

Jeder Teil: Test zuerst (rot → grün), nur berührte Tests laufen lassen; volle Suiten (Backend, ui,
Studio, widget, E2E) am Ende einmal; danach unabhängiges Review je Teil und Befunde beheben.
Änderungsnotiz je Teil unter `docs/aenderungen/2026-10-31-paket-19-<n>.md`.

## Deploy-Hinweise (sammeln)

- Studio-Passwort und `STUDIO_API_KEY` mit mindestens 12 Zeichen setzen, sonst bleibt das Studio zu.
- Sicherheitsprotokolle: neue Vorgabe 30 Tage — unberührte Installationen folgen dem Werk.

## Log

**2026-10-31, Umsetzung (sechs Teile parallel, je Test zuerst).** Einzelheiten je Teil in den
Änderungsnotizen `docs/aenderungen/2026-10-31-paket-19-1.md` … `-6.md`.

- **19-1:** Traefik-Zugriffslog als JSON ohne Pfad/Basic-Auth-Name/Kopfzeilen; OTel setzt die
  Routen-Vorlage statt des Pfads, `traceparent` nur an `B_API_BASE_URL`/MCP-Host (`_NurAnEigene`);
  `store=False` auf dem Responses-Weg und für die gpt-5/6-Familie bei `openai`/`b-api-openai`
  (`llm_responses.nichts_ablegen`); 422 nur `loc`/`type`/`msg` (`api/pruef_fehler.py`); `nid` und
  Wikipedia-Titel über `inhalt()`; Gruß-Vermerk als SHA-256 (Klartext-Altbestand zählt weiter), Prüfadresse
  ohne Anker, Query nur `v`/`id`/`p`/`page_id` (gleich wie das Widget); Sicherheitsprotokolle 30 Tage
  (Modell, Seed, Fixture, Doku); Backup-Hinweis; Herunterfahren mit Mindestfrist 0,5 s.
- **19-2:** Fehlversuch-Zähler (10/min je IP; nach Erreichen 429 auch für richtige Werte) an Cookie,
  `X-Studio-Key` und am Schlüsselvergleich in `ist_interner_zug`; Mindestlänge 12 (503 + ERROR beim Start,
  auch mit `BOERDI_ALLOW_OPEN_ADMIN`); `safety-config.turn_limits` (anonym/angemeldet, leer = `RATE_LIMIT_CHAT`),
  getrennte Töpfe je Stufe, „angemeldet“ nur bei bestätigter Person oder internem Zug; IPv6 /64;
  reservierte Präfixe → 422 außer `darf_diagnose`; gespeicherte Nachricht ≤ 20 000 Zeichen; Lese-Endpunkt
  verlangt ≥ 16 Zeichen (sonst `[]` wie unbekannt); Lasttest-Kennung mit `uuid4().hex`; Anmelde-Cache LRU
  (negative zuerst, höchstens 256); Sprachfelder geprüft, Anbieter-4xx ohne Rückfall → 400/415; Studio:
  Transkript beim Wechsel geleert, Backup-Hinweis im Panel „Aufbewahrung“, `emit-query-meta` in der Referenz.
- **19-3:** siehe Notiz; u. a. Eulen-Merker als Prüfwert, ID nur bei `persist`, Formulare gesperrt,
  `target` erzwungen, Mikrofon verworfen bei Zuklappen/`destroy`, Sitzungswache nach jedem `await`,
  POST-Fristen, Stale 120 s, Host-Rückrufe gekapselt, OAuth nur `https:`/localhost + Fenster-zu-Erkennung,
  Streaming je Rahmen, `page_url` gekürzt, kein `referrer`/`query`, neues Attribut `emit-query-meta`.
- **19-4:** Verbindung vor jedem LLM-/MCP-Abschnitt frei (`db/verbindung.verbindung_freigeben`, Hülle je
  Knoten, RAG, Import); eigene Sperr-Engine (2 + 2); DB-Fristen (`DB_*_TIMEOUT_S`, CLI ohne Fristen,
  VACUUM ohne Anweisungsfrist); Config-Abgleich mit Wiederholung, 60-s-Versionsabgleich, LISTEN-Ping, `/ready`;
  Werkzeug-Cache nach Zeichen (`MCP_TOOL_CACHE_MAX_*`); Strom `aclose`; Discover-Frist; Sperre im `try`;
  Umwandlung gibt den Platz erst nach Ende frei. Pool-Vorgabe bleibt 5 + 10 (Begründung in der Notiz).
- **19-5:** Zustimmung `JA`/`NEIN`/`UNKLAR`, Frist erst nach Platzvergabe, bei `UNKLAR` bleibt der Vorgang,
  „ausgelastet“-Blase mit nur dem Bestätigungs-Chip; Schnellantworten unter der Blase abgebrochen;
  Zug-Aufgaben werden am Zugende abgeräumt; Dublette `unklar` → kein Gruß, nächste Meldung prüft neu;
  strenger Kopf toleriert BOM/Leerraum, ohne Kopf Fehler; Lernpfad-Reset erst nach Erfolg;
  `null_heisst=False` für fremde MCP-Server und Qualitätsprotokoll; `LlmAusgelastet` im Strom als `result`;
  Retry unter Direktaktion als Aktions-Chip; Zahlen in Entitäten bleiben.
- **19-6:** `handleError` ohne Nachricht/Argumente; Studio-`detail` ohne Rohtext, mit Fehlernummer;
  Hintergrundjob-Fehler WARNING, Lasttest-Endstand abgesichert; `save_message`-Verlust WARNING;
  MCP-/Anbieter-/Moderations-Zeilen gedrosselt ohne Traceback (`llm_ereignisse.ist_voruebergehend`).
- **Nachtrag (Claude):** Lasttest speichert den Fehlertext geschwärzt (`ausnahme_text`), wie N-12.
- **Bewusst gelassen:** Gruß-Vermerk-Hash ohne Salz/HMAC (es gibt kein stabiles Server-Geheimnis für alle
  Kopien; der Vermerk verfällt mit der Sitzung); Pool-Vorgabe 5 + 10; Auth-Abweisungen 401/403 ungedrosselt.
- **Prüfung Gesamtstand:** Backend `7307 passed, 2 skipped` (ruff sauber), ui 1031, Studio 1846, widget 74,
  E2E 53, Lint + Prüfskripte sauber, `tsc` nur bekannte TS6059.

**2026-10-31, unabhängige Reviews (5 Prüfer, nur lesend) und Nachbesserungen.** Je Teil Abschnitt
„Review-Nachbesserungen“ in der Änderungsnotiz. Die wichtigsten:

- **19-1/19-6 (HOCH):** `ist_voruebergehend` wertete LiteLLMs Sammel-`APIConnectionError` und jeden
  `TimeoutError` als Anbieterausfall → echte Programm-/DB-Fehler wären gedrosselte Warnungen ohne Traceback
  geworden. Jetzt nur mit Netzfehler in der Kette bzw. eigener Frist (`LlmFristAbgelaufen`). Dazu: 422 behält
  Schema-Grenzen aus `ctx` (Erlaubnisliste, das Studio braucht sie), Gruß-Vermerk als HMAC mit Salz je Sitzung,
  Titel/Suchbegriff fremder Seiten nicht mehr in den Entities, `handleError` mit Ort.
- **19-2 (MITTEL):** Mindestlänge 16 auch an Chat/Stream (sonst Lesen fremder Verläufe über den Prompt);
  Sperre mit WARNING + Zähler `boerdi_studio_auth_failures_total` (bewusst kein anlagenweiter Deckel);
  derselbe falsche Wert zählt je IP einmal je Minute; Studio zeigt 429 als „gesperrt“ mit Wartezeit;
  Valkey-Ausfall → Zählung aus, Vergleich bleibt; Deckel 20 000 nur für Nutzernachrichten; STT-Rückfall nur
  bei 413/415/422 abgebrochen.
- **19-3 (HOCH):** ohne `persist-session` kein `?bsid=` an Links (sonst legte das WLO-Widget die ID ab);
  `queryMeta` auch als Element-Ereignis nur mit Attribut; SVG-`xlink:href` gesperrt; POST-Rückfall eines
  Chat-Zugs mit Frist 960 s (Agent-Werksfrist + Puffer).
- **19-4 (HOCH):** DB-Fristen per `SET` beim Verbindungsaufbau statt als Startparameter (PgBouncer weist
  Startparameter ab); Stopp-Reihenfolge des Config-Abgleichs; VACUUM ohne `lock_timeout`; Warnung bei
  ungespeicherten ORM-Änderungen vor dem Freigabe-Commit; Pool-Wartezeit gemeldet; Formel
  `N × (DB_POOL_SIZE + DB_MAX_OVERFLOW + 6) + Reserve`.
- **19-5 (MITTEL):** Bei `unklar` bleibt der Vorgang nur, wenn die Rückfrage mit Vorschau und Chip gezeigt
  wird (sonst in der DB verworfen — Tour-/gedrosselte Züge); `unklar` nur bei Last/Frist/vorübergehendem
  Fehler, abgelaufene Vorgänge werden verworfen; Platzfrist der Prüfung 3 s; Fristablauf zählt als
  „abbruch“; MCP-Vorabruf-Aufgaben werden am Zugende abgeräumt.
- **Neu offen** (`docs/offene-befunde-und-todo.md` §2): PII-Treffer im Klartext in `safety_logs`
  (Nutzer-Entscheid); Tab-Titel nicht auflösbarer fremder Seiten in `_page_metadata`.
- **Prüfung nach den Nachbesserungen:** Backend `7367 passed, 2 skipped` (ruff sauber), ui 1042,
  Studio 1848, widget 74→76, E2E 53 (ein Lauf parallel zur Backend-Suite hatte einen Fokus-Ausreißer in
  `auth-button.spec.ts`, einzeln 3× und im Wiederholungslauf grün), Lint + Prüfskripte sauber.
