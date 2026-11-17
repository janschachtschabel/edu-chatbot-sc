# Durchtest TG-7: Ablauf „Themenbaum erstellen“ (2026-11-16)

Plan: `docs/plans/2026-11-16-themenbaum-generisch.md`, Paket TG-7. Geprüft wurde jede Option des
Ablaufs `06-ablaeufe/themenbaum` im Chat, auf API-Ebene (so, wie das Widget die Anfragen schickt),
nicht im Browser.

## Aufbau

- **Backend:** Staging-Kopie, lokal auf Port 8107, gegen die Wegwerf-DB `boerdi_durchtest_tg7`
  (angelegt und migriert über `tests/pg_utils`, `import-config` mit den Seeds ab Werk; das
  Startskript bricht ab, wenn `DATABASE_URL` nicht auf die Wegwerf-DB zeigt). Engine `agent` (Seed).
- **LLM:** nativ OpenAI (`LLM_PROVIDER=openai`, `gpt-6-luna` aus `.env`).
- **Master-Skill:** die lokale Datei `docs/skills/vorgehen-knapp.md` (sie nennt schon „Themenbaum
  erstellen“; die Fassung im Repositorium ist älter).
- **MCP:** der Standard-Server (`wlo-mcp…nip.io`, Version 1.4.0), Repository Staging.
- **Anmeldung (Optionen 2b, 3b, 4c):** wie das Widget. Testkonto per Basic-Auth gegen
  `repository.staging.openeduhub.net` (`/iam/v1/people/-home-/-me-`), das Sitzungs-Cookie blieb im
  Speicher. Danach `POST /auth/session` am MCP mit `Origin` des Repositorys und dem Cookie. Den Block
  bekam der Chat als Kopfzeile `WLO-Access-Block`. Die Zugangsdaten gingen nie an das MCP.
- **b-api-Schlüssel:** `B_API_KEY_STAGING` als `Authorization: Bearer …` am Chat und an den
  Ablage-Endpunkten (wie der b-api-Proxy, `turn_auth.uebernimm_llm_schluessel`).
- **Upload-Antworten:** nach Manifest `ui-upload` gebaut (`struktur` mit `dateiliste` je Ordner, `i`
  tiefe-zuerst, `zahlen`, `strukturdokument`, `warnungen`, ggf. `dokument`/`dokumente`/`ablage`).
  Dokumente über `POST /api/ui/dokumente`, Ablage über `/api/ui/ablage/{vorbereiten,datei,abschluss}`.
- Teile und Entwürfe wurden aus der Wegwerf-DB gelesen (`vorgaenge`, `vorgang_ablage`).
- Keine Geheimnisse, Cookies oder Blöcke in Logs oder hier.

## Ergebnis je Option

| Option | Ergebnis |
|---|---|
| 1 Thema, anonym (Text und Knopf) | teilweise — Entwurf richtig, Ende nur über eine im Widget unsichtbare Aktion (M1) |
| 2a Ordner, anonym, Inhalte gemerkt | ok („So lassen“); „Verfeinern“ teilweise (M1, m2) |
| 2b Ordner, angemeldet, erschlossen | teilweise — Ablage, `metadaten_lesen`, node_ids ok; Kestra-Start abgewiesen (B1) |
| 3a Lose Dateien, anonym, schnell | teilweise — Weg ok, Krisenhinweis ok; M1, m1 |
| 3b Lose Dateien, angemeldet, gründlich | teilweise — Ablage ok; Kestra abgewiesen (B1); Entwurf schwach (m4) |
| 4a Ein Strukturdokument, anonym | ok (m1) |
| 4b Zwei Strukturdokumente, anonym | ok (m1) |
| 4c Strukturdokument, angemeldet (WLO) | ok; `volltext_fehlt` verständlich, aber bei Scans irreführend (m3) |
| 5 Anonym hochladen, frei weiterarbeiten | fehlgeschlagen — die KI kann das gelesene Dokument nicht nutzen (M2) |
| 6 Gegenproben | ok |

### 1 Themenbaum aus Thema (anonym)

**1A, Start per Text** „Ich möchte einen Themenbaum zu Optik für Klasse 7“:
- Weg: KI-Zug mit `direkt_start` (10–14 s), das Widget drückt „Themenbaum erstellen“, dann
  Einstieg „Ja, neue Struktur“, Grundlage getippt „Optik für Klasse 7“, „Unterricht planen“
  (Chip), Stufe getippt „Klasse 7“, „Ausführlich (3 Ebenen …)“ (Chip), Hinweis getippt „ohne
  Atomphysik“, „Entwurf erstellen“, Übernehmen.
