# Plan: Entwurf aus Dokument, Rückkontrolle, Anmelde-Kürzel, Sitzung auf Staging (2026-11-19)

Auslöser: Rückmeldung des Nutzers vom 19.11. (Ablauf „Themenbaum erstellen“, Grundlage Dokument, auf
Staging). Drei Fehlerbilder, zwei Wünsche, eine Frage.

## 1 Befunde (Phase 1 des Debuggens, belegt)

| # | Symptom | Ursache | Beleg |
|---|---|---|---|
| S1 | „Hier im Chat“, ohne Anmeldung: Dokument gelesen, dann „Der Entwurf ließ sich gerade nicht erzeugen …“ | Ein **vorübergehender Fehler des Anbieters** (503) beim Aufruf für Ebene 1 wird zum Sammelgrund `fehler`; dessen Text sagt der KI „Rufe nicht noch einmal auf; antworte ohne Entwurf“ → Sackgasse | Lokal nachgestellt mit `Automobilkaufleute-2016-09-16.pdf` (OpenAI nativ, `gpt-6-luna`): `ServiceUnavailableError`, `grund fehler`, nach 8,6 s; derselbe Aufruf Minuten später ohne Fehler. `gpt-6-luna` läuft über die Responses-Brücke, dort wiederholt das SDK nur 1–2 Mal (`services/llm.py`, Modulkopf). Ob auf Staging genau das geschah, zeigt erst die Spur — die Lücke besteht so oder so. |
| S2 | „In WLO ablegen“, angemeldet: Entwurf „Unterricht planen in der beruflichen Bildung“ ohne Inhalt der PDF | (a) Die PDF ist ein reiner Scan (18 Seiten, 0 Zeichen Text) — WLO hat keinen Volltext. (b) Der KI-Schritt `entwurf_dokument` darf `ui_strukturentwurf` auch **ohne** `aus_dokument` rufen; nach dem Fehlertext entwirft er dann frei aus den Antworten. (c) Der WLO-Weg hat keine Scan-Prüfung: jeder nicht leere Text (Seitenzahlen, OCR-Reste) gilt als Dokument (`services/dokumente/strukturdokument.volltext`). | `scan_text.py`: `zeichen 0, gescannt True`; kein Code erzwingt `aus_dokument` (nur `hinweis` im Seed); `volltext()` prüft nur `.strip()`. |
| S3 | Widget in der Redaktion auf Staging erkennt die Anmeldung nicht | Der Tauschpfad `/edu-sharing/services/boerdi/auth/session` existiert am Repository-Host nicht — edu-sharing selbst antwortet 404. Es gibt **kein Ingress-Template** (nur Werte `sessionIngress` in `deploy/helm/values.example.yaml`, „T6 baut das Chart“). | `…/services/md-editor/` → 200, `…/services/boerdi/auth/session` → 404 (`ErrorResponse{error='404'…}`). Vergleich mit dem md-editor: sein Chart legt zwei Ingress-Objekte am Repository-Host an (`helm/md-collab-editor/templates/ingress.yaml`). |
| S4 (unterwegs) | Entwurf aus Lehrplan-PDFs ist flach (keine Ebene 2) und die obere Ebene erfindet Titel | Die Gliederung findet die Lernfelder nicht als Überschriften (Art `teile`: Seitenstücke); das Modell sieht nur Gliederung + 1500 Zeichen Anfang und antwortet `unterthemen: 0` für jeden Punkt → keine Ebene 2 (`_neu` nimmt nur Punkte mit Plan > 0). | Augenoptiker 2011: drei Läufe flach (5–13 Punkte, 0 Unterpunkte). **Versuch mit dem ganzen Markdown** (Nutzer-Vorschlag): 13 echte Lernfelder, 3–8 Unterpunkte je Punkt, 48 s. |

Frage des Nutzers: OCR für gescannte PDFs im Chat-Weg? → §2, P7.

## 2 Entscheide

- **E1 (Nutzer):** Die Lernfelder erkennt das Modell im Text, keine eigene Überschriften-Erkennung im
  Code. Ebene 1 bekommt das **ganze Markdown**, wenn es höchstens `GANZTEXT_ZEICHEN` (80 000) Zeichen
  hat; darüber bleibt der bisherige Weg (Gliederung + Anfang + Auszüge). Die Grenze wird an den
  Lehrplänen des Nutzers gemessen (P1-0) und dort ggf. angepasst.
