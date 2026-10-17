# Offene Entscheidungen — kurz erklärt

Stand 2026-10-15, Entscheide oben. Je Punkt steht, worum es geht und welche Antwort gebraucht wird. Die
Einzelheiten stehen in der genannten Quelle. Fällt eine Entscheidung, wird sie hier und in der
Quelle nachgetragen; die Befundliste [`offene-befunde-und-todo.md`](offene-befunde-und-todo.md)
bleibt der Sammelort für alles Offene.

Quellen: **P4** = [`plans/2026-10-03-paket-4-audit-extern.md`](plans/2026-10-03-paket-4-audit-extern.md) §5,
**R** = [`plans/2026-09-29-responses-systemteil-und-cache.md`](plans/2026-09-29-responses-systemteil-und-cache.md) §9,
**B** = Befundliste §2, **BM** = [`plans/2026-09-26-betriebsmodi-und-studio.md`](plans/2026-09-26-betriebsmodi-und-studio.md) §11.

## Offen seit Paket 10 (2026-10-14, drittes Audit)

Quellen: Plan [`plans/2026-10-14-paket-10-drittes-audit.md`](plans/2026-10-14-paket-10-drittes-audit.md),
Audits `audits/2026-10-10-*.md`.

- **Entschieden 2026-10-14 (Nutzer), H-1:** `?bsid=` behält Vorrang vor Cookie und localStorage.
  Restrisiko: Wer einer Person einen Link mit seiner eigenen `bsid` unterschiebt, liest deren weiteres
  Gespräch über `GET /api/sessions/{id}/messages` mit — die Kennung ist der Schlüssel zum Verlauf.
  Später möglich: ein einmaliges Übergabe-Ticket statt der `bsid` in der Adresse oder eine
  abgezweigte Sitzung.
- **Entschieden 2026-10-15 (Nutzer), A-2 Zugangsblock im `sessionStorage` der Gastseite:** langfristig
  lösen, kurzfristig unkritisch (der MCP-Server wird umgebaut). Ja, auf einer Drittseite kann jedes Skript
  dort den Block lesen und damit bis zum Widerruf als die Person in WLO lesen und schreiben (der Block
  enthält das Passwort verschlüsselt, läuft nicht ab und ist an nichts gebunden). Dokumentiert für das
  MCP-Team in [`mcp-und-anmeldung.md`](mcp-und-anmeldung.md) (R1, Wünsche §4). Bis dahin: mit Anmeldung
  nur auf vertrauenswürdigen Seiten einbetten, `CORS_ORIGINS` setzen.
- **A-4 Abmelden widerruft nicht:** Der MCP-Server hat `POST /auth/revoke`, aber ohne CORS — das Widget
  kann ihn auf einer fremden Seite nicht rufen. **Ohne MCP-Änderung machbar:** Das Widget schickt den Block
  beim Abmelden an ein neues Backend-Ende, das Backend widerruft serverseitig. Gebraucht: Ja/Nein (oder
  warten, bis der Umbau es löst). Einzelheiten: [`mcp-und-anmeldung.md`](mcp-und-anmeldung.md) R2.
- **Entschieden 2026-10-15 (Nutzer), A-6 Zustimmung per Freitext: Liste + LLM-Prüfung.** Niemand soll
  an seinem Wortlaut scheitern. Umgesetzt (`services/zustimmung_pruefen`): die Erlaubnisliste bleibt der
  schnelle Weg; passt sie nicht, entscheidet ein kurzer Aufruf (Temperatur 0, Frist 3 s, Phase
  `zustimmung`), aber nur, wenn keine Vetowörter (Verneinung, Absage, Änderungswunsch, Fragezeichen —
  `domain/zustimmung.hat_veto`) dastehen. Fehler oder Zeitüberschreitung = keine Zustimmung. Bekannte
  Grenze: „ja, und such mir dann noch Videos“ gilt als Zustimmung; ausgeführt wird, der Zusatzwunsch geht
  verloren (die Person stellt ihn neu). **Wenn Fehlausführungen auffallen:** Logzeile
  `Zustimmungs-Prüfung für … : zustimmung` neben der Nachricht prüfen; Vetoliste ergänzen oder auf
  „Schreiben nur per Knopf“ (Kurzaudit V-4/V-5) gehen.
- **Erledigt 2026-10-15 (Nutzer-Wahl „Klassifikator + Nachsteuerung“), S-7 falsches Muster:** In der
  Muster-Maschine leitet `domain/kuration_umleitung` einen Auftrag mit Kurationsverb und Gegenstand im
  Bestand (keine Wie-Frage) vor der Musterwahl nach M18, mit Webadresse nach M20; Wortlisten im Studio
  (`classify-overrides` → `curation_reroute`), dazu Few-Shots und Intent-Trigger für I09. Nach dem Import
  von `classify-overrides` wirksam. Ein Golden-Flow „Kuration angemeldet“ bleibt beim Nutzer.