- Zeiten: 10 Züge, 103 s; der Entwurf 42 s, der zweite KI-Zug nach dem Übernehmen 47 s (M1).
- Teile: `bereit`, `vorhaben`, `grundlage`, `zweck`, `stufe` („Klasse 7“), `umfang`, `hinweise`,
  `draft` (`wlo.sammlungsstruktur@1`, wegen der Größe als Verweis in `vorgang_ablage`).
- Entwurf: Thema „Optik für Klasse 7“, Stufe „Sekundarstufe I“ (aus „Klasse 7“ abgeleitet), 66
  Punkte, **3 Ebenen**, 10 oben, z. B. „Lichtquellen und beleuchtete Körper“, „Lichtausbreitung“,
  „Schatten“, „Reflexion“, „Brechung“. **Kein Punkt zu Atomen** — Umfang, Stufe und Hinweis kommen an.
- Leiste: 1/15 2/15 3/8 4/8 5/7 6/7 7/7 7/7 7/7.

**1B, Start per Knopf** (`ablauf_starten {ablauf: themenbaum}`):
- Weg: Grundlage „Optik“, Zweck getippt „für eine Webseite“, „Sekundarstufe I“, „Kompakt“, „Nein,
  weiter“, Entwurf, Übernehmen.
- Zeiten: 9 Züge, 15 s.
- Entwurf: 6 Punkte, 1 Ebene („Licht und Ausbreitung“, „Reflexion“, „Brechung“, „Linsen“, „Auge und
  Sehen“, „Licht und Farben“). „Kompakt“ wirkt.
- Mit „Weiter im Ablauf“ (Direktaktion) Ende „Dein Themenbaum-Entwurf ist gespeichert …“, Chips
  „Neues Vorhaben“, „Arbeitsstand löschen“. Ein getipptes „weiter“ ergab nur einen weiteren Entwurf.

### 2 Nach Ordnerstruktur

**2a anonym, Inhalte gemerkt** — Auswahl „Physik“: Unterordner Optik (3 Dateien), Mechanik (2),
Elektrizitaetslehre (1) mit Unterordner Schaltungen (2); dazu eine Datei in der Wurzel und eine
ignorierte Datei.
- Weg A: Wendung „Themenbaum aus meinen Ordnern“, „Ja“, „Meine Ordner“, Upload-Feld (Antwort
  `erfasst`), Prüfpunkt (`ui_strukturentwurf`), Übernehmen, getippt „Passt so“ (Hinweis „Bitte
  wähle einen der Knöpfe.“), „So lassen“, Ende.
- Zeiten A: 7 Züge, 3 s (ohne KI).
- Teile: `structure`, `struktur`, `draft`, `ordnerweg`.
- Entwurf A: „Physik“, 4 Punkte, 2 Ebenen. `inhalte` je Punkt: Optik 3, Mechanik 2,
  Elektrizitaetslehre 1, Schaltungen 2 (8 von 9 Inhaltsdateien; die Datei in der Wurzel hat wie
  geplant keinen Punkt, die ignorierte fehlt).
- Leiste A: 1/15 2/15 3/15 4/11 5/11 5/11.
- Weg B: wie A bis zum Prüfpunkt, dann „Mit deinen Angaben verfeinern“, „Unterricht planen“,
  „Sekundarstufe I“, „Mittel“, Hinweis getippt „Experimente nicht vergessen“, „Entwurf verfeinern“,
  Übernehmen, „Weiter im Ablauf“ (Direktaktion).
- Zeiten B: 13 Züge, 26 s.
- Entwurf B: 12 Punkte, 2 Ebenen; die Ordner bleiben oben, darunter z. B. „Lichtausbreitung“,
  „Lichtbrechung“, „Kräfte“. Die `inhalte` bleiben an den Ordner-Punkten. „Experiment“ kommt vor.
  Ohne `bildungsstufe` und `thema` (m2).
- Leiste B: 1/15 … 10/10, nie rückwärts.

**2b angemeldet, Inhalte erschlossen** — eigener Ordner „boerdi-durchtest-1611-Physik“ mit 3
Markdown-Dateien in 2 Unterordnern.
- Weg: Upload-Feld zeigt `ablage_in_wlo: true`. Ablage: vorbereiten 3,1 s (Layout `flach`, die
  Dateien liegen direkt im persönlichen Bereich), 3 Dateien je ~3 s `stored`, Abschluss 2,4 s
  (`vorgang.json` abgelegt), gesamt 15 s. Danach Antwort `uebertragen`, Rückfrage „Soll WLO
  Metadaten … erzeugen?“, „Ja, Metadaten erzeugen“.
- **Der Kestra-Start scheitert sofort** (B1), der Ablauf geht zu `ohne_metadaten`.
- Weiter über „Angaben aus WLO lesen“: `metadaten_lesen` 2 s → Teil `metadaten` mit 3 Einträgen
  (nur Titel = Dateiname, keine Lizenz, kein Fach) → Entwurf aus den Ordnern → Prüfpunkt → „So
  lassen“ → Ende.