- **E2:** Was ganz ans Modell geht, ist vorher moderiert — in Stücken zu 20 000 Zeichen über die
  vorhandene Moderation (`ui_module/dienst._moderation`), parallel, höchstens 4 Stücke. Abgewiesen →
  `abgewiesen`; Moderation nicht erreichbar → `MODERATION_FAILURE_MODE` wie sonst. Für einen
  Chat-Text, dessen Anfang beim Lesen schon geprüft wurde, wird trotzdem das Ganze geprüft (das
  Lesen prüfte nur 4 000 Zeichen).
- **E3:** Vorübergehende Fehler des Anbieters (`ServiceUnavailableError`, `InternalServerError`,
  `APIConnectionError`, `BadGatewayError`, Zeitüberschreitung beim Verbinden) beim Entwurf: **einmal**
  nach 2 s wiederholen, wenn die Frist es erlaubt. Bleibt es dabei → eigener Grund
  `voruebergehend` mit dem Satz „gerade nicht erreichbar — in einem Moment ‚nochmal‘ schreiben“.
  Die KI ruft dann nicht neu auf, der Ablauf bleibt am Schritt stehen (wie `volltext_fehlt`).
- **E4:** Neues Feld am KI-Schritt **`agent.feste_argumente`** (je Werkzeug ein Objekt). Der Server
  setzt diese Argumente in jeden Aufruf des Werkzeugs in diesem Schritt — anders als `vorbelegen`
  geht hier der Ablauf vor der KI. Seed: `entwurf_dokument` → `{ui_strukturentwurf: {aus_dokument:
  true}}`, der Schritt aus Inhalten → `{aus_inhalten: true}`. Damit gibt es dort keinen freien
  Entwurf mehr. Studio-Formular und Prüfung kennen das Feld (nur bekannte Werkzeuge, nur Argumente
  des Werkzeug-Schemas).
- **E5:** Scan-Prüfung im WLO-Weg: nach `bereinigen` gilt ein Volltext mit weniger als
  `KAUM_TEXT_WOERTER` (100) Wörtern als „kein lesbarer Text“ (Grund `not_extracted`, gleiche Texte
  wie heute). Seitenzahlen kennt der WLO-Weg nicht, deshalb Wörter statt Zeichen je Seite.
- **E6:** Ebene 2 aus einem Dokument: meldet das Modell bei **allen** oberen Punkten `unterthemen: 0`,
  gilt das als „nicht angegeben“ — jeder Punkt bekommt `UNTERTHEMEN_OBEN` als Plan. Gilt für den
  langen Weg (über 80 000 Zeichen), wo das Modell nur die Gliederung sieht.
- **E7 (Rückkontrolle, Wunsch):** Der Strukturentwurf aus einem Dokument trägt `gelesen`: je
  Dokument Name, Zeichen, Weg (`ganz`/`gliederung`), die ersten 2 000 Zeichen des gelesenen Texts und
  bis zu 30 Abschnittstitel. Feld `x-nur-system` (die KI setzt es nie). Das Modul zeigt es
  **eingeklappt** unter dem Kopf: „Gelesener Text (Name, 62 600 Zeichen) – anzeigen“. Kein eigenes
  Modul, kein zusätzlicher Zug.
- **E8 (Kürzel, Wunsch):** In der Fußzeile, links vom Anmelde-Knopf, ein Kreis mit den Initialen,
  sobald ein Block da ist (`authButton() === 'signOut'`). Initialen aus dem Anzeigenamen (erster
  Buchstabe des ersten und des letzten Worts, „Jan Schachtschabel“ → „JS“); ohne Namen ein
  Personen-Symbol. `aria-label`/`title` „Angemeldet als …“ bzw. „Angemeldet“. Den Namen bei der
  Anmeldung von Hand liefert der MCP, falls `/auth/status` ihn nennt (P5-0 misst das); sonst Symbol.
- **E9 (Sitzung auf Staging):** Wir liefern das Ingress-Stück selbst, nach dem Vorbild des
  md-editors: ein kleines Chart `deploy/helm/boerdi-session-ingress/` mit einem Ingress am
  Repository-Host (Pfad `Exact`, ohne rewrite, ohne Affinität) und Renderprüfungen. Ziel ist
  entweder ein Service im Cluster (`backend.service`) oder — für den Betrieb mit Docker Compose auf
  einem eigenen Rechner — ein `ExternalName`-Service auf den Chat-Host (`backend.externalName`,
  HTTPS, Host-Kopf des Repositorys bleibt erhalten). Dazu `deploy/compose.session.yml` (zweiter
  Traefik-Router für Host+Pfad des Repositorys, nur wenn eingebunden) und die Schrittliste für
  Staging. `MCP_SESSION_URL` ergibt sich aus Host + Pfad; die Renderprüfung bricht ab, wenn der Pfad
  nicht unter `/edu-sharing/` liegt oder nicht auf `/auth/session` endet.