- **Entschieden 2026-10-15 (Nutzer), A-7 und A-9: vorläufig so lassen** (`bsid` bekannt; `allow_curation` bleibt per Vorgabe an — ist es aus, bekommt der Agent die schreibenden Werkzeuge ohnehin nicht). Die Erklärungen bleiben unten stehen.
- **A-7 Schreib-Vorschau im öffentlich lesbaren Verlauf** (neu erklärt 2026-10-15): Jedes Gespräch hat
  eine Kennung (`bsid`). Wer sie kennt, kann den Verlauf ohne Anmeldung abrufen
  (`GET /api/sessions/{id}/messages`) — so stellt das Widget nach einem Neuladen das Gespräch wieder her.
  Im Verlauf steht auch die **Vorschau eines Schreibvorgangs** einer angemeldeten Person: Titel,
  Beschreibung, Sammlungs-Kennungen, auch von nicht öffentlichen Sammlungen, und bei eingebetteten
  Seiten die vorbereitete Anfrage (`_prepared_write`). Ausführen kann ein Mitleser nichts (die Abnahme ist
  an die Person gebunden), aber **lesen**. Bekannt ist die Kennung nur dem, der sie hat — sie wandert aber
  über `?bsid=` in Links (H-1: bleibt so). Möglich: (a) so lassen; (b) die vorbereitete Anfrage aus dem
  öffentlichen Verlauf nehmen und nur nach einem Stromabbruch über einen einmaligen Schlüssel ausliefern
  (die Vorschau-Box bliebe lesbar); (c) zusätzlich die Vorschau-Box für Gäste ausblenden. **Empfehlung:**
  (a), solange `bsid`-Links nicht weitergegeben werden; (b), wenn eingebettete Schreibvorgänge häufig
  werden. Gebraucht: a/b/c.
- **A-9 `/api/agent` darf per Vorgabe kuratieren** (neu erklärt 2026-10-15): `/api/agent` ist die
  Schnittstelle für **andere Anwendungen** statt des Chat-Widgets — Browser-Erweiterung, edu-sharing-Einbettung,
  Server-zu-Server. Herein kommt man mit der Anmeldung der Person, mit dem Studio-Schlüssel oder, nur für
  Testläufe, mit `AGENT_OPEN`. Ein Aufruf
  trägt das Feld `allow_curation`; fehlt es, gilt `true` — der Agent bekommt dann die schreibenden
  Werkzeuge angeboten. Geschrieben wird trotzdem nur mit einer bestätigten Person (eigene Anmeldung im
  Aufruf) und nur zweistufig; ohne Person bleibt es bei einer Vorschau. Die Frage ist nur, ob eine
  Anwendung, die das Feld vergisst, Schreibwerkzeuge sehen soll. (a) so lassen (wer nichts angibt, kann
  alles, was die Person darf); (b) Vorgabe `false` — jede Anwendung muss Schreiben ausdrücklich
  verlangen, bestehende Aufrufer, die schreiben, müssen das Feld ergänzen. **Empfehlung:** (b), sobald
  eine zweite Anwendung angeschlossen wird; heute (a). Gebraucht: a/b.
- **Entschieden 2026-10-15 (Nutzer), P9-3 Abschied mit Anlass in einem anderen Satz: so lassen.**
  Strenger hieße mehr Fehlalarme bei Lehrkräften.
- **Entschieden 2026-10-15 (Nutzer), S-6(b) Kontext-Gruß bei offener Abnahme: bleibt so.** Ein
  sichtbarer Gruß nach einem Seitenwechsel verwirft die offene Abnahme (Regel aus Audit 2026-09-29): ein
  „ja“ auf der neuen Seite könnte das neue Material meinen, ausgeführt würde das alte. Seit Paket 10 nennt
  die Box die Frist. **Wenn es wieder Probleme gibt** (Meldungen „nach dem Seitenwechsel kam eine neue
  Vorschau“, Logzeile `offener Vorgang … verworfen — dieser Zug ist keine Antwort auf die Vorschau` direkt
  nach einem `context_greeting fired`): Alternative wäre, den Gruß zu unterdrücken, solange eine Abnahme
  offen ist — dann aber die Vorschau-Box mit dem Material-Titel deutlich machen.
- **Entschieden 2026-10-15 (Nutzer), S-2 Knopf „im Repositorium anmelden“: nein.** Alle
  Anmeldevorgänge laufen über den Anmelde-Knopf im Widget und die Anmeldung des MCP-Servers; einen
  eigenen Weg ins Repositorium braucht es heute nicht. **Neu denken, falls sich die Kette Chatbot → MCP →
  edu-sharing-Repositorium ändert** (etwa wenn der Browser im eingebetteten Betrieb wieder selbst mit
  der Repository-Sitzung schreibt und diese getrennt abläuft).