- Teile: `ablage` (mit `block_id` = `struktur.block_id`), `metadaten`, `structure`, `struktur`,
  `draft`, `ordnerweg`.
- Entwurf: „boerdi-durchtest-1611-Physik“, 2 Punkte, 1 Ebene (Optik, Mechanik). **Je Datei
  `node_id`** (3 von 3).
- Leiste: 1/15 2/15 3/15 4/13 5/13 6/13 7/13.

### 3 Aus loser Inhaltsmenge

**3a anonym, schnell über die Dateinamen** — 10 Dateien (Brüche, Dezimalzahlen, Prozente, Zinsen,
eine ignorierte, eine mit Krisenwort im Namen).
- Weg: Wendung „Themenbaum aus meinen Dateien“, „Ja“, „Meine Dateien“. Satz „Ich nehme nur die
  Dateinamen …“ steht mit dem Upload-Feld zusammen. Antwort `erfasst`, dann `inhalte_aus_dateien`,
  „Material finden“, „Sekundarstufe I“, „Alles, was zum Stoff gehört“, „Mittel“, „Nein, weiter“,
  Entwurf, Übernehmen, Weiter (Direktaktion).
- Zeiten: 12 Züge, 34 s (Entwurf 21 s).
- Teile: `metadaten` (9 Einträge, Titel aus dem Namen, „Ordner: Mathe-Material“), `struktur`,
  `structure`, `soll_ist`, `draft`.
- Entwurf: „Zahlen und Rechnen“, 12 Punkte, 2 Ebenen, 5 oben („Bruchrechnung“, „Dezimalzahlen“,
  „Prozentrechnung“, „Zinsrechnung“, „Verhältnisrechnung“ — Soll ergänzt). Thema ein Platzhalter
  (m1), `quelle: dokument`, keine Dateien je Punkt (n3).
- Leiste: 1/15 2/15 3/13 4/9 … 9/9.

**3b angemeldet, gründlich über WLO** — 3 Markdown-Dateien zur Biologie.
- Weg: „Meine Dateien“, Frage „Soll WLO deine Dateien gründlich beschreiben?“ (`wlo_erschliessen`
  ja), „Gründlich über WLO“, Ablage 13 s (3 × `stored`, `vorgang.json`), `uebertragen`, Rückfrage,
  „Ja, Metadaten erzeugen“. **Kestra-Start abgewiesen** (B1).
- Weiter über „Angaben aus WLO lesen“, dann Zweck, Stufe, „Nur, was meine Dateien abdecken“,
  „Mittel“, „Nein, weiter“, Entwurf.
- Zeiten: 15 Züge, 30 s, dazu die Ablage.
- Teile: `weg`, `ablage`, `metadaten` (nur Titel), `soll_ist`, `draft`.
- Entwurf: **1 Punkt, 1 Ebene** („Pflanzenbau und Energiegewinnung“, m4). Lizenz, Fach und
  Schlagworte aus Kestra ließen sich nicht prüfen.
- Leiste: 1/15 2/15 3/14 … 12/12.

### 4 Aus Strukturdokumenten

**4a anonym, ein Dokument** (eigener Markdown-Lehrplan, 3 Lernfelder mit je 4 Punkten und ein
Abschnitt „Hinweise zur Leistungsbewertung“).
- Weg: Wendung „Themenbaum aus meinem Lehrplan“, „Ja“, „Ein Dokument mit Gliederung“, Upload-Feld
  mit `einzeldatei_als_struktur`, Lesen über `/api/ui/dokumente` (0,3 s), Antwort `dokument`,
  Fragen, Entwurf, Übernehmen. Die KI gab hier selbst „Weiter im Ablauf“ als Chip.
- Zeiten: 11 Züge, 22 s.
- Teile: `document`, `strukturdokument` (Quelle `chatbot`), `struktur`, `structure`, `draft`.
- Entwurf: 16 Punkte, 2 Ebenen, 3 oben („Betrieb und eigene Rolle“, „Arbeitsplätze ausstatten“,
  „Clients vernetzen“), Fundstelle je Lernfeld. Die Leistungsbewertung wird kein Punkt. Thema
  falsch (m1).
- Leiste: 1/15 2/15 3/9 … 8/8.

**4b anonym, zwei Dokumente** (Biologie, Chemie):
- Weg: freie Bitte „Ich möchte einen Themenbaum erstellen“, die KI startet direkt. Zwei Lesungen,
  Antwort mit `dokument` und `dokumente`.
- Zeiten: 12 Züge, 36 s.
- Teil `strukturdokument` mit 2 Einträgen.
- Entwurf: 24 Punkte, 2 Ebenen, 6 oben, Fundstellen „Lehrplan-Biologie-Sek1.md › Themenfeld 1 …“,
  Abschnitte `d1-a2` … `d2-a4`. Thema = „Unterricht planen“ (m1).