- **E10 (OCR, Frage):** Es gibt `markitdown-ocr` (Microsoft, MIT): Seiten ohne Text werden als Bild
  an ein Vision-Modell geschickt. Bei uns ginge das über die vorhandene LLM-Route (b-api bzw.
  OpenAI) — die **Seitenbilder** verlassen dann den Server wie heute die Chat-Texte. Lokal ohne
  Datenabfluss ginge RapidOCR (Apache-2.0, nutzt das schon vorhandene onnxruntime), kostet aber CPU
  auf dem 2-Kern-Server. **P7 wird erst gebaut, wenn der Nutzer den Weg wählt**; Vorgabe aus
  (`DOKUMENT_OCR=aus`).

## 3 Pakete und Aufgaben

Je Paket: Schritt 0 `/better-coding-workflow` (+ `/better-coding-frontend` bei UI), Tests zuerst,
danach unabhängiges Review, Behebung, volle Suite, Durchtest gegen Wegwerf-DB, Änderungsnotiz.

### Paket A — Entwurf aus Dokument (P1–P4), ein PR

- **A1 (E3, S1):** `services/strukturentwurf_dienst.py` — `_obere_ebene` und `_Lauf.kinder`:
  vorübergehende Fehler einmal wiederholen (Hilfsfunktion `_voruebergehend(e)` in neuer Datei
  `services/strukturentwurf_wiederholen.py`, prüft die LiteLLM-Klassen), sonst Grund
  `voruebergehend`. `ui_module/dienst_fehler.py`: Text `voruebergehend`. Tests: Attrappe wirft
  einmal `ServiceUnavailableError` → Entwurf entsteht; zweimal → `voruebergehend`, Text an die KI
  ohne „antworte ohne Entwurf“.
- **A2 (E4, S2b):** `services/ablauf/typen.py` (Feld `feste_argumente` am Agent-Teil),
  `services/ablauf/vorbelegung.py` bzw. die Stelle, die `vorbelegt` anwendet (feste Argumente
  zuletzt, überschreiben die KI), `services/ablauf/pruefung.py` (Werkzeug im Schritt, Argumente im
  Schema), Seed `06-ablaeufe/themenbaum.yaml` (+ `themenbaum_aus_inhalten.yaml`), Studio-Formular
  (Schema-getrieben: Feld im Schema). Tests: Aufruf ohne `aus_dokument` im Schritt → Dienst bekommt
  `aus_dokument: true`; Prüfung meldet unbekanntes Werkzeug/Argument.
- **A3 (E5, S2c):** `services/dokumente/strukturdokument.volltext` — `KAUM_TEXT_WOERTER`. Test:
  Volltext „- 1 -\n- 2 -“ → Grund `not_extracted`.
- **A4 (E1, E2, S4):** `services/strukturentwurf_dokument.py` (`GANZTEXT_ZEICHEN`, Aufforderung mit
  `text` statt `anfang`), `services/strukturentwurf_prompt.oben_aus_dokument` (Feld `text`, Satz:
  „Die tragende Ordnung (Lernfelder, Themenfelder, Kapitel) steht im Text, auch wenn die Gliederung
  sie nicht zeigt.“), Moderation des Ganztexts in `ui_module/dienst.py` (vor `erzeugen`, mit
  `_moderation()`), `ungeprueft`-Dokumente ebenso. Tests: Dokument unter der Grenze → Aufforderung
  enthält den ganzen Text, darüber Gliederung + Anfang; Moderation je Stück, abgewiesen → Fehler.
- **A5 (E6):** `services/strukturentwurf_dienst._obere_ebene` — alle `unterthemen` 0 bei Dokument →
  Plan `UNTERTHEMEN_OBEN`. Test.
- **A6 (E7, Wunsch):** Dienst setzt `gelesen`; Manifest `ui-strukturentwurf/manifest.json`
  (`gelesen`, `x-nur-system`), `manifeste.json` neu; Komponente zeigt `<details>` eingeklappt
  (Tastatur, Fokus, de/en). Merken/Vertiefen behalten `gelesen` nicht (nur Anzeige). Tests
  Backend + Spec.