- **Optional (zutreffend, geringe Wirkung):** L-2 Label-Cache je Prozess, L-6 f-String-SQL aus
  Konstanten, L-8 doppelte Screenreader-Ansagen (braucht einen Test mit Screenreader), L-10 Aufräumen
  beim Entfernen des Widgets, L-11 `MutationObserver` ohne Drossel, L-13 Lease-Verlust nur geloggt,
  M-9 Widget-Specs ausbauen.

## Offen seit Paket 9 (2026-10-09)

- **Entschieden 2026-10-15 (Nutzer), AcademicCloud und Einbettungen: so lassen.** Die Wissensbasis liegt im
  OpenAI-Raum; ein Wechsel ist kein Schalter. Ein Einbettungsmodell der AcademicCloud soll aber machbar und
  angebbar sein → Paket 11 (D): `LLM_EMBED_MODEL` leitet schon heute über `/academiccloud`; dazu kommt ein
  Kommando, das die Wissensbasis in den neuen Raum überführt. Stand 2026-10-15: die AcademicCloud führt über
  die b-api kein Einbettungsmodell.
- **Gesprächsstand ruhender Sitzungen** (V7, entschieden in Paket 9 im Sinn der 30-Tage-Frist,
  umkehrbar): Entities, Signale und Tour-Stand einer Sitzung, die länger als die Frist der Verläufe
  ruht, werden geleert; die Sitzung und ihre Kosten bleiben. Soll das nicht so sein, genügt eine
  Zeile in `services/aufbewahrung.fristen`.

## Entschieden am 2026-10-09, zweite Runde (Nutzer)

Umsetzung als Paket 8, Plan `plans/2026-10-09-paket-8-antworten.md` — **umgesetzt am 2026-10-09**.

- **Modelle:** Vorgabe bleibt `b-api-openai` mit `gpt-6-luna`. AcademicCloud-Modelle müssen laufen
  können, sollen aber nicht Vorgabe sein (langsamer, schlechter). Umgesetzt: Vorgabe beider
  OpenAI-Wege `gpt-6-luna`; AcademicCloud-Chat `qwen3-30b-a3b-instruct-2507`, die Einbettung dort über
  den OpenAI-Pfad der b-api (derselbe Vektorraum wie die Wissensbasis). Der Werkzeugaufruf auf der
  AcademicCloud ist ungeprüft — jede Probe endete mit 429.
- **Parallelität:** `b-api-openai` wie OpenAI direkt, also 20.
- **`retention_days`:** bauen, in Backend und Studio. Umgesetzt: ein Lauf alle 6 Stunden löscht, was
  älter ist als die Frist (0 = unbegrenzt); im Studio das Panel „Aufbewahrung“ auf der
  Datenschutz-Seite.
- **P5-7:** nach eigenem Ermessen. Gebaut: HSTS (Vorgabe ein Tag) und die CSP fürs Studio (gleich
  durchgesetzt, nachdem eine Browser-Probe über alle Seiten keinen Verstoß fand; `STUDIO_CSP=report`
  ist der Rückweg). Zurückgestellt mit Grund (Plan, Abschnitt P): Socket-Proxy, zweiter
  Sicherungsort, Studio-Sitzungen, CORS zu.
- **Krisenschwelle:** nach Messwerten und eigener Empfehlung, wo sinnvoll im Studio konfigurierbar.
  Umgesetzt: Die Schwellen bleiben bei 0,25 — gesenkt brächten sie nur Fehlalarme (Romeo und Julia
  bei 0,158). Die Lücke schließen 23 eingebaute Krisen-Wendungen im Regex-Gate: 24 von 28
  gemessenen Andeutungen ohne Moderation, 25 mit; sie wirken auch auf der AcademicCloud ohne
  Moderation. Im Studio bleiben Schwellen und eigene Wendungen (`extra_crisis_terms`) pflegbar; die
  Hinweise dort nennen die Messwerte.
- **C1 „blockweise kürzen“:** erklärt im Plan, Abschnitt C.

**Nachfrage, am selben Tag beantwortet** (umgesetzt, Paket-8-Plan, Log „Nachtrag“):
- **Frist für Gesprächsverläufe:** Vorgabe 30 Tage, änderbar. Gelöscht werden Chatnachrichten und
  Sitzungsgedächtnis; die Sitzungen und ihre Verbrauchszahlen bleiben (sonst ginge die Kostenübersicht
  mit).
- **Folgezüge, Rest von C1:** erstmal lassen — viel Korrekturbedarf bei wenig Mehrwert.
- **GWDG-Modelle und Werkzeuge:** je Modell einzeln testen; ein Todo außerhalb des Chatbots.
- **Studio-Startpaket:** etwas über der Warnschwelle ist in Ordnung.

Aus Paket 8 ist damit nichts mehr offen.

## Entschieden am 2026-10-09 (Nutzer)

Umsetzung als Paket 7, Plan `plans/2026-10-09-paket-7-entscheide.md` — **umgesetzt am 2026-10-09**;
L8 (AcademicCloud-Modelle) folgte in Paket 8. Messungen danach (Golden-Läufe u. a.)
stehen in der Befundliste §3. Die Tabellen darunter bleiben als Erklärung stehen; offen sind nur noch
die Punkte am Ende dieses Abschnitts.