**4c angemeldet, über die Ablage (Rolle Struktur), Volltext über die node_id** — drei Läufe:
- **Markdown:** Ablage 1 Datei, Teil `strukturdokument` mit Quelle `wlo` und node_id. Entwurf 19 s
  nach der Ablage, Volltext über `get_wlo_content_text` (825 Zeichen). Entwurf: 15 Punkte, 2
  Ebenen, 3 Lernbereiche mit Fundstellen. Gesamt 39 s.
- **PDF mit Text:** Volltext am Knoten sofort da (272 Zeichen), Entwurf 12 Punkte, 2 Ebenen. Alle 3
  Fundstellen lauten gleich „Teil 1: …“ (n1). Gesamt 28 s.
- **PDF ohne Textschicht (wie ein Scan):** `volltext_fehlt`. Antwort: „WLO erzeugt gerade noch den
  Volltext deiner Datei „…“. Versuch es in einigen Minuten noch einmal …“. Verständlich, aber hier
  falsch: der Text entsteht nie (m3). Kein Entwurf, der Lauf wartet am KI-Schritt.
- Ein echtes „noch nicht erzeugt, später da“ ließ sich nicht herstellen: Markdown und Text-PDF
  hatten den Volltext nach höchstens 20 s.
- Leiste je Lauf: 1/15 2/15 3/9 … 8/8.

### 5 Anonym hochladen und weiterverwenden

- Weg: „Ich möchte dir ein Arbeitsblatt hochladen …“. Die KI zeigt `ui_upload` (Hinweis
  „Arbeitsblatt als PDF, Word- oder Textdatei“). Lesen 0,4 s. Antwort `dokument`: „Das Arbeitsblatt
  … ist jetzt eingelesen. Welche Fragen hast du dazu?“, Chips „Erklär mir den Wasserkreislauf
  daraus“ und „Erstelle Fragen zum Arbeitsblatt“.
- Frage nach den vier Stationen: „Ich sehe hier nur den Dateinamen, nicht den Inhalt … lade das
  Arbeitsblatt noch einmal hoch.“ Ebenso bei der Musterlösung zu Aufgabe 2 (M2).
- Teile: `document`, `strukturdokument`, `struktur`, `structure`. Kein Lauf. **Kestra-Aufträge der
  Sitzung: 0**, keine Umwandlung außerhalb des Chatbots.

### 6 Gegenproben

- **„Anderes wählen“ mit vorhandenen Daten** (Sitzung aus 5): Start per Knopf. „Du hast schon das
  Dokument „Wasserkreislauf-Arbeitsblatt.md“ bereitgestellt. Soll ich das verwenden?“ — „Anderes
  wählen“ verwirft `document`/`structure`, `bereit` bleibt. Grundlage getippt „Wasserkreislauf“,
  Entwurf 6 Punkte, 1 Ebene, Stufe „Primarstufe“. Ok.
  - Angemeldet hängen die Daten an der Person: Eine neue Sitzung desselben Kontos bot die Ordner
    bzw. Dateien des vorigen, schon beendeten Laufs an (G-E6, n4).
- **Getippte Antwort an einer Knopf-Frage:** „Passt so“ bei „So lassen / Verfeinern“ → „Bitte
  wähle einen der Knöpfe.“, die Knöpfe bleiben, die Leiste bleibt bei 5/11. Ok.
- **Krisenwort im Dateinamen** („boerdi-durchtest-1611-Suizid-Praevention.md“, nur als Name in 3a):
  Upload und Teile bleiben, der Ablauf geht weiter. An die Antwort ist angehängt: „Falls dich das
  Thema gerade selbst betrifft: Die Telefonseelsorge … 0800 111 0 111, 0800 111 0 222 oder 116 123.“
  Ok.
- **Leiste:** In allen Läufen nie rückwärts, `von` steigt nie (15 → 13/11/9/8/7, dann fest). Ok.

## Befunde

### MAJOR