- **A7:** P1-0 Messung: alle Rahmenlehrpläne aus `Downloads/Rahmenlehrpläne-2025` und
  `…/kmk.org-Rahmenlehrpläne` (Zeichen je Datei, Anteil unter 80 000) — Ergebnis in der Notiz.
  Durchtest: Augenoptiker, Automobilkaufleute, ein langer Plan, die Scan-PDF (Chat: „kein Text“;
  WLO-Weg in der Attrappe: `volltext_fehlt_datei`, kein freier Entwurf).

### Paket B — Anmelde-Kürzel und Sitzung auf Staging (P5, P6), ein PR

- **B0:** messen, ob MCP `/auth/status` einen Anzeigenamen liefert (MCP-Repo nur lesend, Staging-MCP
  lesend ohne Anmeldung).
- **B1 (E8):** `frontend/projects/ui/src/session/initialen.ts` (reine Funktion, Tests mit Umlauten,
  einem Wort, leer), Fußzeile in `shell/chat-shell.component.html/.scss`, i18n `auth.signedInAs`,
  Kontrast ≥ 4,5:1, 24×24 px mindestens. Specs.
- **B2 (E9):** `deploy/helm/boerdi-session-ingress/` (`Chart.yaml`, `values.yaml`,
  `templates/ingress.yaml`, `templates/service-external.yaml`, `templates/_helpers.tpl` mit
  Prüfungen, `NOTES.txt` mit der abgeleiteten `MCP_SESSION_URL`), `values-staging.example.yaml`.
  Test: `backend/tests/test_helm_values.py` erweitert — `helm template` ist lokal nicht vorhanden,
  deshalb prüft der Test die Vorlagen als Text (Pfad, `pathType: Exact`, kein `rewrite-target`) und
  die Prüfregeln in `_helpers.tpl`.
- **B3 (E9):** `deploy/compose.session.yml` (Router `boerdi-sitzung`, `SESSION_HOST`),
  `deploy/.env.example` (`SESSION_HOST` optional, leer), `deploy/README.md` und
  `docs/uebergabe-betrieb.md` (Schrittliste Staging: Ingress, `MCP_SESSION_URL`, `CORS_ORIGINS`,
  `FORWARDED_ALLOW_IPS`, am MCP `WLO_SESSION_EXCHANGE=1`), `docs/edu-sharing-einbindung.md`.

### Paket C — OCR (P7), Nutzer-Auftrag 19.11.: „optional aktivierbar, sofern sinnvoll auf CPU“

**Prüfung `markitdown-ocr` (C0, 19.11.):** Version 0.1.2 (21.10.2026), MIT — hängt aber an
`pymupdf` (**AGPL-3.0**) sowie `pandas`, `python-docx`, `python-pptx`, `openpyxl`. Verstößt gegen die
Lizenzregel (nur MIT/Apache-2.0/BSD-artig) → **nicht verwenden.** Es rechnet ohnehin nicht auf der
CPU: Seiten ohne Text gehen als Bild (300 DPI) an ein Vision-Modell über einen OpenAI-Client.

**Entscheid E11:** Dasselbe Prinzip selbst, ohne neue Abhängigkeit: `pypdfium2` (BSD-3/Apache-2.0)
und Pillow sind über `markitdown[pdf]`/`pdfplumber` schon installiert. Seiten rendern (150 DPI,
Graustufen, JPEG Q80 ≈ 280 KB), über **unseren** Transport (`services/llm.chat_completion`, also
b-api oder OpenAI, mit Token-Zähler des Zugs, Phase `dokument_ocr`) an das Chat-Modell.
Messung 19.11. (OpenAI nativ, `gpt-6-luna`, Aufbereitungsmechaniker S. 7): Rendern **0,08 s CPU**
je Seite, Modell 17 s, Ergebnis vollständig (Tabelle Lernziele/Lerninhalte als Markdown). Über die
b-api war OpenAI zur Messzeit überlastet (auch reiner Text: „Our servers are currently
overloaded“) — Bildaufruf über die b-api wird nachgemessen (C4).