- **P5-1 Sitzungssperre:** umsetzen.
- **P5-2 Abbruch beim Streaming:** sauber zu Ende generieren, die Antwort aus dem Verlauf nachliefern.
- **P5-3 Kosten von `/api/agent`:** ja, mit aufnehmen, wenn die Aufträge uns Token kosten.
- **P5-4 Einstellungen ohne Wirkung:** streichen wie empfohlen (`agent.safety`, `default_enabled`
  des Lotsen, `confidence_adjustments`); `rag-retrieval` im Studio pflegbar machen;
  `inline_result_grouping` reparieren (danach Golden-Lauf).
- **P5-5 Wiederherstellen:** Option „exakt“ dazu, „ergänzend“ bleibt Vorgabe und ist wählbar.
- **P5-6 Responses-Plan:** E-A und E-A1 ja; E-B ja; E-B2 im Code (braucht es Steuerung, dann im
  Studio); E-C erst messen, bei Eignung umbauen; E-D ja; E-E ja; E-AC prüfen und anpassen; N-1 ja.
- **P5-8 PDF/Word in die Wissensbasis:** ja.
- **P5-9 Schreiben ohne Anmeldung:** standardmäßig aus. Im Muster-Modus wie im Agent-Modus nur mit
  eigenem WLO-Konto. Eine Option im Studio schaltet das Schreiben mit dem Gastkonto (Dienst-Token)
  ein — mit Warnung und Verweis auf die Umgebungsvariablen.
- **Einzelfragen:**
  - „Freigabe“ als Zustimmung: ja (freigabe, freigeben, freigegeben).
  - Vorgabe-Maschine im Seed: Agent.
  - Agent-Schnellantworten: ja (Master-Skill-Text überträgt der Nutzer, danach an).
  - Fast-Modus: im Studio einschaltbar, mit Hinweis auf die Mehrkosten.
  - Token-Streaming: Vorgabe an, wenn ohne Nachteil; im Studio steuerbar, sonst per Umgebung.
  - RAG neben der Klassifikation: bauen.
  - Antwortsprache: in allen Modi die Sprache, in der die Person schreibt.
  - Seitengruß beim Sprachwechsel: in der neuen Sprache neu zeigen.
  - M10: MCP und Inhaltsabrufe nutzen dürfen, RAG ebenfalls.
  - Tote Auslöser: bereinigen, außer sie werden noch gebraucht (prüfen: Web-Tour, Aktionen per Auslöser).
  - `rag-retrieval`: im Studio pflegbar machen (vermutlich fehlt nur die Verdrahtung).
  - D-10 Master-Skill: nur im Agent-Modus (bleibt so).
  - D-11 Kosten: in EUR; Preise werden direkt in EUR hinterlegt, keine Umrechnung.
  - Werkzeug-Ablehnungen im Log: ERROR lassen.
  - GV-RED-1: nur noch auf Abruf.
  - Moderations-Schwellen: anpassen wie empfohlen.
  - B-API-Moderation: testen; bei b-api-openai deren Moderation nutzen, falls möglich; bei
    b-api-academiccloud automatisch aus.
  - Studio-Startpaket: lassen, solange das Budget hält.
  - Policy bei Zeitüberschreitung: so lassen.
  - Skill-Suche: `search_skill` ist nur Rückfall; standardmäßig verborgen, nur nach Aktivierung.
    Allgemeiner: im Studio je MCP-Server festlegen, welche Werkzeuge aktiv sein dürfen.
- **Rahmen für die LLM-Anbindung:**
  - b-api-academiccloud: prüfen, ob der Responses-Endpunkt unterstützt wird.
  - Parallelität: OpenAI (auch gpt-6 über OpenAI) bis 20 gleichzeitige Aufrufe, b-api-academiccloud
    vorerst 2.
  - Evaluationen und andere Dienste laufen mit dem Modell, das für den Chat eingestellt ist.
  - Aufrufparameter der gpt-5- und gpt-6-Familie nur für diese Familien; ältere und
    AcademicCloud-Modelle kennen sie nicht.
- **Damals offen, in der zweiten Runde beantwortet (siehe oben):** P5-7 (der Nutzer wollte Vor- und
  Nachteile, Bauaufwand und Änderungen bei der Nutzung sehen) und `retention_days`. Dazu aus der
  Umsetzung:
  - **AcademicCloud-Modelle:** Chat `mistral-large-3-675b-instruct-2512` und Einbettung
    `e5-mistral-7b-instruct` antworten 503 („Model pricing unavailable“); `qwen3-30b-a3b-instruct-2507`
    läuft. Auf welche Modelle umstellen?
  - **Parallelität b-api-openai:** 20 wie OpenAI direkt oder 2? Bis zur Antwort 2.
  - **Krisen-Andeutungen unter jeder Schwelle** (K8): Krisen-Wendungen pflegen oder eine
    Krisen-Einschätzung im Klassifikator bauen?
  - **Folgezüge (Rest von C1):** „Zuletzt gezeigt“ an die Antwort und das Fenster blockweise kürzen.
    Nachgemessen im Review (B-3): mit Antworten über 1 200 Zeichen bricht der Cache schon ab Zug 3,
    ≈ 300 Token mehr ungecacht je Zug und langer Antwort; der Systemteil bleibt gecacht
    (Befundliste §2, Zahlen im Paket-7-Log).