- **M1 — Nach dem KI-Entwurf kommt die Person nicht zum Ende des Ablaufs.**
  - Nach „Entwurf erstellen“ stehen keine Chips unter der Antwort, auch nicht „Weiter im Ablauf“.
    Ursache: `services/turn_assembly.py:438` hängt `_weiter` nur an, wenn `_qr_mode != "none"`; im
    Agent-Muster gilt `mode=none` (Log „quick_replies: mode=none (pattern AGENT)“).
  - Nach „Übernehmen“ ruft die KI in 7 von 10 Läufen `ui_strukturentwurf` erneut auf. Es erscheint
    ein zweiter offener Entwurf, der Lauf bleibt `wartet_ki` (1A: 47 s). Der Hinweis „Sonst
    ui_strukturentwurf“ in `seeds/06-ablaeufe/themenbaum.yaml` (`entwurf_thema`, ähnlich
    `entwurf_inhalte`/`entwurf_ordner`) begünstigt das.
  - Ein getipptes „weiter“ ergibt nur noch einen Entwurf. Ende („Dein Themenbaum-Entwurf ist
    gespeichert …“) nur über die Direktaktion `ablauf_weiter`, die das Widget hier nicht zeigt. In
    3 Läufen (4a, 4b, 4c) gab die KI zufällig selbst einen Chip „Weiter im Ablauf“.
  - Der Entwurf ist nach „Übernehmen“ gespeichert (Teil `draft`) — es geht nichts verloren, aber
    der Lauf bleibt offen (Leiste „wartet auf die KI“).
  - Schon im Durchtest vom 12.11. sichtbar (Chips leer nach dem Entwurf).
- **M2 — Ein anonym gelesenes Dokument ist im freien Chat für die KI nicht nutzbar.**
  - Der Rahmen sagt „den Text hat das System, nicht du“ (`ui_module/upload_antwort.py`,
    `DOKUMENT_FRAME_START`, `_DOKUMENT_BEREIT`). Den Text liest nur `ui_strukturentwurf`
    (`services/tool_loop_module.py:136`, `DOKUMENT_LADER_KEY`); im freien Chat gibt es kein
    Werkzeug dafür.
  - Folge: Die KI bietet „Erklär mir den Wasserkreislauf daraus“ an und rät danach, das Dokument
    „noch einmal hochzuladen“ — beides führt ins Leere.
  - Der Plan (TG-7, Punkt 5) erwartet „frei im Chat damit arbeiten“; G-E3 verschiebt nur „zu einem
    neuen Inhalt verarbeiten“.

### Blocker außerhalb des Chatbots

- **B1 — Kestra-Auftrag:** Die b-api antwortet auf den Start von
  `edusharing.chatbot/node-metadata-write` mit **403 `EDU_USER_NOT_VERIFIED`**.
  - Nachgestellt mit demselben Schlüssel und `X-Edu-User-Id` = Benutzername des Testkontos; auch der
    lesende Endpunkt `/api/v1/edu-sharing/repo/nodes/{id}` antwortet so. Am 08.11. gab er noch 200.
  - Der Schlüssel selbst gilt (`GET /api/v1/jobs` 200).
  - Die b-api verlangt jetzt offenbar eine Verifizierung der Person. Das muss das b-api-Team klären
    (K18).
  - Folge: Der Weg „Kestra-Metadaten → `metadaten_lesen` → Entwurf mit Lizenz, Fach, Schlagworten“
    ließ sich nicht prüfen. Der Ersatzweg über `ohne_metadaten` funktioniert.

### MINOR

- **m1 — `thema` im Entwurf ist auf den Dokument- und Datei-Wegen falsch oder ein Platzhalter:**
  - 4a „Unterrichtsplanung aus dem gelesenen Dokument“;
  - 4b, 4c (md und pdf) „Unterricht planen“ (das ist der Zweck);
  - 3a „Thema der bereitgestellten Dateien“;
  - 3b „Unterrichtsplanung anhand der bereitgestellten Dateien“.

  Die Vorbelegung setzt `thema` nur aus einer getippten Grundlage
  (`services/ablauf/vorbelegung.py:185`). Vorschlag: `thema` aus dem Dokumentnamen bzw. dem Namen
  der Auswahl vorbelegen.
- **m2 — Der verfeinerte Ordner-Entwurf (2a-B) hat weder `bildungsstufe` noch `thema`,** obwohl
  „Sekundarstufe I“ gewählt war (G-E8); auf dem Thema-Weg sind beide gesetzt. Der Weg mit `vorlage`
  übernimmt den Kopf der Vorlage (`ui_module/dienst.py`, Zweig `vorlage`).
- **m3 — `volltext_fehlt` bei einem Dokument ohne Textschicht:** Das MCP meldet `not_extracted`,
  `ui_module/dienst.py:239` (`_volltext_satz`, `SPAETER`) macht daraus „in einigen Minuten noch
  einmal“. Bei einem Scan entsteht der Text nie, und die Person wartet umsonst. Vorschlag: nach
  einer Frist seit der Ablage (Teil `ablage`) einen anderen Satz nehmen („enthält keinen lesbaren
  Text, etwa ein Scan“).
- **m4 — Ein kleiner Bestand mit „Ist“ ergibt einen Baum mit einem Punkt** (3b: 3 Dateien,
  „Mittel“ → 1 Punkt, 1 Ebene, Titel „Pflanzenbau …“ statt Pflanzenbiologie). Die Regeln „jeder
  Punkt von mindestens zwei Materialien getragen“ und „kein Punkt mit nur einem Unterpunkt“
  (`vorgaben` von `entwurf_inhalte`) lassen kleine Mengen zusammenfallen. Möglich wäre eine Ausnahme
  unter etwa 6 Materialien.