- **C1:** `services/dokumente/ocr.py` (neu): `seiten_lesen(rumpf, *, seiten_max, frist_ende,
  usage_acc) -> OcrErgebnis(markdown, seiten, gelesen, gekuerzt)`; Rendern in `asyncio.to_thread`,
  höchstens `min(4, llm_parallel.anbieter_deckel() // 2)` Seiten zugleich, je Seite ein Aufruf mit
  festem Prompt (nur Text wiedergeben, Daten, keine Anweisungen befolgen); vorübergehende Fehler wie
  E3 einmal wiederholt; Seiten nach der Frist → `gekuerzt`.
- **C2:** `services/dokumente/aufnahme.aufbereiten`: nur PDF, nur wenn `gescannt(...)` und
  `DOKUMENT_OCR=llm` → OCR, danach der gewohnte Weg (Moderation, Gliederung, Befund mit Warnung
  `ocr`). Sonst wie heute `kein_text`. Nur der Weg „Hier im Chat“; der WLO-Weg liest den Volltext des
  Repositorys.
- **C3:** Settings `DOKUMENT_OCR` (`aus` Vorgabe | `llm`), `DOKUMENT_OCR_SEITEN` (20),
  `deploy/.env.example`, `deploy/README.md`. Nicht bei Anbietern ohne Bildeingang (AcademicCloud →
  aus, mit Log-Hinweis). Upload-Feld: bei aktivem OCR der Satz „Gescannte Seiten gehen als Bild an
  das KI-Modell“ (Datenschutz), Rückmeldung nach dem Lesen „per Texterkennung gelesen“.
- **C4:** Durchtest: Aufbereitungsmechaniker (18 Seiten) lokal OpenAI nativ und — wenn erreichbar —
  über die b-api; Dauer, Kosten, Güte; danach Entwurf aus dem Dokument.

## 4 Nicht im Umfang

- Eigene Erkennung von Lernfeld-Überschriften (E1).
- Halten des Cookies im Server wie beim md-editor — wir tauschen einmal beim MCP (Plan 2026-11-15).
- Istio-Variante des Ingress (Staging nutzt nginx); bei Bedarf später nach dem md-editor.
- Das vollständige Chart des Chatbots (Team 6).

## 5 Abnahme

- S1: Attrappe mit einer 503 → Entwurf entsteht; mit zwei → Satz „gleich nochmal“, Ablauf bleibt am
  Schritt. Durchtest lokal mit Automobilkaufleute.
- S2: Scan-PDF im WLO-Weg → kein Entwurf, Satz „kein lesbarer Text“; Aufruf der KI ohne
  `aus_dokument` im Dokument-Schritt erreicht den Dienst mit `aus_dokument: true`.
- S3: Chart rendert mit Staging-Werten einen Ingress `Exact` auf den Pfad; Renderprüfung bricht bei
  falschem Pfad ab; Schrittliste vollständig. Abnahme auf Staging macht der Betrieb (Nutzer).
- S4: Augenoptiker und Automobilkaufleute → Lernfelder als obere Ebene, je Punkt ≥ 3 Unterpunkte.
- Rückkontrolle: eingeklappt, per Tastatur aufklappbar, zeigt Name, Zeichen, Anfang.
- Kürzel: „JS“ bei „Jan Schachtschabel“, Symbol ohne Namen, nicht sichtbar ohne Anmeldung.
- Volle Suite, Frontend-Tests, CI grün.

## 6 Nachträge aus dem Review von Paket A (2026-11-19)

- **E1a (Anker, Review A MAJOR 3):** Auf dem Weg „ganz“ liefert Ebene 1 je Punkt `anker` — die
  ersten 3–8 Wörter der Überschrift des Lernfelds/Kapitels, wörtlich wie im Text. Der Code sucht
  den Anker nur (keine eigene Überschriften-Erkennung, E1 bleibt): ohne Groß/klein, Leerraum und
  Satzzeichen normalisiert, Trennungen am Zeilenende beachtet; findet er den ganzen Anker nicht,
  den längsten Anfang mit mindestens 3 Wörtern (gemessen: eine zweite Spalte mitten im Titel); steht
  er mehrmals, gilt seit dem zweiten Review (MAJOR 1) die **Reihenfolge der Punkte**: die
  aufsteigende Kette über die Fundstellen aller Anker (längste aufsteigende Teilfolge in
  Modellreihenfolge), die die meisten Punkte abdeckt, erst bei Gleichstand die größte Summe der
  Längen; Punkte ohne Platz in der Kette → Rückfall. (Vorher gewann die längste Stelle — oft die
  letzte Erwähnung, das Beispiel-Lernfeld der Lesehinweise.) Mindestens 3 Wörter.
  Die Stelle gehört dem Lauf, nicht dem Block. Auszug für Ebene 2 = vom Anker bis zum nächsten
  Treffer eines anderen Ankers (nicht nur des gewählten), höchstens 12 000 Zeichen. Den Weg „ganz“
  gibt es nur mit der Zusage des Aufrufers, dass der ganze Text moderiert ist
  (`erzeugen(ganz_moderiert=True)`); die Moderation ist an die Frist gebunden. Nicht gefunden → Text der
  Abschnitte mit `min(DOKUMENT_AUSZUG × n_am_selben_abschnitt, 24 000)`. Auf dem Weg „ganz“ ist der
  Text schon moderiert — die Auszugs-Moderation entfällt dort. Umsetzung
  `services/strukturentwurf_anker.py`.