## P5-7 im Einzelnen (geprüft 2026-10-09)

Fünf Teile, unabhängig voneinander entscheidbar. „Bauen“ trennt Code im Repo von Server-Betrieb.

| Teil | Heute | Bauen | Was sich ändert | Vorteil | Nachteil |
|---|---|---|---|---|---|
| **HSTS** (Browser nur noch per HTTPS) | kein HSTS; nur drei einfache Header (`main.py`) | klein, nur Deploy: Traefik-Header, Dauer schrittweise erhöhen | Redaktion: nichts. Admins: ein abgelaufenes Zertifikat ist ein harter Ausfall (kein Wegklicken mehr) — Zertifikats-Überwachung nötig | kein Rückfall auf HTTP | Aussperr-Risiko bei Zertifikatsfehlern |
| **CSP fürs Studio** (nur erlaubte Skripte und Quellen) | keine CSP; der Studio-Build hat ein Inline-Skript in `index.html` | klein–mittel: Header für `/studio` im Backend, Angular-Build anpassen, erst „nur melden“, dann scharf | Redaktion: nichts, wenn die Regel stimmt; gefährdet sind Drucken/PDF, Anmeldung und Vorschaubilder in der Widget-Vorschau | eingeschleuster Code im Studio (etwa über Inhalte in der Vorschau) läuft nicht | schützt nicht die Demo-Seiten auf derselben Adresse (dafür eigene CSP dort oder eine eigene Studio-Adresse) |
| **Studio-Sitzungen** mit Ablauf und Widerruf | Cookie aus dem Passwort abgeleitet, 30 Tage im Browser, serverseitig nicht widerrufbar; Widerruf nur per Passwortwechsel + Neustart | mittel: Sitzungstabelle (Migration), zufälliger Schlüssel, Ablauf, echtes Abmelden, Studio-Ansicht „Sitzungen“, Not-Befehl | Redaktion: gleiches Passwort, gelegentlich neu anmelden, nach dem Deploy einmal. Admins: verlorene Sitzungen gezielt beenden | gestohlenes Cookie wertlos, verrät nichts über das Passwort; Grundlage für „wer hat was geändert“ und spätere Rollen | ein Fehler im Tor sperrt alle aus (Ausweg: Passwort + Not-Befehl); bricht die Kompatibilität mit dem ALT-Studio |
| **Docker-Socket-Proxy** | Traefik (am Internet) hat den Docker-Socket „nur lesend“ — das schützt die Docker-API nicht | klein, nur Deploy: Proxy-Container, der nur Leseabfragen durchlässt; MIT-lizenzierter Proxy (HAProxy-basierte sind GPL) | Admins: ein Container mehr; falsch eingestellt hat Traefik keine Routen (sofort beim Deploy sichtbar) | übernommenes Traefik ist nicht mehr gleich Root auf dem Server | eine Komponente mehr in der Lieferkette |
| **Sicherung auf zweitem Rechner** + Probe + Alarm | tägliche DB-Sicherung, aber nur auf demselben Server (14 Tage); kein Alarm, keine Probe-Wiederherstellung | Repo klein–mittel: verschlüsselte Kopie nach außen (restic/rclone), Lebenszeichen-Ping, Probe-Skript. Betrieb: zweiter Speicherort in der EU (AV-Vertrag), Schlüssel, Alarmkanal, eine Übung | Admins: neue `.env`-Einträge, Alarme beantworten, Speicherkosten | übersteht Serververlust und Kompromittierung; Fehler fallen binnen eines Tages auf; Wiederherstellung bewiesen | Sicherungen enthalten Chatverläufe (Datenschutz am zweiten Ort); laufende Betreuung; bis zu 24 h Datenverlust bleiben |
| **CORS zu** als Vorgabe | offen für alle Websites (bewusst seit 2026-08-18, Safari-Vorfall) | klein: Vorgabe umdrehen, Doku, Tests; optional abgelehnte Herkünfte loggen; optional Liste im Studio pflegen (mittel) | jede einbettende Website (www/ohne www, Staging, edu-sharing, LMS) muss in die Liste, sonst scheitert jede Anfrage — sichtbar nur in der Konsole der Website; Änderung braucht Neustart; Server mit `CORS_ALLOW_ALL=true` in der `.env` bleiben offen | fremde Websites nutzen Widget und LLM-Budget nicht mehr über ihre Besucher | kein Schutz außerhalb des Browsers (dafür das Rate-Limit); genau der Fehlersuch-Aufwand, den die offene Vorgabe vermeiden sollte |