- **m5 — Ein abgewiesener Kestra-Start ist schwer zu erkennen.** `auftraege/client._pruefe_antwort`
  macht aus 401/403 `abgewiesen`, ohne den festen Fehlercode der b-api (`EDU_USER_NOT_VERIFIED`) zu
  loggen. Der Text an die Person nennt „nicht eingerichtet, nicht erreichbar oder Anmeldung
  abgelaufen“, nicht „die b-api erkennt deine Anmeldung nicht an“.

### NIT

- **n1:** Fundstelle bei einem PDF aus WLO ohne erkannte Überschriften: alle Punkte zeigen
  denselben „Teil 1: …“ (4c, PDF).
- **n2:** Im Rohtext fester Sätze stehen Markdown-Escapes in Namen
  („boerdi\-durchtest\-1611\-Physik“, `einstieg_mit`). Rendert das Widget Markdown, sieht man sie
  nicht; im Browser nicht geprüft.
- **n3:** Ein Entwurf aus losen Dateien trägt `quelle: dokument` und keine Zuordnung Datei → Punkt.
  Nur der Ordner-Weg hat `inhalte` (TG-3f); fürs spätere Befüllen wäre eine Zuordnung nützlich.
- **n4 (Beobachtung):** Angemeldet bietet ein neuer Lauf die Ordner bzw. Dateien des vorigen,
  beendeten Laufs an, auch in einer neuen Sitzung (G-E6, personengebundener Vorgang). Das ist
  gewollt, wirkt nach „Ende“ aber überraschend.

## Testknoten im Repository (Staging)

- Angelegt: **14 Knoten** im persönlichen Bereich des Testkontos (Layout `flach`, kein Ordner):
  - 9 Dateien mit dem Präfix `boerdi-durchtest-1611-` (7 Markdown, 2 kleine PDF);
  - 5 `vorgang.json` bzw. `vorgang - n.json`, vom MCP beim Abschluss jeder Ablage angelegt.
- Metadaten wurden nicht geschrieben, weil der Kestra-Start abgewiesen wurde.
- **Entfernt: alle 14.** Vor dem Löschen geprüft: Kennung aus dem Teil `ablage` dieser Sitzungen,
  Name mit Präfix bzw. `vorgang*.json`, Ersteller ist das Testkonto, heute angelegt. Gelöscht über
  `DELETE /node/v1/nodes/-home-/{id}?recycle=true` (HTTP 200), also in den Papierkorb des
  Testkontos (die schonendste Art).
- Der persönliche Bereich hat danach wieder dieselben 13 Knoten wie vorher, keinen neuen.
- Lokal: Backend beendet, Wegwerf-DB `boerdi_durchtest_tg7` gelöscht (`pg_utils.drop_db`, keine
  `boerdi_durchtest*` mehr). Andere Container und die Dev-DB wurden nicht angefasst.

## Nicht geprüft

- **Kestra-Metadaten** (2b, 3b), also auch Lizenz, Fach, Stufen und Schlagworte aus WLO und ein
  Entwurf `aus_inhalten` mit diesen Angaben — blockiert durch B1.
- **„Volltext entsteht später und klappt dann“:** nicht herstellbar; Markdown und Text-PDF hatten
  den Volltext sofort.
- **Widget im Browser:** Darstellung, Chips, Leiste und Fortschritt-Modul nur über die
  API-Antworten geprüft.
- **Aufteilen in Blöcke zu 50** und `ui_fortschritt` / „Stand prüfen“: ohne laufenden Auftrag nicht
  erreichbar.
- **Der Master-Skill aus dem Repositorium:** getestet wurde mit der lokalen Fassung
  `vorgehen-knapp.md`.

Hilfsskripte und Protokolle liegen im Scratchpad unter `tg7/` (`lib.py`, `opt*.py`, `lauf_*.log`).

## Behebung (16.11.)

Alle Befunde außer B1 (b-api) behoben, mit den Entscheiden des Koordinators. Ohne neuen Live-Lauf;
geprüft über Tests im Ablauf-Harness, Simulation und Unit-Tests.

