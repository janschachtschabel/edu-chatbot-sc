# Plan: Entscheide vom 10.11. umsetzen, Themenbaum aus hochgeladenen Inhalten

Stand: **Entwurf 10.11.**, wartet auf Freigabe und auf die Antworten in §5. Grundlage:

- die Antworten des Nutzers vom 10.11. auf die offenen Fragen (§1);
- der Muster-Flow `edusharing.chatbot/node-metadata-write` (Beispielseite `flow-start`, §2);
- der kompakte Gestaltungsleitfaden „Themenbäume neu denken“ (10.11.) (§3);
- die Startansicht des Klick-Prototyps v4 „Sammlung mit Assistent“ (§3).

Vorgänger: `2026-11-09-ablaeufe-im-studio.md` (AS-0…AS-8 in PR #51), P1-Notiz
`2026-11-09-p1-chatbot-umwandlung.md`.

## 1. Entscheide des Nutzers (10.11.)

| Nr. | Frage | Entscheid | Folge |
|---|---|---|---|
| N1 | Dürfen Nicht-Angemeldete Dokumente in den Chat laden? | **Ja**, solange keine Operation am edu-sharing-Repositorium läuft. | Wie heute (`dokument_ohne_anmeldung` an). Will die Person ablegen, schreiben oder Kestra nutzen, fordert der Chatbot zur Anmeldung auf (wie N2). |
| N2 | Wem gehört ein anonym gelesenes Dokument nach der Anmeldung? | Es liegt im Zwischenspeicher des Chatbots und **gehört mit Anmeldung und Schreiboperation der Person**, die sich anmeldet und damit arbeitet. Umwandeln in Kestra nur mit Anmeldung. | Paket TB-E1. |
| N3 | Zählen Probe-Sitzungen (Studio-Vorschau) in der Auswertung? | **Nein**, eventuell gesondert ausweisen. | Paket TB-E2. |
| N4 | Darf die KI einen Ablauf direkt starten (AS-5c)? | **Ja**, wie ein Werkzeug oder weil der Ablauf es so beschreibt. Meist löst ein Knopf im Ablauf den nächsten Schritt aus. | Paket TB-E3. |
| N5 | Formeln im Widget | **Direkt integrieren**; die Grenzen des Widget-Bündels steigen um 10 kB. | Paket TB-E4. |
| N6 | Wo wird umgewandelt? | **Tendenziell in Kestra.** Für einzelne Anwendungsfälle (Dokument verarbeiten und im Chat direkt darauf reagieren) im Chatbot. Hängt vom Ablauf ab. | AS-T mit beiden Orten (`ort: kestra` und `ort: chatbot`). Der Ablauf wählt den Ort. |
| N7 (T1) | Upload-Weg | **Beide Wege bleiben offen.** Gebraucht wird ein Weg mit Datei- und Ordner-Upload in der Oberfläche. Später sollen auch Inhalte aus dem Repositorium einbezogen werden. | `ui_upload` (Ordner + Dateien, MCP-Stapel) ist der erste Weg; TB-5 später. |
| N8 (T2) | Übergabeformat | Siehe Muster-Flow: strukturiertes JSON in `outputs` (§2). | Teil-Typ je Flow (TB-2). |
| N9 (T3) | Identität beim Schreiben | **Noch nicht klar.** Was Kestra ergänzt, bleibt für die WLO-Person lesbar. | Schreibende Flows nur mit Freigabe der Person (Paket S); Frage F1 in §5. |
| N10 (T4) | Benachrichtigung | **Nein**, vorerst nicht; wie ein Job, dessen Stand man abfragt. | Wie heute: „Stand prüfen“ und Abfrage im Zug. |
| N11 (T5) | Eingabeschema der Flows | Wahrscheinlich nicht; **nice to have**. Ein- und Ausgabe sind strukturiertes JSON, je Flow eigen. | Vermerkt; das Studio pflegt Ein- und Ausgabe je Flow von Hand (TB-1). |
| N13 | Identität bei Flows (Nachtrag 10.11.) | **Vorläufig:** Die Nodes legt die WLO-Person an, angemeldet über den MCP. Der Flow läuft nicht mit ihren Rechten, schreibt aber in ihre eigenen Nodes; das genügt. Endgültig wird es später gelöst. | TB-1 startet über Weg A mit `X-Edu-User-Id` (§2 „Startweg“). |
| N14 | Antworten zu F2, F3, F5, F7 (Nachtrag 10.11.) | **F5:** heute keine Obergrenze je Job; ein **optional einstellbares** Limit ist sinnvoll. **F7:** vermutlich fehlt der Bericht bei `FAILED`. **F3:** ein Flow, der nur ausgibt, wäre ein zusätzlicher Flow, später (Tests, andere Abläufe). **F2:** prüfen bzw. fragen. Für vorhandene Materialien ist der Flow womöglich ungeeignet; er wird **erst nur für den beschriebenen Anwendungsfall** (frisch hochgeladene Dateien) genutzt, die Grenzen werden vermerkt. | TB-1 (Limit je Job einstellbar, Grenzen in Studio-Hinweis und Handbuch), TB-2 (`FAILED` ohne Bericht), §5b. |
| N12 | Werkzeug des MCP für die Bytes privater Dateien | **Vermerken**, später erklären. | `mcp-und-anmeldung.md`; kein Paket jetzt. |

## 2. Der Muster-Flow `node-metadata-write` (gelesen, nicht ausgeführt)

Die Beispielseite (`flow-start`) lädt Dateien hoch, startet den Flow und fragt den Stand ab. Gemessen ist
nichts; das hier ist der Inhalt der Beispieldateien:

- **Hochladen:**
  - je Datei ein `ccm:io` in der Inbox (`POST …/-inbox-/children?type=ccm:io&renameIfExists=true`);
  - dann der Inhalt als Multipart (`POST …/{id}/content?mimetype=…`) direkt an die REST-API des
    Repositoriums, denn der B-API-Proxy antwortet auf Multipart mit 415;
  - vorhandene nodeIds lassen sich zusätzlich angeben.
- **Start:** `POST /edu-sharing/rest/bapi/api/v1/jobs/flows/edusharing.chatbot/node-metadata-write`
  mit `{node_ids: [...], language}` → `202` mit `jobId`.
  - Der Weg geht über den **B-API-Proxy des Repositoriums**, angemeldet mit der Sitzung der Person
    (Cookie aus `validateSession`).
  - Der Flow meldet seine eigenen B-API-Aufrufe mit seiner Eingabe `bapi_token` an. Die Seite schickt
    keinen Schlüssel.
- **Ablauf im Flow:**
  - Er holt je Node den Volltext über einen **neuen Textendpunkt** von edu-sharing (GET).
  - Er erzeugt die Metadaten mit dem Metadaten-Agenten der B-API.
  - Er **schreibt sie in den Node**, und zwar **überschreibend**: Titel, Beschreibung, Schlagworte,
    Sprache, Fach (taxon id), Bildungsstufe, Zielgruppe, Ressourcentyp.
- **Abfrage und Abbruch:** `GET …/jobs/{jobId}?details=true` (die Seite fragt alle 3 s), Abbruch per
  `DELETE …/jobs/{jobId}`. Endstände `SUCCEEDED`, `FAILED`, `CANCELLED`.
- **Ausgabe `report`:** je Node eine Zeile mit
  - `status` (`OK`, `NO_TEXT`, `TEXT_FAILED`, `METADATA_FAILED`, `NOTHING_TO_WRITE`, `WRITE_FAILED`),
  - `httpCode`, `characters`,
  - den geschriebenen Eigenschaften.

**Die Flow-Definition** (vom Nutzer nachgereicht, 10.11.):

- **Kopf:**
  - Labels `bapi.expose: true`.
  - Scopes `edu-sharing-repo, edu-sharing-repo-write, llm, edu-sharing-llm,
    proxy:metadata-agent-canvas`.
  - `bapi.repo.properties` nennt die acht Felder, die der Flow schreiben darf: `cclom:title`,
    `cclom:general_description`, `cclom:general_keyword`, `cclom:general_language`, `ccm:taxonid`,
    `ccm:educationalcontext`, `ccm:educationalintendedenduserrole`, `ccm:oeh_lrt`.
- **Eingaben:**
  - `bapi_token` (SECRET, Pflicht; geht als `Authorization: Bearer` an jeden B-API-Aufruf);
  - `node_ids` (Liste);
  - `language` (`de`/`en`, Vorgabe `de`).
- **Je Node**, bis zu 4 gleichzeitig:
  1. `read_text`: `GET {b-api}/api/v1/edu-sharing/repo/nodes/{id}/text`, Frist 2 min.
  2. `generate_metadata`: `POST {b-api}/api/v1/proxy/metadata-agent-canvas/generate` mit
     `{input_source: text, text, language}`, Frist 5 min.
  3. `build_properties`: nur die acht Felder, nur nicht-leere Werte, jeder Wert als Liste von
     Zeichenketten.
  4. `write_metadata`: `PATCH {b-api}/api/v1/edu-sharing/repo/nodes/{id}/metadata` mit `properties` und
     `versionComment`.
     - Die Felder werden **ersetzt**.
     - **Jede Änderung legt eine neue Version an.**
     - Die Beschreibung des Flows rät: zuerst an Testknoten starten.
- **Bericht** `report`: je Node `nodeId`, `status`, `httpCode` (Zahl), `characters` (Zahl), `written`
  (`{changedKeys, ignoredKeys}`). Nacheinander geprüft:
  - Text nicht 200 → `TEXT_FAILED`.
  - Text leer → `NO_TEXT`.
  - Agent nicht 200 → `METADATA_FAILED`.
  - Schreiben 200 → `OK`.
  - Nichts zu schreiben → `NOTHING_TO_WRITE`.
  - Sonst → `WRITE_FAILED`.
- **Wird kein einziger Node geschrieben**, bricht der Flow mit `Fail` ab: Der Job ist `FAILED`, mit der
  Meldung „No node could be written …“. Ob der `report` dann noch in `outputs` steht, ist offen (F7).

**Folgen für den Chatbot:**

- Der Textendpunkt ist ein **B-API-Endpunkt** (`/api/v1/edu-sharing/repo/nodes/{id}/text`). Der Chatbot
  könnte ihn mit dem durchgereichten Schlüssel der Person selbst aufrufen. Das wäre Weg E der P1-Notiz,
  ohne MCP.
- Das passt zu N6 („Dokument verarbeiten und im Chat direkt darauf reagieren“). Zuerst eine
  Staging-Messung mit Testknoten (F4).
- **Identität:** Alle Repositoriums-Aufrufe des Flows tragen nur `bapi_token`, kein `X-Edu-User-Id`.
  Wem der Knoten gehört und wer schreiben darf, entscheidet also allein, **was für ein Token**
  `bapi_token` ist. Beim Start über den Repositoriums-Proxy ist es vermutlich ein an die Sitzung der
  Person gebundenes Token, das der Proxy einsetzt (die Beispielseite schickt keins). Das macht F1
  genauer.
- **Nicht der Chatbot schreibt, sondern der Flow.** Die Freigabe der Person (Paket S) muss deshalb
  **vor dem Start** liegen. Sie nennt die Nodes und die acht Felder und sagt: „überschreibt, legt
  Versionen an“.
- Ein `FAILED` mit dieser Meldung heißt „kein Node geschrieben“, nicht „Flow kaputt“. Die
  Rückmeldung unterscheidet das.

**Startweg** (Kestra-Leitfaden der B-API vom 10.11., §9.1):

- **Weg A:** direkt an die B-API, mit API-Schlüssel. Bei Repositoriums-Scopes ist `X-Edu-User-Id`
  Pflicht (sonst 400). Der Job arbeitet im Repositorium mit den Rechten dieses Benutzers, nie mit einem
  technischen.
- **Weg B:** über den Repositoriums-Proxy mit der Sitzung (Cookie), für Anwendungen im Browser. Wer
  dort Schlüssel, Kosten und Freigabe trägt, ist offen.
- **Der Chatbot nimmt Weg A** (er ist ein Server): der durchgereichte Schlüssel der Person wie heute,
  dazu `X-Edu-User-Id` = `authority` der Person.
  - `authority` liefert der MCP mit `wlo_auth_status` bzw. `/auth/status`. Heute behält der Chatbot
    davon nur einen Streuwert (`services/mcp/anmeldung._aus_stand`).
  - TB-1 hält `authority` **nur im Zug**: nie gespeichert, nie geloggt, nur nach bestätigter Anmeldung
    (wie `has_personal_auth`).
  - Gemessen 07.11.: Lesen mit `X-Edu-User-Id` = Benutzername 200, ohne 400, erfunden 403.
- **Grenzen** (B-API):
  - 20 unfertige Jobs je Schlüssel (danach 429);
  - `bapi_token` höchstens 12 h;
  - Laufzeit Standard 24 h (`bapi.maxRuntime`).
- **Ergebnisse:**
  - `outputs` und `files` erst bei `SUCCEEDED`;
  - `warnings: true` auch bei `SUCCEEDED`;
  - `progress` und `iterations` mit `?details=true`;
  - keine Rückmeldung von selbst.

**Abgleich mit dem Chatbot heute** (`services/auftraege/client.py`):

| Punkt | Chatbot heute | Muster-Flow |
|---|---|---|
| Weg | direkt an die B-API (`B_API_BASE_URL`), `Authorization: Bearer` mit dem durchgereichten Schlüssel der Person | über den B-API-Proxy des Repositoriums, mit der Sitzung der Person |
| Identität | **kein** `X-Edu-User-Id` (K18 offen) | ergibt sich aus der Repositoriums-Sitzung |
| Erlaubte Flows | nur lesende aus `B_API_JOBS_FLOWS` | **schreibt** in die Nodes |
| Eingabe | Startdaten des Schritts `auftrag` | `node_ids[]` aus dem Upload, `language` |
| Ausgabe | `outputs`, Dateien als Name und Größe | `outputs.report` (JSON, eine Zeile je Node) |

Der Chatbot hat **keine Repositoriums-Sitzung** der Person. Er hat nur die Anmeldung über den MCP (den
Zugangsblock). Wie er den Flow im Namen der Person startet, ist darum die erste Frage (F1).

## 3. Was Leitfaden und Prototyp für den Ablauf heißen

**Gestaltungsleitfaden** (Text gelesen; die Grafiken auf S. 3, 4, 7 und Abb. 5 ließen sich nicht als
Text lesen):

- **Ein Modell, mehrere Sichten:**
  - Der Baum zeigt nur die Hauptordnung.
  - Lehrplan, Kompetenzen, Niveau, Format und Zielgruppe sind **Facetten oder eigene Verknüpfungen**,
    keine Unterknoten („Klasse 8“ und „Arbeitsblätter“ unter „Optik“ sind falsch).
- **Eingangsdaten sind Herkunft, keine Zielstruktur:**
  - Bei einem Ordner-Upload sind Titel, Volltext, Dateien und Ordnernamen automatisch nutzbar.
  - Die Ordnerlogik bleibt erhalten; die Zielthemen werden vorgeschlagen.
  - Jahreszahl, Arbeitsstand und Bewertung im Ordnerpfad bleiben Herkunfts- oder Statusangabe.
- **Raster als Warnung, nicht als Sperre:**
  - Tiefe 3–4 Ebenen (persönlich 2–3).
  - Hauptebene 5–15 Knoten.
  - 3–20 Kinder je Knoten, Ziel 5–12, keine Einzelkinder.
  - Blatt etwa 5 Inhalte (privat ab 1); große Knoten ab 40–60 Inhalten erst über Facetten, dann
    teilen.
- **Benennung:** 1–4 Wörter. Keine Jahreszahlen, Klassenstufen oder Formate im Namen. Synonyme als
  Alternativbezeichnungen.
- **Dialog:** Vier Kernfragen (wofür, für wen, welche Grundlage, gibt es Inhalte?) setzen Baumart,
  Soll-/Ist-Sicht, Ausgangsstruktur und Standardfacetten. Weitere Fragen nur bei Bedarf.
  **Vorschau statt Endpunkt:** Entwurf mit Hinweisen auf Lücken, mögliche Facetten und begründete
  Abweichungen; die Person ändert, dann gibt sie frei.
- **Verfahren:** Für unsortierte Bestände Bottom-up (Inhalte gruppieren + LLM), hybrid mit Soll-Gerüst.
  Sechs Prüfschritte (Struktur, Befüllung, Plausibilität, redaktionelle Sichtung, Tree-Test, Nutzung).
  **Maschinell erschlossen ist nicht geprüft:** Vorschläge tragen Herkunft, Konfidenz und Status.

**Klick-Prototyp v4:** Die Datei enthält nur die Startansicht (442 Byte Text).

- **Einstieg:** in der Sammlungsseite „Physik“ (Hauptsammlung der Redaktion; Fach Physik;
  Sekundarstufe I/II; 0 Materialien) über „Sammlung mit Assistent“.
- **Sechs Phasen:** im Titel genannt, aber nicht in der Datei.
- **Für den Chatbot heißt das:** Start von außen mit Startdaten `sammlung` (AS-4). Den Sammlungskontext
  (Fach, Stufe) bringt die Seite mit.

## 4. Pakete

Reihenfolge nach Abhängigkeit. Jedes Paket bekommt ein Review mit Befundbehebung, Tests zuerst, und eine
Änderungsnotiz. Schritt 0 jedes Pakets: Skill `better-coding-workflow` laden, bei Oberfläche zusätzlich
`better-coding-frontend`.

### Gruppe E — Entscheide umsetzen (sofort baubar)

- **TB-E1 Dokument gehört der Person, die sich anmeldet (N1, N2):** **Umgesetzt 10.11.**, reviewt (`ablage.fuer_aufrufer` für Lader und Teil `document`). Plan:
  - **Heute:** Ein anonym gelesenes Dokument gehört `aufrufer=None` (`services/dokumente/stand.py`,
    `ablage.py`). Nach der Anmeldung findet der Entwurf es nicht (`kein_dokument`).
  - **Neu:** Beim ersten Zugriff einer angemeldeten Person in **derselben Sitzung** wird ein
    besitzerloses Dokument ihr zugeschrieben. Spätestens die erste Schreiboperation legt den Besitz
    fest.
  - **Grenze:** Ein Dokument einer **anderen** Person wird nie übernommen. Eine Abmeldung gibt das
    Dokument nicht frei.
  - Will eine anonyme Person ablegen, schreiben oder umwandeln, kommt die Anmelde-Aufforderung mit Chip.
    Das gibt es heute schon; ein Test hält es fest.
  - **Tests zuerst:**
    - lesen anonym, dann anmelden, dann Entwurf → gefunden;
    - eine andere Person → nicht gefunden;
    - nach dem Abmelden → nicht wieder anonym.
- **TB-E2 Proben gesondert ausweisen (N3):** **Umgesetzt 10.11.**, reviewt. **Abweichend vom Plan:** Merkmal ist die Spalte `sessions.vorschau` (Migration 0022) statt `entities._probe` (die Aufbewahrung leert `entities`), dazu Widget-Attribut `vorschau` für Gespräche der Vorschau ohne Probe; ausgewiesen über die Datenbasis „Nur Studio-Vorschau“ (`scope=probe`) statt einer eigenen Zeile. Plan:
  - Probe-Sitzungen kommen aus der Auswertung und den Kosten des Betriebs heraus.
  - Die Auswertung zeigt sie als eigene Zeile „Proben (Studio-Vorschau)“.
  - **Entscheid:** Das Merkmal ist `entities._probe`. Es steht schon in jeder Probe-Sitzung, deshalb
    gibt es kein zweites Präfix.
  - **Prüfen:** Wo zählen Auswertung, Nutzung und Kosten Sitzungen? Gleiche Regel überall, mit Test je
    Abfrage.
- **TB-E3 Abläufe direkt starten (N4, AS-5c):** **Umgesetzt 10.11.**, reviewt. **Abweichend vom Plan:** `modus: direkt` am Auslöser `agent` (nicht `direkt: true`); das Widget drückt den Knopf (`ui.direkt_start`). Plan:
  - Die KI darf einen Ablauf **direkt** starten, als Werkzeug (`direkt: true` am Auslöser) oder weil
    ein Ablaufschritt ihn nennt.
  - **Bremsen:**
    - höchstens ein Start je Zug;
    - kein Start, solange ein anderer Lauf wartet (die bestehende Bremse „läuft schon“);
    - kein schreibender Schritt ohne Freigabe (Paket S);
    - keine Schleife (derselbe Ablauf nicht zweimal in Folge ohne Eingabe der Person).
  - Der Knopf im Ablauf bleibt der übliche Weg.
- **TB-E4 Formeln im Widget (N5):** **Umgesetzt 10.11.** — keine Bibliothek passte (temml/KaTeX weit über 10 kB), daher eine eigene kleine LaTeX→MathML-Umwandlung; Bündel 192,4 kB gzip. Querschnitts-Review der Gruppe E behoben (Notiz `aenderungen/2026-11-10-querschnitt-gruppe-e.md`). Plan:
  1. **Messen:** den Befund mit echten Antworten nachstellen (LaTeX `$…$`/`\(…\)`, Unicode).
  2. **Grenzen:** Widget-Bündel 690 → 700 kB roh, 200 → 210 kB gzip, Warnung 190 → 200 kB
     (`check-widget-budget.mjs`, `angular.json`).
  3. **Darstellung:** LaTeX → **MathML** im Bündel; der Browser zeichnet MathML selbst.
     - Keine Schriftdateien, keine Netzquelle, also DSGVO-konform.
     - Die Bibliothek wählt eine Messung: Sie muss mit dem Rest in die 10 kB passen.
     - Passt keine, kommt eine eigene, kleine Umsetzung der häufigen Formen (Bruch, Hoch/Tief, Wurzel,
       griechische Buchstaben, Operatoren). Das melde ich vorher.
  4. **Sicherheit:** MathML nur aus der eigenen Umsetzung, durch den bestehenden Sanitizer; Tests
     gegen eingeschleustes HTML.
  5. **Vorgabe an das Modell** im Master-Skill: Formeln als LaTeX.

### Auftrag des Nutzers vom 10.11. abends (N15) — Umsetzung Gruppe F/T

> „Themenbaum aus Thema (ohne Inhalte) umsetzen — die eingrenzenden und präzisierenden Fragen fehlen.
> Abläufe so benennen, dass man sie im Studio klar zuordnen kann. TB-1 so erweitern, dass auch
> schreibende Flows möglich sind; ein Vermerk, dass der Flow schreibt (WLO-Anmeldung nötig) — das
> muss der Nutzer festlegen können. TB-2 bauen. TB-3: am Klick-Prototyp und den Fragen aus der
> Recherche orientieren, die beiden Abläufe anlegen und die fehlenden Elemente ergänzen, damit erste
> Tests möglich werden. Noch nicht: den Themenbaum in Sammlungen umwandeln — erst nur bis zur Anzeige
> im Chat, dann Ende. Metadaten auf Staging schreiben ist ok, Umfang klein halten.“

**Fehlende Elemente** (Erkundung 10.11.):
- Der Chatbot kennt den Benutzernamen (`authority`) nicht, nur einen Streuwert. Ohne ihn gibt es
  kein `X-Edu-User-Id`.
- Der Bericht des Flows enthält keine Metadaten-Werte (nur `changedKeys`). Ein Ablauf kann die
  Metadaten der hochgeladenen Nodes nicht lesen: lesende Werkzeuge bekommen keine Teile, und die KI
  sieht die nodeIds der Ablage nicht.
- Eine Wahl (Schnellantworten) wird kein Teil, und der KI-Schritt sieht Freitext und Wahl nicht
  (`hinweis` ohne Platzhalter). Die Kernfragen kämen also nicht beim Themenbaum an.
- Ein Seed mit `auftrag` blockiert den Werksabgleich, wo der Flow nicht in `B_API_JOBS_FLOWS` steht.

**Pakete** (je Review mit Befundbehebung, danach ein Querschnitts-Review):

> **Stand 10.11. abends:** TB-F1, TB-F2, TB-T1 und TB-T2 sind umgesetzt. Jedes Paket hat ein
> Review mit Behebung, danach lief das Querschnitts-Review F/T mit Behebung
> (`aenderungen/2026-11-10-querschnitt-gruppe-ft.md`). Nichts davon ist committet. Die Gruppe F
> unten (TB-1/TB-2) beschreibt das **frühere** Design und gilt nur noch als Hintergrund.
> - Die Box mit Chip ist ersetzt durch die Rückfrage, eine Wahl direkt vor dem Auftrag.
> - `wlo.metadaten-bericht@1` ist ersetzt durch `outputs.report` im Teil des Auftrags und
>   `metadaten_lesen`.
> - `hoechstens_je_auftrag` ist offen.

| Paket | Inhalt |
|---|---|
| **TB-F1** Flow mit Identität und Vermerk „schreibt“ | `authority` nur im Zug halten, nie loggen oder speichern. Beim Start eines Auftrags `X-Edu-User-Id` mitschicken, nur mit bestätigter Anmeldung. Am Schritt `auftrag` das Feld `repo_schreibt` (Studio, Ja/Nein): Der Flow schreibt ins Repositorium. Damit sind schreibende Flows erlaubt; die Prüfung verlangt die Voraussetzung `anmeldung` (gilt schon für jeden Auftrag) und einen Satz an die Person vor dem Start (Wahl-Schritt davor). Der Befund `auftrag_frei` blockiert nur einen eingeschalteten Ablauf, damit ein Seed den Werksabgleich nicht sperrt. |
| **TB-F2** Bericht und Metadaten als Teile | Der `report` steht schon im Teil des Auftrags (`outputs.report`). `FAILED` ohne Ausgabe führt zu `bei_fehler` (gibt es). Neu ist das Ablauf-Werkzeug `metadaten_lesen`: Es nimmt die nodeIds aus dem Teil `ablage` (vom eigenen Endpunkt geschrieben, also verlässlich), liest höchstens 50 Nodes mit `get_nodes_details` unter der Anmeldung der Person und schreibt den Teil `metadaten` (je Node Titel, Beschreibung, Schlagworte, Fach, Stufe, Ressourcentyp, gekürzt). |
| **TB-T1** Antworten erreichen den Themenbaum | Eine Wahl schreibt mit `schreibt` am Schritt das Label der Option als Teil (immer das deutsche, sprachfest). **Abweichung (Entscheid 10.11.):** Der `hinweis` des KI-Schritts setzt **keine** Platzhalter ein, weil getippter Text dort ein Einfallstor für Anweisungen wäre. Die KI sieht die Antworten in der Arbeitsstands-Zeile („Wahl: …“) und im Verlauf. `ui_strukturentwurf` bekommt `aus_inhalten`: Der Dienst liest den Teil `metadaten` auf dem Server (wie `aus_dokument`) und baut den Baum aus den Inhalten. |
| **TB-T2** Zwei Abläufe als Seed | `themenbaum_aus_thema` („Themenbaum · aus einem Thema“) und `themenbaum_aus_inhalten` („Themenbaum · aus eigenen Inhalten“). Dazu wird `sammlungsstruktur` zu „Themenbaum · aus Ordnern“ (nur der Titel). Kernfragen nach dem Leitfaden: Wofür (Unterricht planen, Materialpool, Redaktion), Für wen (Stufe), Fach und Thema, Tiefe. Beide enden mit der Anzeige des Entwurfs im Chat. Seeds aus (`aktiv: false`), mit Testfällen. |
### Gruppe F — Flow-Anbindung (nach F1)

- **TB-1 Flow `node-metadata-write` als Auftrag** (Weg A, N13):
  - `X-Edu-User-Id` aus der bestätigten MCP-Anmeldung, nur im Zug, nie gespeichert oder geloggt. Ohne
    Anmeldung kein Start.
  - Die nodeIds kommen nur aus dem Teil `ablage` desselben Vorgangs (die Person hat sie angelegt), nie
    aus dem Modell.
  - **Limit je Job (N14):** ~~Feld `hoechstens_je_auftrag`, Teil `wlo.metadaten-bericht@1`~~
    **Umgesetzt 13.11. (Paket R1)** als `aufteilen: {argument, hoechstens}`: Teilaufträge
    nacheinander, das Ergebnis bleibt ein Teil `wlo.auftrag@1` (Listen wie `report` aneinander).
    Notiz `aenderungen/2026-11-13-paket-r1-kestra-auftraege.md`.
  - **Nur für frisch hochgeladene Dateien (N14, F2):** Der Schritt nimmt nodeIds nur aus dem Teil
    `ablage` desselben Vorgangs, also nur Dateien, die die Person in diesem Lauf hochgeladen hat.
    Vorhandene Materialien gehören nicht dazu.
  - Die Freigabe nennt die Grenze: „ersetzt Titel, Beschreibung, Schlagworte … der hochgeladenen
    Dateien, jede Änderung als neue Version“.
  - Je Flow ein Eintrag mit Ein- und Ausgabe-Form (von Hand gepflegt, N11) und der Angabe
    „schreibt“/„liest“.
  - Ein schreibender Flow startet nur nach der Freigabe der Person (Box + Chip wie Paket S, mit Liste
    der Nodes und der überschriebenen Felder).
  - Der Start läuft über den in F1 entschiedenen Weg.
  - **Tests:**
    - Start nur nach der Freigabe;
    - ohne Anmeldung keine Freigabe;
    - in der Probe ein Trockenlauf.
- **TB-2 Teil `wlo.metadaten-bericht@1`:** `outputs.report` als typisierter Teil (AS-6 R2).
  - Je Node: Stand, Zeichen, geschriebene Felder.
  - Rückmeldetexte je Stand (`NO_TEXT` usw.).
  - Verzweigung `wenn_auftrag`:
    - fertig (alle `OK`);
    - teilweise (einige `OK`);
    - fehlgeschlagen (`FAILED`, kein Node geschrieben).
  - `FAILED` ohne `report` (vermutlich der Normalfall, N14) wird zu einem Bericht ohne Zeilen, mit
    dem Stand „nichts geschrieben“ und der Fehlermeldung des Jobs. Der Text an die Person nennt keine
    Gründe je Datei, er verweist auf einen neuen Versuch.
  - Große Berichte per Verweis.

### Gruppe T — Ablauf „Themenbaum aus Inhalten“ (nach TB-1/TB-2)

- **TB-3 Ablauf im Seed:**
  1. **Kernfragen** (Wahl-Schritte): Wofür dient der Baum? Für wen? Ein Start aus der Sammlungsseite
     bringt den Kontext mit (Startdaten `sammlung`).
  2. **Upload** von Ordner und Dateien (`ui_upload`, MCP-Stapel mit Freigabe) → Teil `ablage` mit nodeIds
     und Ordnerpfaden.
  3. **Auftrag** `node-metadata-write` mit diesen nodeIds (Freigabe) → warten, „Stand prüfen“ → Teil
     `wlo.metadaten-bericht@1`.
  4. **Entwurf** (`ui_strukturentwurf`) aus Titeln, Schlagworten, Fach und Ordnernamen. Ordnernamen
     gelten nur als Herkunft. Klassenstufe, Format und Jahr werden zu Facetten, nicht zu Knoten.
  5. **Vorschau mit Hinweisen:**
     - Raster-Warnungen aus §3;
     - leere, dünne und überfüllte Knoten;
     - mögliche Facetten;
     - Zuordnungen als „maschinell, ungeprüft“.

     Die Person ändert, dann gibt sie frei.
  6. **Anlegen** der Sammlungen und **Zuordnen** der Materialien (MCP-Werkzeuge, mit Freigabe).
- **TB-4 Prüfungen nach dem Leitfaden:** Struktur-Warnungen im Code, wo sie messbar sind:
  - Tiefe, Breite, Einzelkinder, Befüllung;
  - Benennung: Jahreszahl, Klassenstufe oder Format im Namen.

  Was eher Auslegung ist (Begriffsart der Geschwister, Facette oder Thema), gehört in den Master-Skill
  bzw. den Hinweis des Agent-Schritts, nicht in Code.

### Später

- **TB-5 Inhalte aus dem Repositorium einbeziehen (N7):** nodeIds aus Suche oder Sammlung als Eingabe
  des Flows. Der Muster-Flow nimmt schon vorhandene nodeIds an.
- Vermerkt: Eingabeschema der Flows von der B-API (N11), Byte-Werkzeug des MCP (N12).

## 5. Fragen zum Mitdenken (offen)

**Zum Flow** (für dich bzw. das Kestra- und B-API-Team):

- ~~**F1 Anmeldeweg:**~~ **Vorläufig entschieden (N13).**
  - Weg A: durchgereichter Schlüssel plus `X-Edu-User-Id` = `authority` aus der MCP-Anmeldung. Die
    Nodes gehören der Person.
  - `bapi_token` füllt die B-API je Job; der Chatbot gibt es nicht mit.
  - Offen bleibt: Ist `X-Edu-User-Id` der Benutzername oder die interne ID? Der Leitfaden lässt das
    offen; gemessen ist der Benutzername.
- **F8 Gemeinsamer Schlüssel:** edu-sharing wählt den durchgereichten Schlüssel selbst, einen für
  Angemeldete und einen für Gäste (Diensteleitfaden 2.2).
  - Dann teilen sich **alle** Angemeldeten die Grenze von 20 unfertigen Jobs. Bei vielen Personen
    gleichzeitig gibt es 429.
  - Ist das so, und gibt es dafür eine höhere Grenze?
  - Bis dahin sagt der Chatbot „Warteschlange voll, später erneut“ (`voll` mit `Retry-After`, gibt es
    schon).
- **F9 Rechte am Schlüssel:** Der Schlüssel der Angemeldeten braucht diese Rechte:
  - `JOB_RUN_EDUSHARING_CHATBOT_NODE_METADATA_WRITE`;
  - `EDU_SHARING_REPO`, `EDU_SHARING_REPO_WRITER`;
  - `METADATA-AGENT-CANVAS` und die LLM-Rechte.

  Der Gast-Schlüssel darf sie nicht haben. Wer stellt das ein?
- ~~**F2 Überschreiben:**~~ **Beantwortet (N14):** prüfen bzw. fragen; erst nur frische Uploads, Grenzen in §5b. Bisheriger Text: Der Flow **ersetzt** die acht Felder; jede Änderung ist eine neue Version (also
  wiederherstellbar). Soll er auch Angaben ersetzen, die die Person selbst eingetragen hat?
  Alternativen:
  - nur leere Felder füllen;
  - Vorschläge über die Suggestions-API („maschinell erschlossen ist nicht geprüft“).

  Für frisch hochgeladene Dateien ist Ersetzen unkritisch, bei vorhandenen Materialien (TB-5) nicht.
- ~~**F3 Nur lesen:**~~ **Beantwortet (N14):** später als eigener Flow. Bisheriger Text: Eine Variante ohne `write_metadata`, die `properties` je Node in den `report`
  legt (etwa `node-metadata-generate`), ist im Flow eine kleine Änderung.
  - Der Themenbaum könnte die Metadaten dann **vor** der Freigabe nutzen.
  - Geschrieben würde erst danach, mit dem Schreib-Flow oder per `PATCH`.
  - Baut das Team sie?
- **F4 Textendpunkt** `GET /api/v1/edu-sharing/repo/nodes/{id}/text` (Scope `edu-sharing-repo`):
  - **Läuft auf Staging** (Leitfaden 10.11.).
  - Antwort `{"text": …}`; der Text entsteht gegebenenfalls erst beim Aufruf (Frist 2 min).
  - Leer heißt: keine Datei oder kein extrahierbarer Text (Bild-PDF).
  - **Offen:** welche Formate (PPTX?), und ob der Chatbot ihn auf Weg A mit `X-Edu-User-Id` selbst
    nutzen darf. Das wäre „Dokument verarbeiten und direkt reagieren“ (N6) ohne Kestra.
  - Messung mit Testknoten: anlegen, lesen, entfernen.
- ~~**F5 Grenzen:**~~ **Beantwortet (N14):** optionales Limit je Job im Chatbot. Bisheriger Text:
  - Der Flow begrenzt `node_ids` nicht und läuft mit 4 gleichzeitig, bis zu 2 + 5 + 2 min je Node.
  - Das Token gilt höchstens 12 h, deshalb sollte der Flow `bapi.maxRuntime` auf höchstens `PT12H`
    setzen (Leitfaden; das Label fehlt heute).
  - Der Chatbot teilt große Uploads auf, etwa höchstens 50 Nodes je Job (Annahme, vorher gemessen).
  - Was heißt `NO_TEXT` für den Ablauf: Node überspringen, oder fragt die Person nach (Scans)?
- **F6 Ablageort:** Das Beispiel lädt in die Inbox, unser Stapel in einen Vorgangs-Ordner im
  persönlichen Bereich. Ist das für Textendpunkt und Schreiben gleich?
- ~~**F7 Bericht bei `FAILED`:**~~ **Beantwortet (N14):** vermutlich fehlt er; der Chatbot geht davon aus. Bisheriger Text: Laut Leitfaden gibt es `outputs` erst bei `SUCCEEDED`. Bricht der Flow
  mit „No node could be written“ ab, fehlt der Bericht also genau im Fehlerfall.
  - **Vorschlag ans Team:** `require_one_ok` weglassen und nur im `report` melden.
  - Bis dahin sagt der Chatbot bei diesem `FAILED`: „Für keine Datei konnten Metadaten geschrieben
    werden“, ohne Gründe je Datei.
- **F10 `ignoredKeys`:** unveränderte Werte oder nicht erlaubte Felder? Die Rückmeldung an die Person
  hängt davon ab (Leitfaden §12 offen).

**Zum Themenbaum** (aus Leitfaden und Prototyp):

- **L1 Kernfragen:** Sind die vier Kernfragen feste erste Schritte des Ablaufs? Welche der vier
  Sammlungsarten (Grafik S. 4, nicht lesbar) gibt es, und wie heißen sie?
- **L2 Soll oder Ist:** Zeigt der Entwurf leere Knoten? Der Leitfaden sagt: bei persönlicher Planung
  sichtbar als Aufgabe, im Materialpool nur befüllte.
- **L3 Ordner:** Ordnerstruktur übernehmen (Herkunft bewahren) oder neu ordnen? Bietet der Entwurf
  beides an?
- **L4 Facetten:** Klassenstufe, Format und Jahr werden zu Metadaten am Material, nicht zu Knoten. Der
  Flow schreibt Bildungsstufe und Ressourcentyp schon. Reicht das?
- **L5 Raster:** Die Zahlen des Leitfadens als Warnung in der Vorschau, nicht als Sperre. Einverstanden?
- **L6 Mehrfachzuordnung:** Darf ein Material in mehreren Knoten liegen? Das ginge als Referenz, ohne
  Kopie.
- **L7 Prüfstatus:** Wo steht, dass eine Zuordnung maschinell und ungeprüft ist? edu-sharing kennt dafür
  kein Feld an der Sammlungsreferenz (Leitfaden: Klärungsbedarf).
- **L8 Knotenangaben:** Beschreibung bzw. Geltungsbereich und Alternativbezeichnungen am Knoten. Achtung:
  `cm:description` wird am Sammlungs-Endpunkt still verworfen (bekannte Falle).
- **L9 Zielort:** Wo entsteht der Baum: als persönliche Sammlung oder unter einer Redaktionssammlung
  (der Prototyp startet in der Physik-Hauptsammlung)? Mit wessen Rechten?
- **L10 Prototyp:** Bitte das vollständige HTML des Klick-Prototyps (die sechs Phasen fehlen in der
  Textdatei).

## 5b. Bekannte Grenzen des Muster-Flows (vermerkt, N14)

- Er **ersetzt** acht Felder und fragt nicht, ob die Person sie schon gepflegt hat. Darum gilt er nur
  für frisch hochgeladene Dateien. Für vorhandene Materialien (TB-5) braucht es einen anderen Flow
  („nur leere Felder“ oder Vorschläge) oder eine Rückfrage. Erst klären, dann TB-5.
- Er kennt keine Obergrenze je Job. Der Chatbot teilt auf (Limit einstellbar).
- Bei `FAILED` fehlt vermutlich der Bericht (Abbruch `require_one_ok`). Vorschlag ans Team bleibt:
  den Abbruch weglassen.
- `bapi.maxRuntime` fehlt, das Token gilt aber höchstens 12 h.
- Ein Flow, der nur ausgibt (ohne Schreiben), kommt später als eigener Flow (F3), etwa für Tests und
  die Vorschau vor der Freigabe.

Diese Grenzen stehen auch im Handbuch der Abläufe (`docs/ablaeufe.md`), sobald TB-1 umgesetzt ist.

## 5a. Diensteleitfaden (Team 6) — Abgleich später

Der Chatbot steht in der Swagger der B-API schon als Dienst („bad boerdi chatframework“). Der
Diensteleitfaden gilt also auch für ihn.

**Schon da:**
- Trace-ID B3-konform mit `x-client-trace-id` (Paket 17);
- durchgereichter Schlüssel, nie geloggt;
- Logs ohne Inhalte (Paket 18).

**Zu prüfen (eigenes Paket DL, nicht jetzt):**
- LLM über **Routennamen** statt Modellnamen (`/api/v1/llm/router/…`; den Router gibt es seit Paket 17,
  die Vorgabe ist zu prüfen);
- zwei Ports: öffentlich die API, intern `/health`, `/ready`, `/metrics`;
- Helm-Chart je Version mit NetworkPolicy und Alarmregeln;
- gemessene Ressourcen;
- Steckbrief und Kompatibilitätsmatrix;
- Antwortzeiten je Endpunkt;
- Fehler als JSON mit `trace_id`.

Erst ein Bericht „was fehlt für die Übergabe an T6“, dann Code.

## 6. Nicht im Umfang

- Lehrpläne und Kompetenzen als eigene, versionierte Achsen (Leitfaden §6);
- Tree-Tests und Auswertung von Suchlogs;
- SKOS-URIs für Knoten.

## 7. Prüfung

- Je Paket Tests zuerst;
- die vollen Suiten in der CI;
- Chat-Smokes mit nativem `gpt-6-luna` gegen eine Wegwerf-DB;
- Browser-Abnahme für TB-E4 und TB-3;
- Flows nur gegen Staging, mit Testkonto und selbst angelegten, danach entfernten Nodes.