**Rollen** bleiben „später“: Sie brauchen persönliche Konten oder die WLO-Anmeldung. Eine
Sitzungstabelle mit Platz für Person und Rolle hält den Weg offen.

**Empfohlene Reihenfolge:** Socket-Proxy (klein, großer Gewinn), Sicherung extern mit Alarm (größter
Risikoabbau, braucht einen zweiten Speicherort), HSTS zusammen mit Zertifikats-Überwachung, CSP fürs
Studio (erst „nur melden“), Studio-Sitzungen, CORS zu erst mit der Liste der echten Einbettungen.

**Umgesetzt in Paket 8:** HSTS und CSP fürs Studio — beide im Repo prüfbar. HSTS kommt aus dem Backend
statt aus Traefik: so gilt es hinter jedem Proxy und steht im Test. Die CSP ist gleich durchgesetzt:
Eine Regel, die nur meldet, liest ohne Meldeadresse niemand, und die Browser-Probe fand keinen Verstoß.
Socket-Proxy und Sicherung extern sind reiner Server-Betrieb und lokal nicht ohne neue Images bzw.
einen zweiten Speicherort prüfbar; sie bleiben, mit Studio-Sitzungen und „CORS zu“, zurückgestellt.

## Paket 5 (P4 §5)

| Nr. | Worum es geht | Gebraucht wird |
|---|---|---|
| P5-1 Sitzungssperre | Laufen mehrere Backend-Kopien (Replikas), können zwei Nachrichten derselben Sitzung gleichzeitig laufen und sich Verlauf und Zähler überschreiben. Deshalb läuft heute nur eine Kopie (`BACKEND_REPLICAS=1`). | „Sperre je Sitzung in Postgres bauen“ (Empfehlung; eine zweite gleichzeitige Nachricht bekäme „Sitzung beschäftigt“, danach sind wieder mehrere Kopien möglich) oder „bei einer Kopie bleiben“. |
| P5-2 Abbruch beim Streaming | Schließt jemand den Chat mitten in einer Antwort, rechnet der Server ungeplant weiter, und das Widget schickt die Frage teils ein zweites Mal. | „Zu Ende rechnen, sauber, und die Antwort aus dem Verlauf nachliefern“ (Empfehlung) oder „abbrechen“. |
| P5-3 Kosten von `/api/agent` | Aufträge, die Gastanwendungen direkt an den Agenten schicken, verbrauchen Token, erscheinen aber nicht in der Kostenübersicht. | Ja/Nein zu einer Migration, die sie mit der Quelle „Agent-API“ bucht. |
| P5-4 Einstellungen ohne Wirkung | Das Studio zeigt Felder, die nichts bewirken. | Je Feld: `retention_days` → Lösch-Job bauen (Gespräche nach N Tagen löschen) oder Feld streichen; `agent.safety`, `default_enabled` (Lotse), `confidence_adjustments` → streichen (Empfehlung); `01-base/rag-retrieval` → im Studio pflegbar machen; `inline_result_grouping` → reparieren (danach Golden-Lauf). |
| P5-5 Wiederherstellen „exakt“ | Ein Snapshot oder Backup schreibt nur seine eigenen Bereiche zurück. Was seitdem neu angelegt wurde, etwa ein neues Muster, bleibt stehen. | Ja/Nein zu einer zusätzlichen Option „exakt“, die solche Bereiche löscht. Die Vorgabe bliebe „ergänzend“. |
| P5-6 Responses-Plan | siehe nächster Abschnitt | — |
| P5-7 Studio- und Server-Härtung | Sicherheits-Header (HSTS, CSP) fürs Studio; Studio-Anmeldung mit Ablauf und Widerruf (heute gilt ein Schlüssel aus dem Passwort unbegrenzt); Docker-Socket nur über einen Proxy; Sicherungen auf einem zweiten Rechner; CORS standardmäßig zu. | Welche Teile, in welcher Reihenfolge. Einiges ist Server-Betrieb (Traefik, zweiter Host). |
| P5-8 PDF/Word in die Wissensbasis | Der Import von PDF, DOCX, PPTX und XLSX scheitert, weil Zusatzpakete fehlen (Lizenzen MIT/BSD/HPND). | Ja/Nein zum Einbau (das Image wird größer). Dazu: MPL-2.0 im Lizenz-Gate als dokumentierte Ausnahme? `certifi`, `orjson` und `tqdm` laufen heute schon still durch. |
| P5-9 Schreiben ohne Anmeldung (B-H3) | Im Muster-Modus nimmt der Bot schon mit dem Dienst-Konto Inhalte in Sammlungen auf, ohne persönliche Anmeldung; im Agent-Modus nur mit Anmeldung. | „Muster-Modus angleichen: nur mit Anmeldung“ oder „über einen ausdrücklichen Schalter erlauben“. |

## Responses-Plan (R §9)