- **E2a (Moderation, Review A MAJOR 2):** ein Platz je Entwurf — die Stücke gehen nacheinander;
  Stückgröße = was die Moderation in einem Aufruf ganz prüft (8 × 3 800 + 200 ≈ 30 600 Zeichen, 200
  Überlappung); `teilweise` gilt als kein Urteil. 100 000 Zeichen sind vier Aufrufe.
- **E4a (Review A MAJOR 1):** feste Argumente gelten nur für neue Entwürfe, nicht mit `vorlage: true`.
- **E5a (Review A MINOR 7):** Scan-Prüfung: weniger als 30 Wörter oder weniger als 30 % Buchstaben
  (ohne Leerraum) → `not_extracted`.
- **E6a (Review A MINOR 5):** `unterthemen: 0` gilt je Punkt als „nicht angegeben“, wenn der Punkt
  Text hat (Abschnitte; seit E1c auf dem Weg „ganz“ jeder Punkt) — nicht erst, wenn alle 0 melden.
- **GANZTEXT_ZEICHEN = 100 000** nach der Messung P1-0 (15 von 20 Plänen statt 13).
- **E1b (drittes Review A, ersetzt die Kettenwahl aus E1a):** einfache gierige Regel.
  Fundstellen je Anker: alle Anfänge von voll bis 3 Wörter, je Stelle der längste; ein verkürzter
  Anfang zählt nur mit höchstens 5 Treffern oder mindestens der Hälfte der Wörter; höchstens 20
  Stellen je Anker (mehr = mehrdeutig, keine Stelle) und 300 insgesamt; Treffer am Zeilenanfang
  gehen vor (Querverweise mitten im Text zählen dann nicht). Wahl in Modellreihenfolge: für Punkt i
  die FRÜHESTE Fundstelle hinter dem vorigen platzierten Punkt, deren Auszug (bis zum nächsten
  Treffer irgendeines anderen Ankers) mindestens 300 Zeichen hat; keine solche Stelle → Rückfall
  (zählt für den nächsten Punkt nicht). Ergänzt: hat der Punkt eine solche Stelle vor dem vorigen,
  an der nur sein Anker trifft, steht er außer der Reihe → Rückfall (sonst landete er auf einem
  späten Beispiel). Prompt: „Punkte in der Reihenfolge des Texts“. Läuft die Moderation des ganzen
  Texts im Modus `open` ab, gilt der Weg „gliederung“; die Moderation endet dafür 20 s früher.
- **E1c (viertes Review A, ersetzt E1a und E1b; Nutzervorgabe E1):** keine Anker, keine Suche im
  Code. Auf dem Weg „ganz“ (moderiert, `ganz_moderiert=True`, Text ≤ `GANZTEXT_ZEICHEN`) bekommt
  auch jeder Aufruf für Ebene 2 den ganzen Text; das Modell findet den Abschnitt seines Punkts selbst
  („Fülle nur diesen Punkt aus; die Inhalte stehen im Dokument, meist unter seiner Überschrift;
  Geschwister nicht“). Nachrichten von Ebene 2: Systemteil und Dokument byte-gleich für alle Punkte,
  danach die Aufgabe des Punkts. Gemessen trifft der Cache nur am Ende des Systemteils oder am Ende
  eines früheren Prompts — deshalb vorher ein Vorwärm-Aufruf mit genau `[Systemteil, Dokument]`,
  danach alle Punkte parallel (86–92 % der Eingabe gecacht). Moderation ohne Urteil oder
  Fristablauf im Modus `open` → Weg „gliederung“. Der Weg „gliederung“ bleibt unverändert.