- **M1 — Ende nach dem Entwurf:**
  - (a) „Weiter im Ablauf“ steht unter jeder Antwort eines wartenden KI-Schritts, auch im
    Agent-Muster (`mode=none`) und neben Chips des Gastgebers (`turn_assembly`). Knöpfe einer Frage
    und „Stand prüfen“ bleiben an die Grenzen gebunden.
  - (b) „Übernehmen“ im `ui_strukturentwurf` am KI-Schritt mit `ausgabe: draft` setzt den Lauf
    fort — ohne KI-Zug (`ki_schritt.uebernimmt`, `zug.nach_uebernahme`, Preflight). Der Teil wird
    nur in den Vorgang des Laufs gespeichert; eine nur mitgeschickte Fassung bleibt ein
    gewöhnlicher Zug.
  - (c) Die Hinweise der vier KI-Schritte sagen „einmal entwerfen; nach der Übernahme nicht neu
    entwerfen“ (statt „Sonst ui_strukturentwurf“).
- **M2 — gelesenes Dokument im freien Chat:** neues Werkzeug `dokument_lesen`
  (`services/dokument_lesen.py`): Gliederung bzw. Abschnitt (Kennung oder Titel), höchstens 6000
  Zeichen je Aufruf, Moderation wie die Auszüge des Generators (beanstandet → nichts, kein Urteil →
  Ausfallmodus), gerahmt als Daten. Mehrere Dokumente über Name oder Kennung. Nur die Dokumente der
  Sitzung bzw. Person (`alle_fuer_aufrufer`), nur mit Erlaubnis zum Lesen. Angeboten in der
  Agent-Schleife, wenn ein lesbares Dokument da ist — auch am KI-Schritt (virtuell). Rahmen im
  Upload („Fragen zum Inhalt beantwortest du mit dokument_lesen …“), Master-Skill, Werkzeugliste im
  Studio (Sperre „nur mit gelesenem Dokument“).
- **m1 — Thema:** ohne getippte Grundlage aus den Daten — Ordner-Weg: Wurzelordner; Dokument-Weg:
  erstes Strukturdokument ohne Endung; Datei-Weg: keins, dazu in den Vorgaben „Thema aus den Inhalten
  ableiten, nie den Zweck“. Die KI bleibt vorrangig.
- **m2 — verfeinerter Ordner-Entwurf:** Der Kopf der Vorlage bekommt Stufe und Fach des Auftrags und
  ein Thema, wo er keins hat (`strukturentwurf_dienst.erzeugen`).
- **m3 — PDF ohne Text:** Das MCP meldet `not_extracted` für „noch nicht“ und „nie“ (Bild, PDF ohne
  Textschicht) gleich — unterscheiden lässt es sich nicht. Eigener, ehrlicher Satz
  (`volltext_fehlt_datei`): entsteht gerade oder kein lesbarer Text; erst später noch einmal, sonst
  eine Fassung mit Text hochladen. Ein Lesefehler (Frist, Abruf) behält „in einigen Minuten“.
- **m4 — kleiner Bestand:** Soll oder Ist wird jetzt vor dem Entwurf gefragt (`zum_entwurf`, nach den
  Hinweisen). Unter 5 Inhalten statt dessen „Mit so wenigen Dateien wird der Baum sehr klein. Lieber
  nach Stoff (Soll) aufbauen?“ mit „Nach Stoff (Soll)“ / „Trotzdem nur meine Dateien“. Die Vorgaben
  für Ist: mindestens 2 Punkte oben, Einzelkinder vermeiden. Weiter 40 Schritte (`nach_stufe`
  entfiel).
- **m5 — Abweisung der b-api:** Der Code steht im Log, nur aus einer festen Liste
  (`EDU_USER_NOT_VERIFIED`, sonst „unbekannt“). Die Person liest vor dem Ersatzweg „Der Dienst hat den
  Auftrag abgelehnt: Dein Konto ist dort noch nicht freigeschaltet.“ bzw. allgemein.
- **NIT:**
  - n1: Zeigen alle oberen Punkte dieselbe Fundstelle, entfällt sie.
  - n2: geprüft. `entschaerft` landet nur in Texten, die als Markdown gerendert werden (Blase,
    Führung). Die Testvorschau im Studio entfernt die Escapes (`ohneMarkdownEscapes`). Keine
    Änderung.
  - n3: `quelle` aus losen Dateien ist `ki` (das Format kennt `ki`, `wlo`, `ordner`, `dokument`).
    Die Zuordnung Datei → Punkt steht in `offene-befunde-und-todo.md` §1.
- **Offen:** B1 (b-api, K18); `dokument_lesen` im Muster-Weg; ein neuer Live-Lauf der Optionen 1, 2a,
  3a, 3b und 5 nach dem Deploy.
- **Review-Befunde behoben (16.11.):** kein Steuerchip im Krisen- bzw. Drohungszug (`ki_schritt.vorgegeben`, `safety` an `turn_assembly`); Steuerchip hinten, Chips des Gastgebers ungekürzt; `nach_uebernahme` prüft den Schritt; `dokument_lesen` rahmt auch die Gliederung, entschärft die Namen (`rahmen.name_fuer_ki`, auch für `dienst._namen`), merkt sich Antworten je Abschnitt und liest höchstens 6-mal je Zug; ein leerer Entwurf ist keine Übernahme; Seed-Kommentar zur Zählung.