Neue OpenAI-Modelle laufen über einen anderen Schnittstellen-Weg. Dort kommen die Systemtexte
verklebt an, Seiteninhalt von Dritten steht auf Systemebene, und der Prompt-Cache trifft kaum
(auf einer neuen Seite 0 von 18 674 Token).

| Nr. | Worum es geht | Gebraucht wird |
|---|---|---|
| E-A, E-A1 | Den Systemteil sauber zusammensetzen, damit Überschriften nicht mitten in einer Zeile landen. | Ja/Nein; für beide OpenAI-Wege (Empfehlung) oder nur für gpt-6? |
| E-B | Den Seiteninhalt aus dem Systemteil in eine gerahmte Nachricht vor dem Verlauf verschieben: Der Cache trifft wieder, und kein Fremdtext steht auf Systemebene. Große Seitentexte kosten dann je Folgezug mehr. | Ja/Nein, dazu die Freigabe des Regeltexts (R §6, Task B3). Danach ein Golden-Lauf (du). |
| E-B2 | Wo die Regeln zum Seiteninhalt stehen. | „Im Code“ (Empfehlung) oder „später im Master-Skill“. |
| E-C | „Zuletzt gezeigt“ steht vor der Nachricht und kostet den Cache ab dem Folgezug. | „Erst nachmessen“ (Empfehlung) oder „gleich umbauen“. |
| E-D | Im Muster-Modus den Status der Ergebnis-Box an die Werkzeug-Nachricht hängen; eine bewusste Abweichung vom Altsystem. | Ja/Nein. |
| E-E | Muster-Prompt und Klassifikator genauso umbauen. | Jetzt nichts; erst nach dem Golden-Lauf zu E-B. |
| E-AC | Ob AcademicCloud zwei Nutzer-Nachrichten hintereinander annimmt, ist ungeprüft. | „Zusammenlegen“ oder „du prüfst erst“. |
| N-1 | Doppelte Überschrift „Aktuelle Seite — Aktuelle Seite“ bei fremden Seiten und der Startseite. | Ja/Nein (klein). |

## Einzelfragen (B §2)

| Thema | Worum es geht | Gebraucht wird |
|---|---|---|
| „Freigabe“ als Zustimmung | Ein Gatekeeper-Skill fragt nach „Freigabe“. Ein „Freigabe erteilt“ ohne „ja“ verwirft heute den offenen Schreibvorgang, und es kommt eine neue Vorschau. | Ja/Nein zu den Wörtern freigabe, freigeben, freigegeben (Empfehlung: ja; „frei“ allein nicht). |
| Vorgabe-Maschine im Seed | Der Auslieferungsstand stellt die Muster-Maschine ein, im Betrieb soll der Agent Vorgabe sein (D-15). **Folge für den Werkszustand:** „Alles auf Auslieferungsstand“ stellt eine Anlage auf die Muster-Maschine zurück. | „Seed auf Agent stellen“ (Empfehlung) oder „bleibt Muster, je Anlage im Studio umschalten“. |
| Agent-Schnellantworten | Der Agent schreibt die Antwort-Knöpfe gleich mit, statt einen zweiten Aufruf zu machen: ein Zug dauert dann 6,8 statt 12,2 s. Vorher muss der Master-Skill-Abschnitt „Schnellantworten“ angepasst werden; der Text liegt im Kette-Plan bereit. | Ja: Du überträgst den Text, danach wird `AGENT_INLINE_QUICK_REPLIES` eingeschaltet. |
| Fast-Modus | Die schnellere OpenAI-Stufe `LLM_SERVICE_TIER=fast` bringt einen Muster-Zug von 9,1 auf 7,7 s. Dafür gilt der 4- bis 5-fache Tokenpreis, und die Daten bleiben nicht in der EU. Wirkt nur bei direktem OpenAI-Zugang. | Ja/Nein. |
| Token-Streaming als Vorgabe | Die Antwort erscheint Wort für Wort statt am Stück. Gebaut, aber aus (`CHAT_TOKEN_STREAMING`). | „Erst auf Staging per Umgebung einschalten“ (Empfehlung) oder „gleich überall“. |
| RAG neben der Klassifikation | Die Wissenssuche liefe parallel zur Klassifikation statt danach. Das spart bei Wissensfragen bis zu 2 s. | Ja/Nein zum Bau. |
| Antwortsprache im Muster-Modus | Der Muster-Modus antwortet in der Sprache der Oberfläche, der Agent in der Sprache, in der die Person schreibt. | „Muster-Modus wie der Agent“ (danach Golden-Lauf) oder „so lassen“. |
| Seitengruß beim Sprachwechsel | Nach einem Sprachwechsel bleibt der schon gezeigte Seitengruß in der alten Sprache. | Ja/Nein zu einem eigenen Weg, der ihn in der neuen Sprache neu zeigt. |
| M10 widerspricht sich | Das Muster „KI-Inhalt erzeugen“ verlangt im Text die Suche in der Wissensbasis, darf die Wissensbasis laut seinen Quellen aber nicht nutzen. | „Wissensbasis erlauben“ oder „Pflicht aus dem Text streichen“. Beides ändert Antworten, danach Golden-Lauf. |
| Tote Auslöser (ST-5, Befund 1) | `create-triggers` und `edit-triggers` wirken nirgends mehr, stehen aber im Studio. | Ja/Nein zum Bereinigen (Empfehlung: ja; Dateien, Studio-Abschnitte und Tests fallen weg). |
| `rag-retrieval` (ST-5, Befund 2) | Eine Einstellung der Wissenssuche wird gelesen, ist im Studio aber nicht pflegbar. Gleicher Punkt wie in P5-4. | „Pflegbar machen“ (Empfehlung; Umgebungsvariablen behalten Vorrang) oder „den Zweig streichen“. |
| D-10 Master-Skill im Muster-Modus | Der Master-Skill wirkt heute nur im Agent-Modus (BM §11). | „Bleibt so“, „zusätzlich zu Grundpersona und Domänen-Regeln“ oder „ersetzt sie“. |
| D-11 Währung der Preistafel | Die Kostenrechnung nutzt USD wie der Anbieter. | „USD“ (Empfehlung) oder „EUR mit festem Kurs“. |
| Akzentfarbe im Studio | Das Studio-Blau erreicht als Textfarbe auf getönten Flächen nur 4,15:1 statt 4,5:1. | **Entschieden 2026-10-15 (Nutzer): ja, umgesetzt** — `--st-accent: #1b64d9` nur im Studio (Paket 11); die Widget-Markenfarbe bleibt. |
| Werkzeug-Ablehnungen im Log | Lehnt der MCP-Server einen Aufruf ab, steht das als ERROR im Log. Als WARNING gäbe es weniger Alarm, aber auch echte edu-sharing-Ausfälle, die der Server so meldet, wären dann nur noch WARNING. | „ERROR lassen“ (Empfehlung) oder „senken“. |
| GV-RED-1 | Ein Golden-Testfall nimmt real Inhalte auf Staging auf. Die Vergleichs-Matrix lässt ihn schon weg, ein Einzellauf muss ihn abwählen. | „Im Standard-Set lassen“ oder „nur noch auf Abruf“. |
| Moderations-Schwellen | In Live-Tests ergaben Andeutungen Werte unter der Schwelle (`self_harm` 0,50): „Abschiedsbrief geschrieben“ 0,45, „Schluss machen, endgültig“ 0,28. Die Moderation löste deshalb keine Schutzantwort aus. | „Schwellen senken“ (mehr Schutz, auch mehr Fehlalarme) oder „lassen“. |
| B-API-Moderation | Ob die B-API die Moderation mit dem Bearer-Schlüssel allein annimmt, ist unklar. Sonst läuft sie dort still ins Leere. Gegen die B-API darf ich nicht testen. | Eine Prüfung durch dich: B-API-Doku, Ansprechperson oder das Log auf Moderationsfehler. |
| Studio-Startpaket | Das Studio lädt beim Start beide Sprachen (1,09 MB nach Paket 6, vorher 1,08 MB; Budget-Warnung bei 1,1 MB). Englisch erst beim Umschalten zu laden, hieße jeden Katalog-Teil auf zwei Dateien zu verteilen; heute stehen beide Sprachen bewusst nebeneinander. | „Aufteilen“ (spart rund 200 kB) oder „lassen, solange das Budget hält“ (Empfehlung). |
| Policy-Regel bei Zeitüberschreitung | Eine Policy-Regel prüft die Nachricht mit einem Ausdruck aus dem Studio, höchstens 0,05 s lang (Paket 6). Läuft die Zeit ab, gilt das heute als „trifft nicht“ — eine sperrende Regel (Werkzeug sperren, Pflicht-Hinweis) greift dann nicht. Auslösen kann das nur ein ungünstiger Ausdruck aus dem Studio zusammen mit einer passend gebauten Nachricht. | „So lassen“ (Empfehlung: die Zeitgrenze ist der Schutz, ein Fehlalarm an harmlosen langen Nachrichten wäre spürbarer) oder „bei Zeitüberschreitung die Wirkung anwenden“. |
| Testinstanz: Skill-Suche | Die Werkzeugliste erwartet `search_skill`, der installierte MCP-Server hat die Suche abgeschaltet (`WLO_DISABLE_SKILL_SEARCH`). Die Skill-Suche im Studio scheitert deshalb. | „Werkzeug aus der Liste streichen“ oder „Suche am Server einschalten“. |

## Kein Entscheid nötig

- **B1–B3 (Anrede im Code):** erst nach deiner Nachmessung der Agent-Runde 2.
- **Schon erledigt, stand nur noch in der Liste:** Audit 2026-08-12 F-2 (die zwei High-CVEs, behoben am 2026-08-12/13) und F-6 (Persistenz-Reihenfolge, behoben mit `finalize_message`); D-8 ist durch den Bau von ST-1, ST-2, ST-6 und ST-9 erledigt.