## Zweiter Durchtest (16.11.)

Kurzer Live-Lauf nach der Behebung, wie oben: lokales Backend auf Port 8107, Wegwerf-DB
`boerdi_durchtest_r2`, `gpt-6-luna` nativ über OpenAI, Engine `agent`. Alle Wege liefen ohne Anmeldung.
Skripte `*_r2.py` und Protokolle `lauf_*_r2*.log` liegen im Scratchpad unter `tg7/`.

**Aufbau korrigiert:** Im ersten Lauf griff der lokale Master-Skill nicht. `server.py` ersetzte nur
`master_skill._hole`. Der Takt holt seit Paket 17 aber über `_abrufen` (`master_skill.py:208`,
`_hole_und_teile`). Das Log zeigte deshalb „geladen (27662 Zeichen)“, also die Fassung aus dem
Repositorium. `server_r2.py` ersetzt auch `_abrufen`. Jetzt galt die lokale Fassung (30365 Zeichen,
mit `dokument_lesen`).

| Weg | Ergebnis | Beleg |
|---|---|---|
| 1 Thema | ok | „Entwurf erstellen“ (25 s): 45 Punkte, 2 Ebenen, Thema „Optik für Klasse 7“. „Übernehmen“ (0,6 s, kein KI-Zug) → „Dein Themenbaum-Entwurf ist gespeichert …“, Lauf `fertig`. „Weiter im Ablauf“ steht am wartenden KI-Schritt und unter dem Entwurf. |
| 2a Ordner anonym | ok | „So lassen“ → `fertig`. „Verfeinern“ → Entwurf mit Thema „Physik“ aus dem Ordner und „Sekundarstufe I“ (m2 behoben), `inhalte` 3/2/1+2 an den Ordner-Punkten, „Übernehmen“ → `fertig`. |
| 3a lose Dateien | ok (Thema schwach) | 4 Inhaltsdateien → „Mit so wenigen Dateien wird der Baum sehr klein. Lieber nach Stoff (Soll) aufbauen?“, „Trotzdem nur meine Dateien“ → 3 Punkte oben, „Übernehmen“ → `fertig`. Thema blieb ein Platzhalter (r2-1). |
| 5 Hochladen + freier Chat | ok | 3 Läufe, in jedem ruft die KI `dokument_lesen` auf. Antwort: Verdunstung, Kondensation, Niederschlag, Abfluss; „Transpiration … Wasserabgabe der Pflanzen über ihre Blätter“. Musterlösung zu Aufgabe 2: „Die Sonne erwärmt das Wasser … verdunstet …“. Kestra-Aufträge: 0. |
| Gegenprobe Krise | ok | Am wartenden KI-Schritt (Chip vorher da) Krisensatz → Telefonseelsorge-Nummern, Chips `[]`, kein „Weiter im Ablauf“. Im nächsten gewöhnlichen Zug ist der Chip wieder da. |

Die Leiste lief in allen Wegen nie rückwärts. Es gab keine MCP-Schreibaufrufe (nur
`lookup_wlo_vocabulary`) und keine Knoten im Repositorium. Der Server ist gestoppt, die Wegwerf-DB
gelöscht. Die Dev-DB und andere Container blieben unberührt.

**Befunde:**
- **r2-1 (MINOR):** Auf dem Datei-Weg setzte die KI als `thema` den Platzhalter „Themen aus den
  bereitgestellten Dateien“. Der Titel war gut („Fotosynthese, Zellatmung und Blattaufbau“). Die
  Regel in `seeds/06-ablaeufe/themenbaum.yaml:449` verbietet nur den Zweck, keine Platzhalter.
  `services/ablauf/vorbelegung.py:146` belegt auf diesem Weg bewusst nichts vor. Das gilt für 1 von
  1 Lauf, m1 ist also nur teilweise behoben. Nachstellen mit `opt3a_r2.py`.
- **r2-2 (NIT):** Der Ordner-Entwurf ohne Verfeinern („So lassen“) hat kein `thema`, nur
  `titel: Physik` (`ui_module/strukturentwurf_ordner.py:138`).

**Behoben nach dem zweiten Durchtest:** r2-1 — Vorgaben und Hinweis des Schritts `entwurf_inhalte`
verbieten jetzt auch Platzhalter als Thema und verlangen das gemeinsame Sachgebiet (Test
`test_r2_1_die_vorgaben_verbieten_platzhalter_als_thema`). Ob die KI sich daran hält, zeigt erst der
nächste echte Lauf. r2-2 bleibt bewusst so: Der Ordner-Entwurf ohne Verfeinern trägt den
Wurzelordner als Titel, ein Thema entsteht erst beim Verfeinern.
