# Abläufe im Studio — Arbeitsbereich, Schritte, Auslöser, Tests (Entwurf 2026-11-09)

Stand: **Entscheide E1–E5 gefallen (09.11.), alle wie empfohlen.** Querschnitt AS-U+BU und zweites Review (§5k, §5l) behoben, Browser-Abnahme AS-U bestanden (10.11.); AS-7a/b/c umgesetzt und reviewt, Querschnitts-Review behoben, Browser-Abnahme bestanden (§5m). AS-8a/b/c umgesetzt, AS-8a zweimal reviewt, AS-8b im Browser abgenommen (§5n). AS-0 fertig, reviewt und im Browser abgenommen; AS-1 fertig und reviewt (09.11.); AS-2 (Regel-Editor, Ablaufbild, Querverweise) fertig und reviewt; Querschnitts-Review über AS-0…AS-2 behoben (09.11.); AS-3a/3b/3c fertig, je reviewt, Querschnitts-Review AS-3 behoben (09.11.); AS-Da/Db/Dc/Dd fertig und je reviewt (`ablage_zuordnen` offen, T1); Querschnitts-Review AS-D behoben (09.11.); P1 gemessen (09.11., Notiz `2026-11-09-p1-chatbot-umwandlung.md`); AS-T wartet auf Entscheide aus P1; AS-4a/4b/4c fertig, je reviewt, Querschnitts-Review AS-4 behoben (09.11.); Entscheid AS-4a Befund 10 = Option 2; Restbefunde RB-1…RB-3 fertig, je reviewt, Querschnitts-Review behoben (09.11.); Browser-Abnahme AS-4 + RB-3 bestanden (09.11.); AS-5a/5b umgesetzt (10.11., §5g); AS-5c (`direkt`) offen; AS-Ua/Ub fertig, je zweimal reviewt (10.11., §5h); Zwischenpaket BU (Widget-Bündel 199,9 → 187,4 kB gzip) umgesetzt (10.11., §5i); als Nächstes AS-Ud.

| Entscheid | Ergebnis |
|---|---|
| E1 Speicherung | eine Datei je Ablauf |
| E2 Start von außen | Widget-API/Attribut mit Startschema; signierter Start über die B-API später. **Nutzer-Zusatz:** Ein Ablauf soll auch wie ein Werkzeug im Chat auslösbar sein, zusätzlich zum fest eingebauten Aufruf (→ D1, AS-5, in beiden Modi). |
| E3 Webseitenführung | Abläufe können führen; die heutige Tour bleibt, ein Umzug kommt später hinter einen Schalter |
| E4 Tests | Testfälle (Simulation ohne LLM) plus „Im Widget ausprobieren“ |
| E5 Oberfläche für die Person | eigenes Paket AS-U |

Ergänzt am 09.11.: Datenweitergabe zwischen Schritten (§4 D8, Paket AS-D), Prüfung zur Umwandlung
von Dokumenten (§4 D9, P1, AS-T; Kestra als Ziel, ein Übergang im Chatbot nur nach dem Entscheid aus der P1-Notiz, Punkt 2) und eine Ablauf-Oberfläche für die Person im Widget (§4 D10, AS-U).

## 1. Ziel

Die Redaktion legt im Studio mehrere Abläufe an, verwaltet und testet sie, an einer leicht
zugänglichen Stelle. Ein Ablauf führt die Person Schritt für Schritt. Er kann Folgendes:

- Texte ausgeben;
- UI-Module zeigen;
- Schnellantworten anbieten und nach der Wahl verzweigen;
- Kestra-Aufträge starten und auf ihre Rückmeldung reagieren;
- verzweigte Führungen wie die Webseitenführung abbilden.

Ein Ablauf startet per Knopf, per Wendung, per KI (als Werkzeug) oder von außen mit
mitgegebenen Daten. Das Ziel dahinter: Die Redaktion bindet den Chatbot ein, reicht Infos hinein,
etwa die Sammlung, um die es geht, und der Ablauf führt die Person. Die ersten Anwendungsfälle
betreffen Sammlungsstrukturen.

## 2. Ist-Stand (Code vom 09.11.)

| Bereich | Heute | Lücke |
|---|---|---|
| Studio | `06-ablaeufe/katalog` ist der dritte Abschnitt der Seite „UI-Module“, ein Formular für alle Abläufe. Liste und Detail sind verschachtelt, die Liste zeigt nur die `id`. Es gibt „Prüfen“ (`POST /api/config/ablauf-pruefen`) und die Schrittfolge als Textliste. | Keine eigene Seite, kein Titel und kein Zustand in der Liste. Ein Dokument für alle Abläufe, also auch nur eine Fassung. Kein Ablaufbild. |
| Schritte | `nachricht`, `modul`, `werkzeug` (auch schreibend mit `freigabe`), `agent`, `auftrag`, `verzweigung`, `ende` (`domain/config_models/ablauf.py`). | Texte sind fest, ohne Platzhalter. `weiter` und Regeln sind rohes JSON. |
| Schnellantworten | Keine eigenen; ein Lauf zeigt nur Systemknöpfe. Optionen gibt es nur über `ui_entscheidung` + `wenn_gewaehlt`. | Keine Chips mit Ziel. Freitext wird kein Teil und lässt sich nicht verzweigen. |
| Bedingungen | `wenn_teil` (Teil vorhanden), `wenn_gewaehlt`. | Keine Wertvergleiche, keine Seite, keine Startdaten, kein Ergebnis eines Auftrags. |
| Kestra | Schritt `auftrag`: Start mit der Anmeldung der Person; Rückmeldung über „Stand prüfen“ oder automatisch im Zug der Person; Ergebnis als Teil; `dateien_holen`; Abbrechen. | Flows nur aus `B_API_JOBS_FLOWS`, ohne Eingabeschema. Keine Verzweigung nach dem Ergebnis. Rückmeldetexte nicht einstellbar. |
| Auslöser | `knopf`, `text` (Wendung), `modul`; `agent` nur als Vorschlag (Knopf), nur im Agent-Modus. | Kein direkter Start durch die KI, kein Werkzeug im Muster-Modus, kein Start mit Daten von außen (kein Startschema, `page_context` erreicht den Ablauf nicht). |
| Tests | Statische Prüfung beim Speichern; Simulation nur in pytest. | Kein Testlauf im Studio, keine Testfälle je Ablauf. |
| Datenweitergabe | Teile im Vorgang, typisiert: `wlo.ordnerbaum@1` (Upload erfasst), `wlo.ablage@1` (je Datei nodeId, Stand, Rolle; `ablage/vorgang_teil.py`), `wlo.sammlungsstruktur@1` (Entwurf), `wlo.dokument-verweis@1`, Auftragsergebnis. Lesen über `$teil` mit `pfad`, schreiben über `schreibt`. Teile aus Antworten kommen nur von `ui_upload` und `ui_strukturentwurf`. | Kein Zusammenführen (Ordnerbaum plus nodeIds der Ablage zu einer Struktur mit nodeIds). Kein Markdown der Inhaltsdateien als Teil. Keine Typprüfung zwischen Schritten. Keine Sicht auf den Datenfluss. |
| Umwandlung | Im Chatbot vorhanden: markitdown (PDF, DOCX, PPTX, XLSX, Text, Markdown), Kindprozess mit Frist, Seiten- und Größengrenzen, ein Platz geteilt mit dem RAG-Import (`services/dokumente/umwandlung.py`). Genutzt für das Strukturdokument und RAG. | Nicht für viele Inhaltsdateien eingesetzt; kein OCR für Scans und Bilder. |
| Oberfläche im Widget | Ein Lauf zeigt seine Schritte als Chat-Nachrichten und Module, dazu `ui_fortschritt` für Aufträge und den Hinweis „Gespräch fortsetzen“. | Kein Überblick für die Person: wo sie im Ablauf steht, was noch kommt, was schon gesammelt ist; kein „Meine Vorgänge“. |
| Webseitenführung | Eigene, fest programmierte Zustandsmaschine (`domain/tour.py`, sechs feste Schritte); die YAML liefert nur Texte, Gruppen und URLs. | Abläufe kennen keine Seite, keine Ankunft auf einer Seite und keine Navigation. |

## 3. Lösungswege für die Grundsatzfragen

### E1 Speicherung: ein Katalog oder eine Datei je Ablauf

- **A — ein Katalog wie heute**, dazu eine eigene Seite mit Liste und Detail.
  - Vorteile: wenig Umbau, Prüfung und Fassungen bleiben, wie sie sind.
  - Nachteile: Wer einen Ablauf speichert, speichert alle. Zwei Personen erzeugen Konflikte (409). Werks- und eigene Fassung gibt es nur für alle Abläufe zusammen. Ein einzelner Ablauf lässt sich nicht exportieren.
- **B — eine Datei je Ablauf** (`06-ablaeufe/<id>`), wie die Gruppen-Dokumente.
  - Vorteile: Fassung, Konflikt und Werkszustand je Ablauf. Anlegen, Duplizieren und Löschen sind Dateiaktionen. Export und Import je Ablauf. So war es schon im Plan 11-05 gedacht.
  - Nachteile: Der Lader liest mehrere Dateien. Der heutige Katalog muss einmal übertragen werden. Prüfungen über alle Abläufe (doppelte Wendungen) laufen dateiübergreifend.
- **C — Abläufe als Datenbanktabelle.** Bricht das Muster, nach dem alle Einstellungen gepflegt werden. Verworfen.

**Empfehlung B.**

### E2 Start mit Daten von außen (Redaktion)

- **A — Gastgeberseite per Widget:** Attribut oder JS-Aufruf `startAblauf(id, daten)` im eingebetteten Widget, etwa `{sammlung: <nodeId>}`. Das Widget schickt `ablauf_starten` mit `startdaten`. Das Backend prüft die Daten gegen das Startschema des Ablaufs. Nutzt die heutige Einbettung samt Ticket-Anmeldung.
- **B — Link mit Parametern:** `…?ablauf=<id>&sammlung=<nodeId>`. Einfach, aber die Daten stehen in der Adresse (Protokolle, Verlauf). Nur für unkritische Kennungen.
- **C — Server-API mit signiertem Auftrag:** edu-sharing legt über die B-API einen Start an, das Widget löst ihn mit einer Kennung ein. Am sichersten, braucht aber Arbeit auf der edu-sharing-Seite.

**Empfehlung A jetzt, C später**, falls Daten mit Gewicht (Rechte, Personenbezug) mitkommen.

Unabhängig vom Weg gilt:
- Startdaten sind Eingaben und nie Rechte. Schreiben braucht weiter die Anmeldung der Person.
- Die Startdaten landen als Teil `start` im Vorgang.

### E3 Webseitenführung

- **A — Abläufe können führen.** Dafür kommen neue Bausteine:
  - der Schritt `seite`: Link anbieten und optional auf die Ankunft auf der Seite warten;
  - die Bedingung `wenn_seite`;
  - der Auslöser `seite`: Start beim Öffnen auf einer passenden Seite.

  Die bestehende Tour bleibt. Ein Beispiel-Ablauf „Führung“ zeigt, wie sie als Ablauf aussähe; der Umzug kommt später hinter einen Schalter.
- **B — die Tour gleich umziehen.** Dann gibt es eine Maschine statt zwei, aber das Risiko für die laufende Tour ist hoch (Einstieg je Seite, Synonyme der Gruppen).
- **C — keine Führungen in Abläufen.**

**Empfehlung A.**

### E5 Oberfläche für die Person

Die Ablauf-Leiste, gesammelte Daten und „Meine Vorgänge“ (D10) kommen als **eigenes Paket AS-U
nach AS-3** — so sieht die Person in jedem Ablauf gleich, wo sie steht. Alternative: nur die
Schritte im Gespräch wie heute (weniger Aufwand, aber bei langen Abläufen ohne Überblick).
**Empfehlung: AS-U bauen.**

### E4 Tests

- **A — Testfälle je Ablauf plus Simulation im Studio.**
  - Ein Testfall nennt: Startdaten, die Antworten an jedem wartenden Schritt, Attrappen-Ergebnisse für Werkzeuge und Aufträge.
  - Erwartet werden: der Weg durch die Schritte, der Endschritt und die Teile.
  - Das Backend spielt den Fall mit dem echten Treiber durch, ohne LLM, MCP oder Kestra. Das ist deterministisch und kostet nichts.
  - Im Studio stehen „Tests ausführen“ und das Ergebnis je Fall.
- **B — dazu „Im Widget ausprobieren“:** Vorschau mit Startknopf und Startdaten, in einer Studio-Testsitzung. Aufträge und Schreiben laufen dort nur als Trockenlauf.
- **C — nur die Widget-Probe.** Ohne wiederholbare Fälle bleibt jede Änderung ein Handtest.

**Empfehlung A + B.** A kommt früh, damit die folgenden Pakete abgesichert sind.

## 4. Eigene Entscheide (Vorgaben, änderbar)

- **D1 Abläufe als Werkzeuge der KI.**
  - Jeder aktive Ablauf mit Auslöser `agent` wird ein Werkzeug `ablauf__<id>`. Die Felder seines Startschemas sind die Parameter. Das gilt in beiden Modi; im Muster-Modus nur, wenn das Muster das Werkzeug in `tools:` nennt (wie bei den UI-Modulen).
  - Der Modus ist je Auslöser einstellbar: `vorschlagen` (Vorgabe; die Person bekommt einen Knopf) oder `direkt`. `direkt` geht nur bei Abläufen ohne schreibende Schritte und ohne Aufträge.
  - Beschreibung und `wann`/`nicht_wann` des Ablaufs werden zur Werkzeugbeschreibung.
- **D2 Schnellantworten.**
  - `nachricht`- und `modul`-Schritte können `optionen` tragen: Chips mit `label` und `ziel` (Schritt).
  - Mit Optionen wartet der Schritt. Die Wahl verzweigt direkt, ein eigener `verzweigung`-Schritt ist nicht nötig.
  - Optional nimmt der Schritt Freitext an (`freitext: {ziel, schreibt}`). Der Text wird dann ein Teil.
  - Getippter Text, der keiner Option entspricht, geht wie heute an die KI. Der Lauf wartet weiter, und die Chips der Wahl bleiben unter jeder Antwort (sie sind der Weg „zurück zum Ablauf“).
- **D3 Platzhalter in Texten:** `{start.sammlung}` und `{teil.<name>.<pfad>}`. Werte werden als Text eingesetzt, gekürzt und ohne Markdown-Wirkung. Die Prüfung meldet unbekannte Namen.
- **D4 Bedingungen:**
  - neu `wenn_wert`: Teil oder Startdaten, Pfad, Vergleich `gleich|enthaelt|vorhanden|leer|groesser|kleiner`;
  - neu `wenn_seite`: Muster auf die aktuelle Seite;
  - neu `wenn_auftrag`: `fertig|fehler`.
  - Ein Regel-Editor im Studio ersetzt das JSON.
- **D5 Kestra:** Verzweigung nach dem Auftragsergebnis (D4) und Rückmeldetexte je Status am Schritt. Das Eingabeschema der Flows liest das Studio aus der B-API, sobald die B-API es liefert (Anfrage ans Team); bis dahin bleibt die Liste aus `B_API_JOBS_FLOWS`.
- **D6 Studio-Seite „Abläufe“:**
  - eigener Eintrag in der Seitenleiste unter „gemeinsam“;
  - Liste mit Titel, aktiv, Auslösern, Befunden der Prüfung und benutzten Modulen;
  - Neu (leer oder aus Vorlage), Duplizieren, Löschen (mit Rückfrage), Aktiv-Schalter;
  - Detail mit Formular, Regel-Editor, Ablaufbild (SVG, nur lesend; Klick wählt den Schritt), Prüfen, Tests;
  - Querverweise zwischen Modul und Abläufen in beide Richtungen.

  Ein grafischer Editor per Ziehen kommt nicht (zu viel Aufwand für den Nutzen).
- **D8 Datenweitergabe zwischen Schritten.** Die Teile sind der Datenbus des Ablaufs. Sie sind
  generisch: Ein neuer Anwendungsfall braucht neue Abläufe, keinen neuen Code.
  - Jeder Schritt nennt, was er liest (`$teil`-Verweise) und was er schreibt (`schreibt` mit
    Typ). Werkzeuge, Dienste und Flows geben ihren erwarteten Eingabetyp an.
  - **Auswahl aus einem Teil** (neu, R1): Ein Verweis kann eine Liste filtern und ein Feld
    herausziehen, etwa „die nodeIds aller abgelegten Strukturdokumente“:
    `{$teil: ablage, liste: inhalte, wo: {rolle: struktur, stand: stored}, feld: node_id}`.
    Damit entstehen `structure_node_ids` und `content_node_ids` für Flow-1 ohne eigenen Dienst.
  - **Ergebnis in Teile aufteilen** (neu, R2): Ein Auftrag bildet seine Ausgaben auf eigene Teile
    ab, je Ausgabe mit Typ, etwa `struktur → draft (wlo.sammlungsstruktur@1)`,
    `zuordnung → zuordnung (wlo.zuordnung@1)`, `befund → befund`, `inhalte → inhalte
    (wlo.inhalte@1)`. Große Ausgaben bleiben in Kestra; der Teil hält dann nur den Verweis, und der
    Chatbot holt den Inhalt erst, wenn ein Schritt ihn liest (wie `dateien_holen`).
  - Die Prüfung meldet, wenn ein Schritt einen Teil liest, den vorher kein Schritt schreibt, oder
    einen falschen Typ erwartet. Das gilt je möglichem Weg, also auch nach Verzweigungen.
  - Im Studio kommt eine Sicht „Daten“: je Teil der erzeugende Schritt, die lesenden Schritte, der
    Typ und ein Beispielwert aus den Testfällen.
  - Lokale Dienste nur, wo eine Auswahl nicht reicht:
    - `struktur_mit_nodeids`: verbindet einen bearbeiteten Entwurf mit den Sammlungs-nodeIds nach
      dem Anlegen, damit Folgeschritte (Einsortieren, Metadaten) die richtigen Knoten treffen.
    - `ablage_zuordnen`: Ordnerbaum plus `ablage` ergeben eine Struktur mit nodeIds, für den Fall
      „Sammlung direkt aus Ordnern“ ohne Kestra.
  - Große Teile (über 8 KB) liegen schon heute in `vorgang_ablage`. Die KI sieht nur Kurztexte,
    nie nodeIds oder Volltexte (wie heute).
- **D9 Umwandlung zu Markdown: beides abbildbar.** Ziel ist Kestra (Team-Skizzen §4b): Kestra
  extrahiert die Texte der Inhalte und des Strukturdokuments, schreibt das Markdown ans Repo und
  erzeugt die Metadaten. Ob und wie der Chatbot bis dahin selbst umwandelt, entscheidet die
  P1-Notiz (`2026-11-09-p1-chatbot-umwandlung.md`, Optionen A–F; Ziel A, ein Übergang erst nach den
  Vorfragen ans Team). Ein Ablauf soll beide Wege können, ohne dass sich die Folgeschritte
  ändern:
  - Schritt `umwandeln` mit `ort: chatbot|kestra`. Bei `kestra` startet er den Extraktions-Flow
    (wie ein Auftrag), bei `chatbot` wandelt er im Chatbot um.
  - Beide liefern denselben Ausgabetyp `wlo.texte@1`: je Datei die nodeId, das Markdown oder ein
    Verweis darauf, Länge, Stand. Folgeschritte (Themenbaum, Metadaten, `wlo_attach_fulltexts`)
    lesen nur diesen Teil.
  - Umgestellt wird im Studio am Schritt; ein Testfall je Ort sichert ab, dass der Rest gleich
    läuft.
  - Markdown nur, wo eine KI damit arbeitet (Skizze). Für reine Ablage ohne KI wird nicht
    umgewandelt.
  - Die Prüfung P1 setzt die Grenzen des Chatbot-Wegs:
    - **P1-a Formate und Qualität:** echte Unterlagen (Lehrplan-PDF, DOCX, PPTX, gescanntes PDF)
      durch `umwandlung.py`; Ergebnis, Dauer, Fehler. Scans ohne Textschicht gehen nur über Kestra
      (OCR).
    - **P1-b Menge:** Wie viele Dateien schafft der eine Umwandlungsplatz in einer Frist, ohne den
      RAG-Import zu blockieren? Ergibt die Obergrenze je Schritt; darüber verweist die Prüfung auf
      `ort: kestra`.
    - **P1-c Weg der Bytes:** Nach dem Upload liegen die Dateien in WLO, nicht beim Chatbot. Ergebnis
      (P1-Notiz): heute kommt der Chatbot weder an die Bytes (MCP 403/405) noch verlässlich an den
      Text des Repositorys; der Weg über die nodeId (Option F) braucht ein Werkzeug des MCP-Teams.
- **D10 Oberfläche für die Person im Widget** (generisch, für alle Abläufe):
  - **Ablauf-Leiste** über dem Eingabefeld, solange ein Lauf läuft: Titel des Ablaufs, „Schritt 3
    von 6“ mit Namen (aus dem Ablauf, mögliche Wege nach Verzweigungen gezählt), Knöpfe
    „Abbrechen“ und „Später fortsetzen“. Tastatur- und Screenreader-tauglich.
  - **Gesammelte Daten** aufklappbar: was der Ablauf bisher hat, in lesbarer Form je Teiltyp
    (Ordner und Dateien mit Stand, Entwurf, Texte als Länge), ohne nodeIds.
  - **„Meine Vorgänge“** für Angemeldete: offene Vorgänge mit Ablauf, Stand und letzter Änderung;
    „Fortsetzen“ und „Löschen“ (mit Rückfrage). Baut auf dem K2a-Hinweis „Gespräch fortsetzen“ auf.
  - Die Schritte selbst bleiben Nachrichten und Module im Gespräch; die Leiste ersetzt sie nicht.
  - Alles als nachgeladenes UI-Modul oder Hüllen-Komponente mit den M3-Tokens, de/en.
- **D7 Doku:** ein Autorenhandbuch `docs/ablaeufe.md` mit drei Beispiel-Abläufen:
  - Sammlung aus Ordnern;
  - Sammlung prüfen (Abgleich plus Lücken);
  - Führung.

## 4b. Abgleich mit den Team-Skizzen (09.11., evtl. nicht der letzte Stand)

### Was die Skizzen festlegen

- **Upload:** direkt aus dem Frontend in die Inbox von edu-sharing; daraus kommen Binary und nodeId.
  Das Frontend merkt sich, welche nodeId das Strukturdokument ist.
- **Flow-1** (`edusharing.support/flow-1`): Eingaben `structure_node_ids`, `content_node_ids`.
  - `structure_texts`: Text lesen, Markdown extrahieren, Markdown ans Repo schreiben.
  - `content_texts`: dasselbe, dazu Metadaten erzeugen und schreiben.
  - Ein zweiter Flow mit nur `node_ids` macht dasselbe für einzelne Knoten.
- **Flow-2** (`flow-2`): den Themenbaum erzeugen und prüfen; bei Bedarf erneut anfragen.
- **Flow-3/4:** die Sammlungsstruktur anlegen (mit kompendialen Texten und Metadaten) und die
  Inhalte zuordnen.
- **Übergabe an den Chatbot:** in getrennten Teilen, jeder mit eigenem Verweis.
  - `struktur`: JSON (Ordner, Baum) oder Markdown (Strukturdokument);
  - `zuordnung`: nodeId → `knoten_id`;
  - `befund`: Zahlen und Hinweise;
  - `inhalte`: `Partial<Node>[]`, nur Metadaten;
  - `volltext_ref` optional.

  Große Teile bleiben in Kestra, der Chatbot holt sie per Verweis.
- **Gespräch:** stop/start zwischen den Flows. edu-sharing benachrichtigt die Person, sie öffnet
  den Chatbot erneut; dann folgen der Stand, die Präsentation und Rückfragen. Offen ist: Wer fragt
  den Stand der Flows ab?

### Derselbe Anwendungsfall als Ablauf

Mit den Bausteinen dieses Plans, als Prüfstein für die Pakete:

1. `modul ui_upload`: Ordner und Dateien wählen, Rollen Struktur oder Inhalt. Ergebnis: Teil
   `ablage` mit nodeId und Rolle je Datei. Der Upload-Weg (MCP oder direkt in die Inbox) ist
   dem Ablauf egal.
2. `auftrag flow-1`: Argumente per Auswahl (R1) `structure_node_ids` und `content_node_ids`;
   `warten: frei`. Die Person darf gehen. Ausgaben werden Teile (R2).
3. Wiederkehr: Benachrichtigung, Link oder „Gespräch fortsetzen“ → „Stand prüfen“ (R3).
4. `auftrag flow-2`: Themenbaum aus `struktur` und `inhalte`. Ergebnis: Teil `draft`.
5. `modul ui_strukturentwurf`: zeigen und bearbeiten. Schnellantworten (D2) „Passt“, „Neu
   erzeugen“ (zurück zu 4, R4), „Abbrechen“.
6. Optional `modul ui_strukturabgleich` gegen eine bestehende Sammlung.
7. `auftrag flow-3` (schreibend): nur nach Freigabe der Person (R5) die Struktur anlegen.
   Ergebnis: Teil `angelegt` mit nodeIds der Sammlungen.
8. `auftrag flow-4` (schreibend, Freigabe): Inhalte zuordnen über `zuordnung` und `angelegt`.
9. `ende` mit Zusammenfassung (Platzhalter D3).

### Was daraus an Anforderungen folgt

- **R1 Auswahl aus Teilen:** Listen filtern, Felder herausziehen (D8). → AS-D
- **R2 Ausgaben eines Auftrags als typisierte Teile, große per Verweis** (D8). → AS-6
- **R3 Wiederkehr von außen:** Ein Einstieg mit Vorgang- oder Auftragskennung setzt fort und
  prüft den Stand, etwa aus einer Benachrichtigung von edu-sharing. Er gehört zu E2 (Startdaten).
  Die Kennung ist nie ein Recht: Fortsetzen darf nur die angemeldete Besitzerin (wie K2a).
  → AS-4
- **R4 Schleifen mit Wartepunkt:** „Neu erzeugen“ führt zurück zum Auftrag. Das erlaubt die Prüfung
  heute schon, weil ein wartender Schritt dazwischen liegt. Die Testfälle (AS-1) decken es ab.
- **R5 Schreibende Aufträge:** Flow-3/4 schreiben ins Repo. Sie brauchen dieselbe Freigabe wie
  schreibende Werkzeuge (Paket S), dazu die Klärung, unter welcher Person Kestra schreibt (K18:
  `X-Edu-User-Id` nur aus geprüfter Anmeldung). Heute lässt der Chatbot nur lesende Flows zu.
  → AS-6, abhängig von T3
- **R6 Wer fragt den Stand ab:** heute der Chatbot, sobald die Person zurückkommt (oder
  automatisch im Zug). Die Benachrichtigung durch edu-sharing ersetzt den fehlenden
  Hintergrund-Wächter. → T4

### Fragen an das Team (T)

- **T1** Upload-Weg: direkt in die Inbox (Skizze) oder über den MCP-Stapel (heute gebaut, mit
  Freigabe und Rollen W4)? Für den Ablauf zählt nur der Teil `ablage`; beide Wege können ihn
  füllen. **Für `umwandeln` nicht egal:** T1 entscheidet über die Übergänge B/C/D der P1-Notiz
  (bei einem Upload in die Inbox sieht der Chatbot die Datei nie).
- **T2** Übergabeformat: Kommen `struktur`, `zuordnung`, `befund` und `inhalte` als Outputs des
  Jobs, als Dateien oder als Verweise (welche Art Verweis, wie lange gültig)?
- **T3** Schreiben in Flow-3/4: Unter welcher Identität (Trusted App mit `X-Edu-User-Id`), und wie
  weist der Chatbot die Freigabe der Person nach?
- **T4** Benachrichtigung: Schickt edu-sharing einen Link zurück in den Chatbot (mit welcher
  Kennung), oder öffnet die Person ihn selbst?
- **T5** Liefert die B-API das Eingabeschema der Flows (für die Studio-Auswahl und die Prüfung)?

## 5. Pakete (Reihenfolge nach Abhängigkeit; je Paket Review mit Befundbehebung)

| Paket | Inhalt | hängt an |
|---|---|---|
| **AS-0** | Datei je Ablauf (E1 B): Lader, Übertragung des Katalogs, Prüfung über alle Dateien. Studio-Seite „Abläufe“ mit Liste und Detail (D6 ohne Bild und Regel-Editor), anlegen, duplizieren, löschen, aktiv. | E1 |
| **AS-1** | Testfälle und Simulation (E4 A): Modell `tests` je Ablauf, Endpunkt `POST /api/config/ablauf-testen`, Studio „Tests ausführen“. | AS-0 |
| **AS-2** | Bearbeiten: Regel-Editor für `weiter`/Regeln, Ablaufbild, Querverweise Modul ↔ Ablauf. | AS-0 |
| **AS-3** | Schritte erweitern: Schnellantworten mit Ziel und Freitext (D2), Platzhalter (D3), `wenn_wert` (D4). | AS-1 |
| **AS-D** | Datenweitergabe (D8): Ein- und Ausgabetypen je Schritt, Auswahl aus Teilen (R1), Prüfung je Weg, Studio-Sicht „Daten“, Dienste `struktur_mit_nodeids`, `ablage_zuordnen`. | AS-3 |
| **P1** | Prüfung des Chatbot-Wegs (D9): Formate und Qualität, Menge je Frist, Rückholen über die nodeId; Ergebnis als Notiz mit Grenzen. **Erledigt 09.11.:** [`2026-11-09-p1-chatbot-umwandlung.md`](2026-11-09-p1-chatbot-umwandlung.md) — ein Platz je Replik (~4–5 PDFs à 40 S./min bei dichtem Satz), etwa 200 statt 300 Seiten in 60 s, Scans nur Kestra; nach dem Upload ist weder Bytes noch Text sicher zurückzuholen. Sechs Wege (A Kestra für alles … F Bytes über die nodeId); Ziel A, ein Übergang erst nach den Vorfragen ans Team (Flow-Termin, T2, wer den Themenbaum baut, T1); Entscheide in der Notiz. | — |
| **AS-T** | Schritt `umwandeln` (D9) mit `ort: kestra` (Ziel) und — nur nach dem Entscheid aus der P1-Notiz — `ort: chatbot`; gleicher Ausgabetyp `wlo.texte@1`; Testfall je gewähltem Ort. | AS-D, P1; `ort: kestra` zusätzlich AS-6 (R2), T2 und der Extraktions-Flow (Team) |
| **AS-U** | Oberfläche im Widget (D10): Ablauf-Leiste, gesammelte Daten, „Meine Vorgänge“. Dazu (Abnahme AS-4, 09.11.): feste Ablauftexte tragen kein Etikett „KI-generierte Antwort“ (Merker am Zug). | AS-3 |
| **AS-4** | Auslöser und Startdaten: Startschema, Teil `start`, Widget-API `startAblauf` und Attribut (E2 A), Prüfung der Startdaten, Wiederkehr mit Vorgang- oder Auftragskennung (R3). | AS-3 |
| **AS-5** | Abläufe als Werkzeuge (D1): Agent und Muster, `vorschlagen`/`direkt`. | AS-4 |
| **AS-6** | Kestra: Ausgaben als typisierte Teile, große per Verweis (R2); `wenn_auftrag`; Rückmeldetexte; schreibende Aufträge mit Freigabe (R5, nach T3); Flow-Schema (nach T5). | AS-D |
| **AS-7** | Führungen (E3 A): Schritt `seite`, `wenn_seite`, Auslöser `seite`, Beispiel „Führung“. | AS-3 |
| **AS-8** | „Im Widget ausprobieren“ (E4 B) mit Trockenlauf. Autorenhandbuch und Beispiele (D7). | AS-4 |

Den detaillierten Aufgabenplan je Paket (Dateien, Tests zuerst, Prüfbefehle) schreibe ich nach
der Freigabe der Entscheide.

## 5b. Aufgaben AS-0 — Datei je Ablauf, Studio-Seite „Abläufe“

Schritt 0: `/better-coding-workflow` und `/better-coding-frontend` laden. Die übrigen Pakete
bekommen ihren Aufgabenplan unmittelbar vor dem Start, auf dem Code-Stand nach dem vorigen Paket.

**Ist:** Gruppierte Bereiche (ein Dokument je Datei) gibt es für `03-patterns` und `04-personas`,
beide als Markdown mit Frontmatter. Das betrifft:
- `config_guards._GROUPED_AREAS`;
- `config_kennungen.kennung_von` liest `frontmatter.id`;
- `POST /api/config/documents` legt `{frontmatter, body}` an;
- `DELETE /api/config/file`;
- das Studio mit `group-section` und `group-documents`.

Abläufe sind YAML-Dokumente. Darum wird die Gruppe um eine **Dokumentform** erweitert: Markdown
(Kennung in `frontmatter.id`) oder YAML (Kennung im Feld `id`).

### AS-0.1 Gruppe `06-ablaeufe` mit YAML-Dokumenten (Backend)

- **Dateien:**
  - `api/config_guards.py`: `_GROUPED_AREAS` um `06-ablaeufe`;
  - `api/config_kennungen.py`: `kennung_von` je Gruppe, `schluessel_fuer`;
  - `api/config_documents.py`: Vorlage eines leeren Ablaufs, Kopie setzt `id` und `titel`;
  - `domain/config_models/__init__.py`: `model_for("06-ablaeufe/<id>")` → `AblaufArea`;
  - `domain/config_models/ablauf.py`: `AblaufArea` als Dokument; `id` muss dem Schlüssel entsprechen;
  - `domain/area_effects.py`.
- **Reserviert:** Die Kennung `katalog` ist vergeben (Übergang).
- **Leerer Ablauf:** `{id, titel: {de: <Name>}, aktiv: false, schritte: [{id: ende, typ: ende, text: {de: ""}}]}`.
- **Tests zuerst** (`tests/test_ablauf_dokumente.py`):
  - anlegen (201);
  - doppelte Kennung (409);
  - Kopie mit neuer `id`;
  - Kennung passt nicht zum Schlüssel (400);
  - Pfadangriffe wie bei den Mustern (`06-ablaeufe/../x`, `06-ablaeufe/`);
  - löschen;
  - Modellfehler (422).

### AS-0.2 Laufzeit liest alle Ablauf-Dokumente

- **Dateien:**
  - `services/ablauf/ausloeser.py`: `laden`/`katalog` lesen alle Schlüssel `06-ablaeufe/*`, nur
    aktive; feste Reihenfolge nach `id`, damit „erster Treffer“ bei Wendungen stabil bleibt;
  - `services/ablauf/zug.py`, `api/config_choices.py` (Auswahllisten);
  - `services/ablauf/pruefung.py`: Prüfung je Dokument; neue übergreifende Warnung bei gleicher
    Wendung in zwei aktiven Abläufen;
  - `api/config_ablauf.py`: `ablauf-pruefen` nimmt ein Ablauf-Dokument.
- **Tests:** Ein Lauf eines Ablaufs aus einem Dokument läuft wie bisher. Die **Fassung** des
  Laufs (Hash der Schritte) ist für denselben Ablauf vor und nach der Umstellung gleich, sodass
  laufende Läufe weiterlaufen. Dazu Wendungs-Warnung, inaktiv nicht startbar, `ablauf-pruefen` mit
  Dokument.

### AS-0.3 Übertragung des Katalogs

- **Seed:** `backend/seeds/06-ablaeufe/katalog.yaml` → `backend/seeds/06-ablaeufe/sammlungsstruktur.yaml`
  (ein Dokument).
- **Datenbank:** Alembic-Datenmigration **0021**. Gibt es eine Zeile `06-ablaeufe/katalog` (Werk
  und, falls vorhanden, eigene Fassung), wird je Ablauf eine Zeile `06-ablaeufe/<id>` mit gleichem
  Inhalt und gleicher Fassungsart angelegt; die Katalog-Zeile wird danach entfernt. Bereits
  vorhandene Zeilen werden nicht überschrieben. Die Rückmigration fügt den Katalog wieder zusammen.
- **Tests:** Migration auf einer Postgres-Testdatenbank (wie `test_ablauf_pg.py`) mit eigenem
  Katalog aus zwei Abläufen ergibt zwei Dokumente samt eigener Fassung. Die Rückmigration stellt
  den Katalog wieder her. Läuft die Migration zweimal, ändert sich nichts.
- **Betrieb:** Migration 0021 und `boerdi import-config --werksabgleich`.

### AS-0.4 Studio-Seite „Abläufe“

- **Navigation:** eigener Eintrag „Abläufe“ in der Gruppe „gemeinsam“ (`studio-views.ts`,
  `curated-pages-gemeinsam.ts`). Der Abschnitt auf der Seite „UI-Module“ entfällt; dort steht
  stattdessen ein Verweis auf die neue Seite.
- **Liste:** Panel `ablaeufe.component`, gebaut nach dem Muster von `group-section`, mit einer
  Zeile je Ablauf:
  - Titel (Sprache des Studios, sonst `id`);
  - Schalter „aktiv“;
  - Auslöser als Kürzel;
  - benutzte Module;
  - Befunde der Prüfung als Zahl.

  Dazu Suche, „Neuer Ablauf“ (Name → Kennung, wie bei den Mustern), Duplizieren und Löschen mit
  Rückfrage. Der Schalter „aktiv“ speichert das Dokument mit Fassung (409-Kasten wie überall).
- **Detail:** das vorhandene Bereichsformular für `06-ablaeufe/<id>` samt „Prüfen“ und Schrittfolge
  (K2c). Ungespeicherte Änderungen sperren den Wechsel (`unsavedChangesGuard`).
- **Zustände:** Laden, leer („Noch kein Ablauf — lege den ersten an“), Fehler mit „Erneut
  versuchen“, Konflikt.
- **Barrierefreiheit:** per Tastatur bedienbar, Schalter mit Namen, Live-Region für Meldungen.
- **Texte:** de/en im Katalog (`i18n/catalogue/ablaeufe-seite.ts`).
- **Tests (Vitest):** Liste aus der API, aktiv schalten (PUT mit Version, 409), anlegen, kopieren,
  löschen mit Rückfrage, leer- und Fehlerzustand, i18n-Wächter.

### AS-0.5 Abschluss

- **Doku:** `docs/ui-module.md` (Verweis), Änderungsnotiz `docs/aenderungen/…-paket-as-0-*.md`,
  `docs/offene-befunde-und-todo.md`.
- **Prüfungen:**
  - volle Backend-Suite, `ruff check .`;
  - Frontend `ng test studio`, `check:*`, eslint;
  - E2E, falls Studio-Abdeckung vorhanden.
- **Review** mit Befundbehebung.

### Abnahme AS-0

- Im Studio steht „Abläufe“ in der Seitenleiste. Dort lassen sich zwei Abläufe anlegen, einer
  kopieren, einer löschen und einer aktiv schalten, ohne JSON.
- Speichern eines Ablaufs ändert die anderen nicht (eigene Fassung je Ablauf).
- Der Ablauf `sammlungsstruktur` läuft im Widget wie vorher, auch ein vor der Umstellung
  begonnener Lauf.
- Die Migration 0021 ist umkehrbar, und ein zweiter Lauf ändert nichts.

## 5c. Aufgaben AS-1 — Testfälle und Simulation

- **Modell** (`domain/config_models/ablauf.py`): `AblaufArea.tests` (höchstens 20) mit `AblaufTest`:
  - `name`;
  - `teile` (Teile vor dem Start);
  - `werkzeuge` (Schritt-ID → Ergebnis eines Werkzeugs, `null` = liefert nichts);
  - `eingaben` (höchstens 30). Je Eingabe `bei` (der wartende Schritt), dazu je nach Wartepunkt:
    - `antwort` (Antwort eines abfragenden Moduls);
    - `ergebnis` und `fehler` (Auftrag oder Freigabe);
    - `freigabe` `ja` oder `nein`;
    - `teile` (was die KI am `agent`-Schritt hinterlässt);
  - `erwartet` mit `weg` (Schritte in genau dieser Reihenfolge), `status`, `ende` und `teile` (Namen,
    die es am Ende gibt).

  Die Fassung eines Laufs bleibt gleich, weil sie nur an den Schritten hängt.
- **Simulation** (`services/ablauf/simulation.py`) mit dem echten Treiber und einer
  Attrappen-`Umgebung`. Sie ruft weder LLM noch MCP, startet keinen Auftrag und legt nichts vor.
  - **Neue Nähte der `Umgebung`**, im Betrieb ohne Wirkung:
    - `ersatz`: Werkzeug-Ergebnis je Schritt;
    - `simulation`: Module nur aus fertigen Daten, sonst ein Platzhalter-Block;
    - `protokoll`: jeder besuchte Schritt.
  - **Antworten** werden wie im Zug zu Teilen (`teile_aus_antwort`).
  - **„nein“** lässt den Lauf an der Freigabe warten.
  - **Abweichungen** werden je Testfall als Text gemeldet: anderer Weg, anderer Status oder anderes
    Ende, fehlender Teil, eine Eingabe für einen anderen Schritt, eine nicht verbrauchte Eingabe.
- **Endpunkt** `POST /api/config/ablauf-testen` (Rumpf `AblaufArea`) → `{ergebnisse: [{name, ok,
  status, weg, ende, abweichungen}]}`. Studio-Schlüssel, schreibt nichts, im Vertrag dokumentiert.
- **Studio:** In „Prüfen und Schrittfolge“ kommt der Knopf „Tests ausführen“ dazu. Das Ergebnis
  steht je Testfall als ✓/✗ mit Text und Abweichungen, angesagt über die Live-Region. Die Testfälle
  selbst werden im Formular des Ablaufs gepflegt.
- **Tests zuerst:** `tests/test_ablauf_simulation.py` (Wege, Werkzeuge, Aufträge, Freigabe ja/nein,
  KI-Teile, Abweichungen, keine echten Aufrufe, Grenzen) und der Endpunkt; Studio-Spec für den Knopf.

## 5d. Aufgaben AS-3 — Schnellantworten, Platzhalter, `wenn_wert`

AS-3 kommt in drei Teilpaketen, je mit Review und Befundbehebung; danach ein Querschnitts-Review.
Für alle drei gilt: **neue Felder haben die Vorgabe `None`**. `fassung` lässt `None` weg; eine
Vorgabe `[]` änderte die Fassung jedes Ablaufs, und jeder Deploy bräche wartende Läufe ab.

### AS-3a Schnellantworten mit Ziel und Freitext (D2)

- **Modell:** `Schritt.optionen: list[Schnellantwort] | None` (nur `nachricht` und `modul`, `NurBei`), je
  Option `id` (Kennung), `label` je Sprache und `ziel` (Schritt). Dazu
  `Schritt.freitext: Freitext | None` mit `ziel` und `schreibt` (Name eines Teils).
- **Prüfung:**
  - **Grenzen:** höchstens 8 Optionen (keine, wenn nur Freitext), Kennungen und Labels eindeutig, jedes Ziel ist ein Schritt.
  - **Freitext:** `freitext.schreibt` hat die Form eines Teils.
  - **Abfragendes Modul:** Ein `modul`-Schritt mit abfragendem Modul hat keine Optionen, denn er
    wartet schon auf seine Antwort.
  - **Nachfolger:** `nachfolger()` nennt die Ziele der Optionen und das Ziel des Freitexts.
    Erreichbarkeit und Schleifenprüfung sehen sie dadurch.
  - **Kein `weiter`:** Ein Schritt mit Optionen hat kein `weiter`, denn die Wahl entscheidet.
- **Treiber:**
  - Ein Schritt mit Optionen oder Freitext zeigt seinen Text und Block und wartet dann.
    - Status `wartet_wahl`.
    - `Ausgabe.wahl = {schritt, optionen: [(id, label)], freitext: bool}`.
  - `weiter_wahl(ablauf, lauf, wahl, text, umgebung)`:
    - eine angebotene Kennung → ihr Ziel; `lauf.gewaehlt` = `[wahl]`, damit eine folgende
      Verzweigung sie lesen kann;
    - sonst Text bei einem Schritt mit Freitext → Teil `schreibt` (Typ `text`), dann
      `freitext.ziel`;
    - sonst `None`.
- **Zug:**
  - **Chips:** Die Optionen erscheinen als Direktaktion-Chips
    `__action__|<label>|ablauf_wahl|{ablauf, schritt, wahl}`, wie „Stand prüfen“.
  - **Direktaktion `ablauf_wahl`:** Sie geht durch dieselbe Sicherheitsprüfung (Liste in
    `preflight.py`) und hat einen Zweig in `preflight_ablauf.antwort`. Sie wirkt nur, wenn der Lauf
    dieser Person an genau diesem Schritt und in dieser Fassung wartet.
  - **Getippter Text:**
    - Gleicht er dem Label einer Schnellantwort (wie eine Wendung verglichen), ist er diese Wahl.
    - An einem Schritt mit Freitext ist er sonst die Antwort und wird ein Teil. Er läuft durch die
      Sicherheitsprüfung wie jede Nachricht.
    - Ohne Freitext geht er wie heute an die KI. Der Lauf wartet weiter, und jede Antwort trägt die
      Chips erneut („Zurück zum Ablauf“ ist damit die Wahl selbst).
- **Simulation:** `TestEingabe.option` und `TestEingabe.text` für `wartet_wahl` (nicht `wahl`: `.wahl.` ist in den Studio-Texten für Auswahlwerte vergeben); eine Kennung, die
  der Schritt nicht anbietet, ist eine Abweichung (wie im Betrieb).
- **Studio:**
  - Feldtexte DE/EN.
  - Die Schrittfolge und das Ablaufbild zeigen die Pfeile der Optionen (Beschriftung = Label) und
    des Freitexts.
  - Die Ziele der Regel-Editor-Auswahl gelten auch hier: `x-widget: schritt-ziel`, ein Auswahlfeld
    der Schritte.
- **Tests zuerst:**
  - Modell und Prüfung;
  - Treiber (Wahl, Freitext, unbekannte Wahl, Fassung unverändert für Abläufe ohne die Felder);
  - Zug und Preflight (Chip, falscher Schritt, alte Fassung, getippter Text mit und ohne Freitext);
  - Simulation;
  - Studio-Specs.

### AS-3b Platzhalter in Texten (D3)

- **Wo:** `{teil.<name>}` und `{teil.<name>.<pfad>}` in `text` und `freigabe` (nicht in den Labels der Optionen — die Chips entstehen ohne die Teile; die Prüfung meldet es)
  und dem Text von `ende`. `{start.<feld>}` ist reserviert; es wirkt ab AS-4 und meldet bis dahin
  einen Befund.
- **Einsetzen:**
  - im Treiber beim Ausgeben, über die Teile des Laufs;
  - als Text, höchstens 200 Zeichen;
  - Markdown-Zeichen entschärft, damit ein Teil keine Links oder Überschriften baut;
  - ein fehlender Wert wird zu „—“.
- **Prüfung:** Ein Platzhalter mit einem Teil, den kein Schritt davor schreibt und der nicht als
  Startteil zählt, ist ein Befund (wie `$teil`-Verweise). Bei kaputter Syntax ebenso.
- **Studio:** Hinweis am Textfeld. Die Simulation setzt ebenfalls ein (Testfälle mit `ende` sehen
  den Text).

### AS-3c Bedingung `wenn_wert` (D4)

- **Modell:** `Weiter.wenn_wert` mit:
  - `quelle` (`teil.<name>[.<pfad>]`);
  - `vergleich` (`gleich|enthaelt|vorhanden|leer|groesser|kleiner`);
  - `wert` (Text; bei `vorhanden` und `leer` leer).
- **Treiber** `_waehle`:
  - Zahlenvergleich nur, wenn beide Seiten Zahlen sind; sonst greift die Regel nicht.
  - `enthaelt` gilt für Text (Teilstring) und Listen (Element).
- **Prüfung:** Die Quelle verweist auf einen bekannten Teil, der Vergleich braucht seinen Wert
  (oder keinen).
- **Studio:** Der Regel-Editor bekommt die Bedingung „Wert vergleichen“ mit Quelle (Vorschläge aus
  den Teilen), Vergleich und Wert. `fehlerVon` und `regelFehlerVon` kennen sie.
- **Simulation:** über die Teile des Testfalls, ohne eigenes Feld.

## 5e. Aufgaben AS-D — Datenweitergabe zwischen Schritten (D8)

Vier Teilpakete, je mit Review; danach ein Querschnitts-Review. Neue Felder wieder mit Vorgabe
`None` (Fassung).

### AS-Da Auswahl aus einem Teil (R1)

- **Form:** ein Verweis mit Auswahl,
  `{"$teil": "ablage", "liste": "inhalte", "wo": {"rolle": "struktur", "stand": "stored"},
  "feld": "node_id"}`.
  - `liste`: der Pfad zur Liste im Teil; statt `pfad`, beide zusammen sind ungültig.
  - `wo`: höchstens 5 Bedingungen Pfad → Wert. Gleich heißt genau gleich (Text, Zahl, ja/nein,
    `null`). Ein Eintrag passt, wenn alle Bedingungen passen.
  - `feld`: der Pfad im Eintrag. Ohne `feld` ist das Ergebnis die gefilterten Einträge selbst.
  - Ergebnis ist immer eine Liste, auch eine leere. Einträge ohne das Feld fallen weg. Ist die
    Stelle keine Liste, fehlt der Wert wie bei einem fehlenden Teil.
- **Wo es gilt:** überall, wo `$teil` gilt (`daten`, `argumente`; Treiber und Simulation). Wer einen
  Teil bekommen darf (`darf`), entscheidet weiter der Name des Teils.
- **Prüfung:** Form von `liste`, `wo` und `feld`. Ein Objekt mit `$teil`, das kein gültiger Verweis
  ist, ist ein Befund, denn es bliebe sonst still als wörtlicher Wert stehen.
- **Studio:** Verweise mit Auswahl stehen in der Tabelle „Argumente“ als JSON. Ein eigener Editor
  folgt erst, wenn die Form sich bewährt hat.

### AS-Db Prüfung je Weg und Typen

- **Lesen vor dem Schreiben:** Ein `$teil`-Verweis braucht einen Teil, der auf einem Weg vor dem
  Schritt entsteht (`_teile_davor`, wie bei Platzhaltern und `wenn_wert`), oder einen, der vor dem
  Start da ist (Modul-Auslöser; ab AS-4 Startdaten).
  - **Übergang:** Teile, die heute schon vor dem Start im Vorgang liegen können (ein früherer Lauf
    derselben Person), bleiben erlaubt, wenn der Ablauf sie selbst irgendwo schreibt. Dann gibt es
    nur eine Warnung, keinen Befund. Ein Befund ist, was kein Schritt und kein Modul schreibt.
- **Typen:**
  - Jeder schreibende Schritt hat einen bekannten Ausgabetyp (Dienst, Modul-Manifest, Freitext
    `text`, MCP `text`, Auftrag `wlo.auftrag@1`).
  - Dienste und Modul-Eingaben nennen den erwarteten Eingabetyp.
  - Passt ein Verweis ohne Pfad nicht, ist das ein Befund.
  - Mit Pfad oder Auswahl gibt es keinen Typvergleich, denn der Inhalt ist dann ein anderer.

### AS-Dc Studio-Sicht „Daten“

- **Eine Tabelle je Ablauf:** Teil, Typ, schreibende Schritte, lesende Schritte (Verweise,
  Platzhalter, `wenn_teil`/`wenn_wert`) und ein Beispielwert aus den Testfällen (gekürzt).
- **Umgesetzt (Abweichung):** das Backend rechnet die Sicht mit „Prüfen“ aus derselben Quelle wie die Prüfung (`typen`) — eine zweite Typtabelle im Studio liefe auseinander. Ein Klick auf einen Schritt
  wählt ihn wie „Zum Schritt“.

### AS-Dd Dienste `struktur_mit_nodeids` und `ablage_zuordnen`

- `struktur_mit_nodeids`: Entwurf (`wlo.sammlungsstruktur@1`) plus Ergebnis des Anlegens ergeben
  den Entwurf mit der nodeId je Knoten (`wlo.sammlungsstruktur@1`, Feld `node_id`).
- `ablage_zuordnen`: Ordnerbaum (`wlo.ordnerbaum@1`) plus `ablage` (`wlo.ablage@1`) ergeben die
  Struktur mit den nodeIds der abgelegten Inhalte je Ordner.
- **Beide** laufen lokal, sind rein und ohne Netz, mit Typen nach AS-Db; Tests mit echten Formen.
- **Format des Anlegens:** Erst vor AS-Dd am MCP-Vertrag nachsehen (`wlo_create_collection_tree`),
  nicht raten.
- **Umgesetzt (09.11.):** `struktur_mit_nodeids` mit dem vorhandenen Feld `wlo_id` statt `node_id`
  (Vertrag des Moduls), Zuordnung über den Titelpfad wie `collection-tree.ts`; dazu (Review)
  `baum_aus_entwurf` für das Argument `tree`. **`ablage_zuordnen` offen:** `ablage` trägt keinen
  Ordnerpfad je Datei, der Ordnerbaum keine Dateien; wartet auf T1.

## 5f. Aufgaben AS-4 — Startdaten, Start von der Gastseite, Wiederkehr (E2 A, R3)

Schritt 0 je Teilpaket: `/better-coding-workflow` (dazu `/better-coding-frontend` bei 4b/4c).
Nach jedem Teilpaket Review mit Befundhebung, danach Querschnitts-Review AS-4 und volle Suite.

**Ist:** Ein Ablauf startet per `ablauf_starten` (`action_params: {ablauf}`) nur über einen
Auslöser `knopf`, über eine Wendung oder über ein Modul. Daten bringt kein Start mit;
`{start.…}` ist reserviert und ein Befund. Das Widget kennt `startTask(text)` (Auftrag als Zug)
und die Attribute aus `ngOnInit`; „Gespräch fortsetzen“ (K2a) bietet nur den jüngsten wartenden
Vorgang an (`POST /api/ui/vorgaenge/offen`).

### AS-4a Startschema und Teil `start` (Backend, Studio-Formular)

- **Modell:** `AblaufArea.start: list[StartFeld] | None` (Vorgabe `None`, höchstens 10 Felder).
  `StartFeld` trägt:
  - `name`: Muster wie ein Teilname;
  - `typ`: `text`, `nodeid`, `zahl` oder `ja_nein`;
  - `pflicht`: `bool`;
  - `beschreibung`: `{de, en}`, höchstens 200 Zeichen. Sie wird in AS-5 die Beschreibung des
    Werkzeug-Parameters.
  - `max_zeichen`: für `text`, Vorgabe 200, höchstens 2000.
- **Neuer Auslöser `extern`:** Start von der Gastseite (Widget-API und Attribut). Nur ein Ablauf
  mit `extern` nimmt Startdaten an; `knopf`, `text` und `modul` starten ohne Daten.
- **Prüfung der Daten** (`services/ablauf/startdaten.py`, rein): unbekannte Felder und falsche
  Typen werden abgewiesen, Pflichtfelder müssen da sein. Ein Text wird von Steuerzeichen und
  Cc/Cf bereinigt, zu lang wird abgewiesen (höchstens 500 Zeichen je Feld); eine `nodeid` ist eine UUID (`fullmatch`); eine `zahl` ist endlich;
  `ja_nein` ist `bool`. Die Fehler kommen als Codes, nie mit dem Wert. Startdaten sind Eingaben,
  nie Rechte (E2).
- **Treiber:** `starten(…, start=…)` legt den Teil `start` (`wlo.start@1`) vor dem ersten Schritt
  an. `{start.feld}` ist dann gleich `{teil.start.feld}`, und `$teil: start` mit `pfad` geht ohne
  Sonderweg.
- **Prüfung des Ablaufs:**
  - `{start.x}` mit unbekanntem `x` ist ein Befund, ebenso `start` als Ziel von `schreibt`,
    `freitext.schreibt` oder `agent.ausgabe` (reserviert).
  - Pflichtfelder ohne Auslöser `extern` (oder später `agent`) sind ein Befund: Der Ablauf
    startete nie.
  - `typen.start_teile` kennt `start`.
- **Zug:** `ablauf_starten` nimmt `action_params.start` nur bei `extern` an. Ungültige Daten
  starten nicht (`action.ablauf.startdaten`, ohne Werte), Pflichtfelder ohne Daten ebenso.
- **Simulation:** `AblaufTest.start` (dict) geht durch dieselbe Prüfung; ungültige Daten sind eine
  Abweichung.
- **Studio:** Das Formular ergibt sich aus dem Schema, mit Texten in `fields-ablaeufe`. Der
  Abschnitt heißt „Startdaten“; der Auslöser `extern` heißt „Gastseite (Widget)“.
- **Tests zuerst:** `tests/test_ablauf_startdaten.py`: Prüfung je Typ, Pflicht, unbekannt,
  Länge, Steuerzeichen, Teil `start` und Platzhalter, Befunde, Zug mit und ohne `extern`,
  Simulation.

### AS-4b Start von der Gastseite (Widget)

- **Public API:** `startAblauf(id, daten?)` am Element (`FORWARDED_METHODS`) und an der Shell.
  Sie schickt `ablauf_starten` mit `{ablauf, start}`, als Auftrags-Blase des Gastgebers (wie
  `startTask`, ehrlich sichtbar). Sie wartet auf die Shell und auf einen laufenden Zug (wie
  `startTask`).
- **Attribute:** `ablauf-start` und `ablauf-start-daten` (JSON; umbenannt, weil `start-ablauf`
  als Input mit der Methode `startAblauf` zusammenstieße), gelesen in `ngOnInit`. Sie starten
  einmal nach dem ersten Öffnen. Kaputtes JSON startet nicht und meldet sich in der Konsole des
  Gastgebers, ohne Werte.
- **Doku:** `docs/browser-plugin-einbindung.md` und `edu-sharing-demo.html` (Beispiel).
- **Tests zuerst:** Specs für `element-api` (Methode durchgereicht), die Shell (Aktion und
  Parameter, Warten auf einen laufenden Zug) und das Lesen der Attribute.

### AS-4c Wiederkehr mit Vorgang- oder Auftragskennung (R3)

- **Endpunkt** `POST /api/ui/vorgaenge/wiederkehr` mit `{vorgang}` oder `{auftrag}`:
  - nur mit bestätigter Anmeldung;
  - nur für die eigene Kennung (`aufrufer`), sonst dieselbe Antwort wie „nicht gefunden“ (kein
    Orakel);
  - Antwort: die Gesprächskennung, wie bei `/offen`; `no-store`, kein Log mit Kennung.
- **Widget:** `vorgangFortsetzen({vorgang | auftrag})` (API) und die Attribute `fortsetzen-vorgang`
  und `fortsetzen-auftrag` (umgesetzt 09.11.; Notiz `aenderungen/…-as-4c-wiederkehr.md`). Das
  Widget wechselt auf das Gespräch wie bei K2a und schickt danach „Stand prüfen“
  (`ablauf_auftrag_pruefen`), wenn der Lauf auf einen Auftrag wartet.
- **Tests zuerst:** Endpunkt (fremd, anonym, unbekannt, eigener Vorgang, eigener Auftrag) und
  Widget-Spec.

### Vorarbeit für AS-5 (aus dem Querschnitts-Review AS-4)

Was das Startschema als Parameter-Schema eines Werkzeugs trägt und was vor AS-5 zu lösen ist:

- **Trägt:** Feldnamen sind gültige JSON-Namen; `text` → `string` mit `maxLength`, `nodeid` →
  `string` mit `pattern`, `zahl` → `number`, `ja_nein` → `boolean`; `pflicht` → `required`;
  `startdaten.pruefen` prüft die Argumente.
- **Namenskonflikt:** `ablauf__<id>` gilt nach `domain/fremdwerkzeug.ist_fremd` als Werkzeug eines
  Fremdservers (am `__`). Anderer Präfix oder Trenner nötig, oder `ablauf` als Serverkennung
  reservieren.
- **Startdaten nur für `extern`:** `zug.starten` nimmt Daten nur dort an, `ausloeser._aktive`
  blendet Abläufe mit Pflichtfeldern für `agent` aus, und `start_pflicht_ausloeser` kennt `agent`
  nicht — alle drei müssen `agent` mit Daten zulassen.
- **`vorschlagen`:** Die Daten der KI reisen im Knopf (`__action__|…|ablauf_starten|{…}`) und kommen
  vom Client zurück (als Eingabe vertretbar); die Person sollte sie sehen; Größe der Knöpfe prüfen;
  `Ausloeser.modus` kennt `direkt` noch nicht.
- **Beschreibung:** Bei Auslöser `agent` ein Befund „Feld ohne Beschreibung“; Sprachwahl mit
  Rückfall auf `de`; eine Gesamtkappe des Schemas (es reist in jedem Agent-Zug mit).
- **Typen:** Es fehlen eine Auswahl (`wahl` → `enum`), Ganzzahl und `min`/`max`.
- **Herkunft positiv (Querschnitts-Review RB, Befund 1, behoben):** `zug.starten` setzt
  `start_quelle = "gastseite"` nur bei `action_params.quelle == "gastseite"` (die Widget-API
  schickt es immer) oder beim Knopf „Neu starten“ (eigene Marke), nie allein aus vorhandenen
  Startdaten und nie aus `from_host`. Ein Vorschlagsknopf der KI mit Daten bekommt eine eigene
  Quelle `ki`.
- **Simulation:** `AblaufTest` braucht eine Herkunft (`gastseite` | `ki`), sonst liefe ein KI-Start
  in der Simulation mit den Rechten der Gastseite (Querschnitts-Review RB, Befund 2).
- **Vertrauen:** Eine `nodeid` der KI kann erfunden oder eingeschleust sein — vor der Nutzung
  prüfen (Knoten da, lesbar). AS-4a Befund 10 ist entschieden (Option 2, Paket RB-1): nur Kennungen der Gastseite dürfen an lesende Werkzeuge, KI-Daten bekommen eine eigene Quelle und dürfen es nicht. Im Weg `direkt` läuft kein Preflight: dort
  `startdaten.pruefen` und eine Moderation der Texte ausdrücklich. Eine Bremse gegen Neustart-Schleifen
  wie bei der Gastseite.

## 5g. Aufgaben AS-5 — Abläufe als Werkzeuge der KI (D1)

Schritt 0: `/better-coding-workflow` laden.

**Ist:**
- **Werkzeug:** Seit A2a gibt es ein Sammelwerkzeug `ablauf_vorschlagen` (`services/ablauf/vorschlag.py`)
  mit der Kennung als Aufzählung. Die Schleife merkt sich die Wahl
  (`AgentRun.ablauf_vorschlaege`). `turn_assembly` setzt daraus den Knopf
  `__action__|<Titel>|ablauf_starten|{"ablauf": id}`.
- **Startdaten:** Keine. Abläufe mit Pflichtfeldern blendet `ausloeser._aktive` für `agent` aus.
  `zug.starten` nimmt Daten nur bei `extern`.
- **Muster-Modus und `direkt`:** fehlen.

**Entscheide (selbst getroffen nach Nutzerauftrag 09.11., dokumentiert):**

| # | Frage | Entscheid | Grund |
|---|---|---|---|
| A5-1 | Ein Werkzeug je Ablauf oder ein Sammelwerkzeug? | **Je Ablauf** ein Werkzeug, dessen Parameter das Startschema sind (wie D1). Das Sammelwerkzeug `ablauf_vorschlagen` entfällt. | Unterschiedliche Parameter je Ablauf lassen sich in einem Werkzeug nur mit `oneOf` ausdrücken, und das füllen Modelle schlecht aus. Zwei Wege nebeneinander wären doppelte Logik. |
| A5-2 | Name | `ablauf-<id>` (Bindestrich) | `ablauf__<id>` gälte nach `fremdwerkzeug.ist_fremd` als Werkzeug eines Fremdservers. Ablauf-Kennungen sind Python-Bezeichner und enthalten nie `-`. Kein MCP-Werkzeug beginnt mit `ablauf-`. Für OpenAI- und Anthropic-Namen ist `-` erlaubt. |
| A5-3 | Herkunft der KI-Daten | Quelle `ki` (`startdaten.QUELLE_KI`). Der Knopf trägt `start_quelle: "ki"`, `zug.starten` gibt KI-Daten **nie** die Rechte aus Option 2 (Kennungen an lesende Werkzeuge). | Entscheid AS-4a, Befund 10 und Querschnitts-Review RB, Befund 1. Eine `nodeid` der KI kann erfunden oder eingeschleust sein. |
| A5-4 | Wer nimmt Startdaten an? | `extern` wie bisher. Neu auch `agent`, nur über den Knopf und gegen das Startschema geprüft. | Daten sind Eingaben, nie Rechte. Der Knopf kommt vom Client zurück, er darf also nicht mehr können als die Gastseite. |
| A5-5 | `direkt` | **Später** (AS-5c, eigenes Teilpaket). Bis dahin schlägt die KI immer per Knopf vor. | Ein Start mitten in der Agent-Antwort braucht Treiber-Ausgabe im selben Zug und eine Bremse gegen Schleifen. Der Knopf ist die Geste der Person. |
| A5-6 | Muster-Modus | **AS-5b**: Ein Muster nennt `ablauf-<id>` in `tools:` (Katalog `tools`). Die Werkzeugschleife des Musters merkt den Vorschlag wie die Agent-Schleife. | D1: beide Modi. Getrennt, weil die Schleife des Musters ein eigener Codepfad ist. |
| A5-7 | Größe | Höchstens 6 Ablauf-Werkzeuge je Zug, Beschreibung höchstens 600 Zeichen, KI-Daten je Knopf höchstens 2000 Zeichen (sonst kein Knopf, die Quittung sagt es dem Modell). | Die Schemas reisen in jedem Agent-Zug mit (Kosten, Cache). Lange Knöpfe gehen sonst an Längengrenzen verloren. |
| A5-8 | Sieht die Person die Daten? | Die Beschriftung bleibt der Titel. Die Quittung verlangt vom Modell, Ablauf **und** Daten in einem Satz zu nennen. Der erste Schritt zeigt sie über Platzhalter. | Ein Knopf mit langem Text wäre unlesbar. Der Klick ist die Zustimmung zu dem, was der Satz darüber sagt. |

**AS-5a (Agent-Modus, Knopf):**
1. `startdaten`: `QUELLE_KI`, `werkzeug_schema(ablauf, lang)`. Feldtypen: `text` → `string` mit
   `maxLength`, `nodeid` → `string` mit `pattern`, `zahl` → `number`, `ja_nein` → `boolean`;
   `required`; die Beschreibung in der Sprache, Rückfall auf `de`.
2. `vorschlag.py`: `werkzeuge(lang)` (je Ablauf eines, höchstens 6), `ist_ablauf_werkzeug(name)`,
   `kennung(name)`. `merken(vorschlaege, name, args)` prüft die Daten mit `startdaten.pruefen`.
   `schnellantworten` baut den Knopf mit `start` und `start_quelle: "ki"`; über 2000 Zeichen kein
   Knopf.
3. `agent_tools`/`agent_loop`/`respond_agent`/`turn_assembly`: die Werkzeugliste statt eines
   einzelnen Werkzeugs; die Prüfung `ist_ablauf_werkzeug`. Die Vorschläge sind Dicts
   `{ablauf, start}`.
4. `ausloeser`: `_aktive("agent")` lässt Pflichtfelder zu; `vorschlaege()` unverändert, sonst
   Voraussetzungen.
5. `zug.starten`: Daten auch bei `agent` (per Knopf); `start_quelle` positiv (gastseite oder
   nichts). KI-Daten: Quelle `ki`, im Lauf ohne Rechte.
6. `pruefung`: Bei Auslöser `agent` ist jedes Startfeld ohne Beschreibung ein Befund. Der Befund
   `start_pflicht_ausloeser` gilt nicht mehr für `agent`.
7. Simulation: `AblaufTest.quelle` (`gastseite` | `ki`, Vorgabe `gastseite`) — Daten bei `extern`
   oder `agent`, die Rechte nur mit `gastseite` (Querschnitts-Review RB, Befund 2).
8. Studio: Feldtexte (Hinweis „Beschreibung wird Teil des Werkzeugs der KI“), Bereichsschema neu
   exportieren.
9. Tests zuerst; danach Review mit Befundbehebung.

**AS-5a umgesetzt und reviewt (10.11.).** **AS-5b umgesetzt (10.11.)** — **AS-5b (Muster-Modus):** Katalog `tools` um `ablauf-<id>` erweitern; `response_tool_selection`
bietet sie an, wenn das Muster sie nennt; Werkzeugschleife des Musters merkt den Vorschlag;
`turn_assembly` wie im Agent-Weg.

**AS-5c (`direkt`):** offen; erst nach AS-5a/b und mit eigener Bremse.

## 5h. Aufgaben AS-U — Oberfläche für die Person im Widget (D10, E5)

Schritt 0: `/better-coding-workflow` und `/better-coding-frontend` laden.

**Ist (Bestandsaufnahme 10.11.):**
- **Laufzustand:** steht in `Vorgang.akte["lauf"]` (`ablauf`, `fassung`, `schritt`, `status`).
  Die Sitzung trägt den Verweis `entities["_vorgang"]` mit `lauf{ablauf, schritt, status,
  fassung}` und `teile{name: {v, z}}`, wobei `z` die Zusammenfassung ist.
- **Öffentlich:** In `UiInfo` steht nichts davon, nur indirekt `ui.pattern = "ABLAUF: id/schritt"`
  bei Antworten über `zug_basis.antwort`.
- **Abbrechen:** Es gibt keinen allgemeinen Abbruch. `zug_basis.abbrechen` ist da (beendet auch
  den Auftrag); dazu kommen die statusgebundenen Abbrüche für Auftrag und Freigabe.
- **Schrittnamen:** `Schritt` hat keinen Namen. Eine Zählung „n von m“ gibt es nirgends;
  `pruefung.nachfolger` liefert die Kanten.
- **KI-Etikett:** „KI-generierte Antwort“ steht an **jeder** Bot-Nachricht
  (`chat-shell.component.html`).
- **Liste der Vorgänge:** `POST /api/ui/vorgaenge/offen` liefert höchstens einen wartenden Vorgang
  eines anderen Gesprächs. Ein Löschen einzeln gibt es nur intern (`vorgaenge.loeschen`).

**Entscheide (selbst getroffen nach Nutzerauftrag 09.11., dokumentiert):**

| # | Frage | Entscheid | Grund |
|---|---|---|---|
| U-1 | Woher kennt das Widget den Stand? | Neues öffentliches Feld `ui.ablauf` an **jeder** Antwort, solange im Gespräch ein Lauf nicht beendet ist. Es wird aus dem Sitzungsverweis gerechnet, ohne DB, und im Debug-Block gespeichert, damit der Verlauf ihn nach dem Neuladen wiederherstellt. Das Widget nimmt den Stand der **letzten** Bot-Nachricht. | Ein eigenes Abfrage-Endpoint bräuchte Polling. Der Verweis ist ohnehin aktuell (Preflight frischt ihn auf). |
| U-2 | Inhalt von `ui.ablauf` | `{id, titel, nr, von, status}`; `status` ∈ `laeuft`, `wartet_wahl`, `wartet_person`, `wartet_auftrag`, `wartet_freigabe`, `wartet_ki` (der Status des Laufs; ein neuer Wert ist möglich, das Widget zeigt dann nur den Schritt); `teile`: `[{name, text}]` (Zusammenfassungen, ohne den Teil `start`, Kennungen in UUID-Form entfernt). | Genau das braucht die Leiste. Startdaten und Kennungen gehören nicht in die Anzeige (D10: „ohne nodeIds“). |
| U-3 | „Schritt n von m“ | `nr` = Länge des längsten Wegs vom ersten Schritt bis zum aktuellen; `von` = `nr` − 1 + längster Weg von dort bis zu einem Ende. Rückwege zählen nicht (einfache Wege, je Schritt höchstens einmal). | So passt `von` zum aktuellen Weg nach einer Verzweigung und wächst nicht durch Schleifen. Gerechnet in `services/ablauf/fortschritt.py` auf `pruefung.nachfolger`. |
| U-4 | Schrittnamen | **Nicht in AS-U.** Die Leiste zeigt „Schritt n von m“ und den Status in Worten. Ein optionales Feld `Schritt.name` kann später kommen. | Schritt-Kennungen sind technisch („lesen“, „e“). Ein neues Feld zöge Studio, Prüfung und Schema nach sich, ohne dass die Leiste davon abhängt. |
| U-5 | Abbrechen | Neue Direktaktion `ablauf_abbrechen` mit Rückfrage („Ablauf wirklich abbrechen? Ein laufender Auftrag endet mit.“), Knopf mit `bestaetigt`. Danach `zug_basis.abbrechen`. Nur der eigene Lauf des Gesprächs. | Ein Abbruch ist nicht umkehrbar und beendet auch einen Kestra-Job, darum mit Rückfrage. Der Baustein ist vorhanden. |
| U-6 | „Später fortsetzen“ (seit Q-12: Knopf „Einklappen“) | Nur im Widget: Die Leiste klappt zu einer Zeile zusammen („Ablauf pausiert — hier weitermachen“). Der Lauf bleibt, wie er ist (bis 30 Tage). Keine Backend-Aktion. | Ein wartender Lauf wartet ohnehin. Die Person soll nur Platz bekommen und wissen, dass nichts verloren geht. |
| U-7 | KI-Etikett | Neues Feld `ui.fester_text` an Antworten aus dem Ablauf-Treiber und seinen festen Hinweisen (`zug_basis.antwort`, `nur_text`). Das Widget lässt dort „KI-generierte Antwort“ weg. Ein KI-Schritt läuft über den Agent-Weg und bleibt gekennzeichnet. | Feste, redaktionelle Texte als KI-generiert zu kennzeichnen ist falsch (Abnahme AS-4). Ein Etikett zu viel ist weniger schlimm als eines zu wenig, darum nur dort, wo es sicher fest ist. |
| U-8 | „Meine Vorgänge“ | **Eigenes Teilpaket AS-Ud:** Endpunkte für die Liste aller eigenen wartenden Vorgänge und das Löschen eines einzelnen (nur die Besitzerin, Rückfrage im Widget); dazu eine Ansicht im Widget. | Größerer Oberflächen-Teil mit eigener Prüfung der Rechte. Getrennt reviewbar. |

**Teilpakete:**
1. **AS-Ua (Backend):**
   - `fortschritt.py` (U-3) und `ui.ablauf` (U-1, U-2): gesetzt in `turn_persist`/`publikum`,
     gespeichert im Debug-Block;
   - `ui.fester_text` (U-7);
   - Direktaktion `ablauf_abbrechen` (U-5), eingetragen in Preflight und `preflight_ablauf`;
   - Tests zuerst, Vertragstest `test_publikum`, OpenAPI exportieren.
2. **AS-Ub (Widget, Leiste):**
   - Komponente über dem Eingabefeld: Titel, „Schritt n von m“, Status in Worten,
     „Abbrechen“ (sendet die Direktaktion), „Später fortsetzen“ (zuklappen, U-6);
   - „Gesammelte Daten“ als aufklappbare Liste der Teile;
   - Stand aus der letzten Bot-Nachricht, auch nach dem Neuladen;
   - kein KI-Etikett bei `fester_text`;
   - Tastatur, `aria-live` für den Wechsel des Schritts, M3-Tokens, de/en; Specs.
3. **AS-Ud (Meine Vorgänge):** Endpunkte `POST /api/ui/vorgaenge/liste` und
   `POST /api/ui/vorgaenge/loeschen`, Ansicht im Widget, Tests.
4. Danach ein Review je Teilpaket, ein übergreifendes Review über AS-U und eine Browser-Abnahme
   gegen eine Wegwerf-DB.

## 5i. Zwischenpaket BU — Widget-Bündel verkleinern (vor AS-Ud)

Schritt 0: `/better-coding-workflow` und `/better-coding-frontend` laden.

**Anlass:** Nach AS-Ub stand `main.js` bei 689,5 kB roh / 200,0 kB gzip, also an beiden harten
Grenzen (690 / 200). Jede weitere Widget-Oberfläche (AS-Ud) wäre gescheitert. Die Analyse vom
10.11. hat die Posten gemessen.

**Entscheide (selbst getroffen, dokumentiert):**

| # | Frage | Entscheid | Grund |
|---|---|---|---|
| BU-a (überholt durch BU-3: das Panel lädt jetzt nach) | Debug-Panel | Die vier Angular-Pipes (`number`, `json`, `keyvalue`, `slice`) werden durch Methoden mit gleicher Ausgabe ersetzt (Rundung wie `DecimalPipe` auf den Dezimalziffern). Das Panel bleibt im Widget. | −4 kB gzip bei geringem Risiko. Das Panel kann „Im Widget ausprobieren“ (AS-8) dienen. Ein Auslagern bräuchte einen rahmenlosen Nachbau. |
| BU-b | Ungenutzte Icons | **Bleiben.** | Das Icon der Kopfzeilen-Knöpfe ist im Studio ein freies Feld („ein Icon aus dem Widget“). Ein entferntes Icon würde in einer bestehenden Konfiguration ohne Warnung zu `explore`. 1,1 kB rechtfertigen keine stille Änderung. |
| BU-c | Logo | Pfadzahlen auf eine Nachkommastelle gerundet. | −0,8 kB gzip. Ein Pixelvergleich bei 512 px zeigt Abweichungen nur in der Kantenglättung. |
| BU-d | `ui_strukturentwurf` | Wird ein nachgeladenes, rahmenloses Custom Element nach dem U3-0-Muster (`laden: "bei_bedarf"`). Die Logikdateien bleiben unverändert. Die bisherige Spec wird auf das Element übertragen und ist der Verhaltensvertrag. | Mit 32 kB roh der größte seltene Posten im Bündel. |
| BU-e | Stile nachgeladener Module | `module:register` übersetzt `ui-<name>.element.scss` mit dem vorhandenen dart-sass in `ui-<name>.stil.generated.ts` (eingecheckt). `--pruefen` (CI) meldet einen veralteten Stand. | Der Entwurf teilt `_baum/_baum.scss` mit dem Themenbaum. Ein Nachbau als Zeichenkette (wie beim Upload) liefe auseinander. |
| BU-f | Statusansage | `BaumAnsage` bekommt einen rahmenlosen Kern (`AnsageKern`). Die Angular-Hülle für den Themenbaum bleibt im Verhalten gleich. | Das Element-Bündel darf kein Angular enthalten. Die Ansage-Regel (gleicher Text → leeren, 100 ms, neu setzen) soll es nur einmal geben. |
| BU-g | Icons im Element | Die beiden SVGs (`edit_note`, `chevron_right`) liegen als eigene Konstanten im Modul. Eine Spec prüft, dass sie gleich `ICONS` sind. | Ein Import von `ICONS` zöge alle Icons ins Modul-Bündel. |

**Teilpakete:** BU-1 (a–c) → BU-2 (d–g). Ziel: `main.js` unter der Warnschwelle von 190 kB gzip.

**BU-3 (nach AS-Ud, Entscheid Ud-5 neu):** Das Debug-Panel wird ein nachgeladenes, rahmenloses
Element. Nachgeladen werden bisher nur UI-Module (Ordner `ui-module/src/ui-*` mit Manifest). Der
Nachlade-Bau bekommt deshalb eine zweite Quelle für **Widget-Teile ohne Manifest**: Diese sind kein
KI-Werkzeug und nicht im Register; sie haben denselben Index, dasselbe SRI und denselben Pfad
`/widget/module/`. Die bisherige Spec des Panels (17 Fälle) wird auf das Element übertragen.
Ziel: wieder unter 190 kB gzip. **Umgesetzt 10.11.:** 186,9 kB gzip.
Je ein Review mit Befundbehebung. Die Browser-Abnahme des Entwurfs folgt mit der AS-U-Abnahme.

## 5j. Aufgaben AS-Ud — Meine Vorgänge (D10, U-8)

Schritt 0: `/better-coding-workflow` und `/better-coding-frontend` laden.

**Entscheide (selbst getroffen 10.11., dokumentiert):**

| # | Frage | Entscheid | Grund |
|---|---|---|---|
| Ud-1 | Was zeigt die Liste? | Die eigenen, **nicht abgeschlossenen** Vorgänge (aktiv und wartend) in **anderen** Gesprächen, alle (Sicherung 20; zuerst hieß es `MAX_JE_PERSON` = 3, Review AS-Ud, Befund 3), die jüngsten zuerst. Je Vorgang: `id`, `titel`, `ablauf` (Kennung, wie `/offen`), `status`, `geaendert`, `session_id`. Das Widget zeigt Titel, Zustand in Worten und Datum. | Wie `/offen`, nur vollständig. Den Vorgang des aktuellen Gesprächs steuert die Ablauf-Leiste (Abbrechen) bzw. „Arbeitsstand löschen“. Ein Löschen „von außen“ ließe dort eine tote Leiste stehen. |
| Ud-2 | Rechte | Wie `/offen`: nur mit bestätigter Anmeldung (403 `nur_angemeldet`), Besitzerin = Kennung der Anmeldung, `no-store`, IP-Drossel, kein Log mit Kennungen. | Die Gesprächs-Kennung ist ein Geheimnis. |
| Ud-3 | Löschen eines Vorgangs | `POST /api/ui/vorgaenge/loeschen` `{session_id, vorgang}`. Nur ein eigener Vorgang eines **anderen** Gesprächs, sonst 404 `unbekannt` (kein Orakel). Ein offener Auftrag endet nach dem Festschreiben auch bei der b-api, wie bei „Arbeitsstand löschen“. Ablage und Aufträge gehen per Kaskade. | Ein Auftrag liefe sonst bei der b-api weiter (Grenze 20 je Schlüssel). |
| Ud-4 | Ort im Widget | Ein Knopf „Meine Vorgänge“ neben dem Anmelde-Knopf, nur für Angemeldete. Er klappt über dem Eingabefeld eine Liste auf (wie die Leiste): je Vorgang Titel, Zustand in Worten, Datum, „Fortsetzen“ (Wechsel wie bei `/offen`) und „Löschen“ mit Rückfrage im Panel. Leer: ein Satz. Fehler: ein Satz mit „Erneut versuchen“. | Der Docstring von `vorgang_aktion` nennt den Einstieg außerhalb eines Ablaufs als offene Entscheidung. |
| Ud-5 | Bündel | Eine Angular-Komponente im Haupt-Bündel, wenn sie ≤ 2 kB gzip kostet und das Bündel unter 190 kB bleibt. Sonst ein nachgeladenes Element. | Höchstens drei Einträge, kleine Ansicht. Für ein Nicht-Modul-Element müsste der Nachlade-Bau erweitert werden. |
| Ud-5 neu (nach Messung) | Bündel | **Gemessen:** +3,15 kB gzip / +14 kB roh, also 190,6 kB statt 187,4. Darin Komponente mit Stil 7,6 kB roh, Texte de/en 2,4 kB, Controller 1,3 kB, API und Lesen 2 kB. „Meine Vorgänge“ **bleibt trotzdem im Haupt-Bündel**. Zum Ausgleich wird das Debug-Panel nachgeladen (BU-3, §5i). | Der Knopf steht für jede angemeldete Person in der Eingabezeile, ist also keine seltene Oberfläche; ein Nachladen bei jedem Öffnen wäre die schlechtere Bedienung. Das Debug-Panel sieht nur die Redaktion, es bringt rund 4 kB und ist rein anzeigend (geringes Risiko). Bis BU-3 liegt das Bündel 0,5 kB über der Warnschwelle, die harte Grenze von 200 kB ist nicht in Gefahr. |

**Bewusst hingenommen (Review AS-Ud, Kleinigkeit 11):** Ist das Gespräch eines gelöschten Vorgangs
in einem zweiten Tab offen, zeigt dessen Ablauf-Leiste bis zum nächsten Zug noch den toten Lauf
(`ui.ablauf` der letzten Antwort). Der nächste Zug räumt auf (`arbeitsstand.auffrischen`): Der
Verweis fällt weg, und eine angemeldete Person übernimmt dann ihren jüngsten offenen Vorgang (Review
V1, Befund 1) — die Leiste zeigt danach dessen Lauf, auch wenn er in einem anderen Gespräch begann
(Querschnitts-Review Q-9; bewusst, eine neue Sitzung soll ihren Vorgang wiederfinden). Ein Push an
fremde Tabs gibt es nicht; der Fall ist selten.

**Aufgaben:** Backend zuerst (Tests, dann Endpunkte, Vertragsliste und OpenAPI), danach Widget (Controller rein, Komponente, i18n de/en, Specs), dann ein Review mit Befundbehebung. Danach ein übergreifendes Review über AS-U und BU sowie die Browser-Abnahme gegen eine Wegwerf-DB.

## 5k. Querschnitts-Review AS-U + BU (10.11.) — Befunde und Entscheide

Ergebnis: 0 kritisch, 4 schwer, 12 mittel, 4 klein. Nach der Behebung folgt ein zweites, unabhängiges
Review (Projektregel bei mehreren schweren Befunden). Stand je Befund: **offen** / **erledigt**.

| # | Befund | Entscheid | Stand |
|---|---|---|---|
| Q-1 | schwer: Angemeldete Personen haben nach Neuladen, Fortsetzen oder Wiederkehr keine Leiste. Der Verlaufsabruf trägt keinen Zugangsblock, der Verweis passt nie. | Variante a: Der Verlauf schickt den Block mit (`accessBlockHeaders`, CORS ist global offen); `_ablauf_stand` übernimmt ihn und bestätigt die Anmeldung nur mit Block. Die „Grenze“ in AS-Ua entfällt. Tests Backend + Widget. | erledigt |
| Q-2 | schwer: Löschen über „Meine Vorgänge“ lässt einen offenen Schreib-Plan im anderen Gespräch liegen; „Plan fortsetzen“ schriebe weiter. | `plan_fortsetzen.weiter` setzt einen Plan mit Ablauf-Marke nur fort, solange der Verweis des Gesprächs auf einen Lauf dieses Ablaufs in `wartet_freigabe` zeigt; sonst verwirft es ihn (`write.planNone`). Test. | erledigt |
| Q-3 | schwer: `innerHTML` mit String im Strukturentwurf bricht auf Seiten mit Trusted Types. | Symbole als `viewBox` + `d`, gebaut mit `createElementNS`. Spec mit Trusted-Types-Attrappe. | erledigt |
| Q-4 | schwer: Debug-Panel, Leiste, Liste und Hinweis stapeln sich über dem Eingabefeld und schneiden es bei wenig Höhe ab. | Ein gemeinsamer Bereich über der Eingabe, höchstens 50 % der Höhe, scrollt selbst. Der Hinweis „Gespräch fortsetzen“ ruht, solange die Liste offen ist (NIT 18). E2E bei 320×360. | erledigt |
| Q-5 | „Arbeitsstand löschen“ liest offene Aufträge ohne Zeilensperre. | Die Zeilen der Besitzerinnen werden vor dem Lesen mit `FOR UPDATE` gesperrt, wie bei `/loeschen`. Test + PG-Test. | erledigt |
| Q-6 | Ohne Schlüssel der Person endet der Auftrag bei der b-api nicht, die Rückfrage verspricht es aber. | `/loeschen` meldet `auftrag_laeuft_weiter`; das Widget sagt es in einem eigenen Satz. | erledigt |
| Q-7 | Der Vorgangsstatus ist gröber als der Laufstatus („Offen“ für beendete, „wartet auf dich“ statt Freigabe/KI). | `/liste` liefert zusätzlich `lauf_status`; das Widget nutzt die Wörter der Leiste. Beendet heißt „Ablauf beendet“. | erledigt |
| Q-8 | Der Titel ist immer deutsch, die Leiste zeigt ihn in der Sprache des Zugs. | `/liste` und `/offen` nehmen `sprache`; ist der Titel der des Ablaufs, kommt er in dieser Sprache. | erledigt |
| Q-9 | Der Plantext zu Kleinigkeit 11 stimmt nicht: der nächste Zug übernimmt den jüngsten offenen Vorgang. | Text berichtigen. `juengster` bleibt (Review V1, Befund 1: eine neue Sitzung findet ihren Vorgang wieder). | erledigt |
| Q-10 | Hülle des Debug-Panels und Platzhalter der Module doppeln die Lade-Logik; die Hülle hängt das Element vor den Eigenschaften ein. | Reihenfolge wie im Vertrag (erst setzen, dann einhängen). Kein gemeinsamer Helfer: zwei Nutzer mit verschiedenem Rückfall (Textfassung vs. Satz), je rund 15 Zeilen; §2.5 nennt beide Verträge. | erledigt |
| Q-11 | Im Dev-Server lädt das Debug-Panel nie. | Mit Review BU-3, Befund 2 erledigt (Satz ohne falschen Grund, §2.5). | erledigt |
| Q-12 | Begriffe: „Vorgang“, „Vorhaben“, „Arbeitsstand“; „Später fortsetzen“ klappt nur zu, „Fortsetzen“ wechselt das Gespräch. | Der Leisten-Knopf heißt „Einklappen“ / „Collapse“. Die Bot-Texte bleiben: „Arbeitsstand löschen“ umfasst auch das Dokument, „Neues Vorhaben“ beginnt etwas Neues; Glossar in `docs/ui-module.md`. | erledigt |
| Q-13 | Veraltete Angaben in `offene-befunde` §1/§4 und BU-a. | Aktualisieren; das Chip-Problem (≥ 4 Wahl-Chips) nach §1. | erledigt |
| Q-14 | „höchstens drei“ in Vertrag, Docstrings, Plan und Notiz. | „alle offenen, Sicherung 20“. | erledigt |
| Q-15 | `docs/ui-module.md` Z. 33 und 426 sind veraltet; BU-3-Notiz ohne Review. | Aktualisieren; Review in der BU-3-Notiz ist nachgetragen. | erledigt |
| Q-16 | Tests an den Nahtstellen fehlen. | Mit Q-1…Q-4: Shell-Spec mit Leiste, Liste und Hinweis; E2E der Leiste (320 px, Tastatur); Kontrast-E2E für Leiste und Liste; Backend-Test `/loeschen` mit Plan; Trusted-Types-Spec. | erledigt |
| Q-17 | `widgetTeile` doppelt. | Mit Review BU-3, Befund 11 erledigt. | erledigt |
| Q-18 | Hinweis und Liste bieten zugleich „Fortsetzen“. | Mit Q-4. | erledigt |
| Q-19 | Plan 190,5 vs. Notiz 190,6 kB. | Auf 190,6 berichtigen. | erledigt |
| Q-20 | Vier Setter zeichnen viermal. | Mit Review BU-3, Befund 4 erledigt. | erledigt |

## 5l. Zweites Review nach dem Querschnitt (10.11.) — Befunde und Entscheide

Ergebnis: 17 von 20 Behebungen stimmen am Code; Q-6, Q-8, Q-16 waren unvollständig. Neu: 0 kritisch,
1 schwer, 7 mittel, 3 klein.

| # | Befund | Entscheid | Stand |
|---|---|---|---|
| Z-1 | schwer: `fetchHistory` wartet nicht auf den Ticket-Tausch; nach einer Anmeldung lädt niemand den Stand neu. In einem neuen Tab fehlt die Leiste weiter. | `fetchHistory` wartet auf `anmeldung`. Nach gelungener Anmeldung (Ticket oder von Hand) holt die Shell den Stand einmal neu (Verlauf mit `limit` 1) und zeigt ihn bis zur nächsten Serverantwort. | erledigt |
| Z-2 | `/offen` bekommt keine `sprache` vom Widget (Rest von Q-8). | Mitschicken, Spec. | erledigt |
| Z-3 | `_lauf_wartet` vergleicht nur Ablauf und Status; ein übernommener anderer Vorgang mit demselben Ablauf ließe den alten Plan weiterschreiben. | Zusätzlich `schritt` der Marke gegen den Verweis; dazu die Freigabe-Kennung im Verweis (`freigabe_id`) gegen `marke.id`. | erledigt |
| Z-4 | `alle_sperren` ohne Reihenfolge: Deadlock möglich; ein Deadlock endet als Fehler. | `ORDER BY id`; ein Deadlock (sqlstate 40P01) in „Arbeitsstand löschen“ antwortet wie ein Konflikt. | erledigt |
| Z-5 | Der Stand im Verlauf kommt nur aus dem Verweis: ein anderswo gelöschter oder beendeter Vorgang zeigt auch nach dem Neuladen eine tote Leiste. | `_ablauf_stand` liest den Vorgang einmal per Kennung; fehlt er oder ist er abgeschlossen, kein Stand. | erledigt |
| Z-6 | Die Bestätigung im Verlauf wartet bis zu 5 s auf den MCP. | Eigene kurze Frist (1 s), danach ohne Stand. | erledigt |
| Z-7 | Der Satz „ohne deine Anmeldung“ nennt die falsche Ursache; die Rückfrage verspricht das Ende ohne Bedingung (Rest von Q-6). | Wortlaut: der Zugang darf den Auftrag bei der b-api nicht beenden; die Rückfrage sagt „wird hier beendet“. | erledigt |
| Z-8 | Nach dem Abmelden bleibt die Leiste mit Abbruch und gesammelten Daten stehen. | Der Stand trägt `persoenlich`; ohne Zugangsblock blendet das Widget eine persönliche Leiste aus. | erledigt |
| Z-9 | `/loeschen` prüft vor der Sperre. | Erst sperren, dann lesen und prüfen. | erledigt |
| Z-10 | Doku: Stände in §5k, 186,9 statt 187,3 kB, zwei alte Kommentare „Später fortsetzen“. | Angleichen. | erledigt |
| Z-11 | Zwei verschachtelte Scrollflächen (Debug-Panel in `.ueber-eingabe`). | Das Panel begrenzt sich nicht mehr selbst. | erledigt |

## 5m. Aufgaben AS-7 — Führungen (E3 A, D4 `wenn_seite`)

Schritt 0 je Teilpaket: `/better-coding-workflow` (bei Widget-Teilen auch `/better-coding-frontend`)
laden.

**Ist (10.11.):**
- Die Tour (`domain/tour.py`) navigiert mit Chips `__guide__|Label|URL`; das Widget übergibt dabei
  die Sitzung über Domänen hinweg (`?bsid=`).
- Die Ankunft erkennt die Tour am **Tour-Tick**, einem unsichtbaren Zug nach jedem Seitenaufruf,
  solange das Tour-Flag in `localStorage` steht (`controllers/tour.controller.ts`).
- Der **Kontext-Ping** (`page_event: context_open`) kommt nur auf erkannten WLO-Seiten
  (`shouldSendContextPing`). Allgemeine Seiten wie `/mitmachen/` melden nichts.
- `Environment.page` trägt den Pfad der Gastseite. Die Tour normalisiert ihn mit `tour._norm_path`.

**Entscheide (selbst getroffen nach Nutzerauftrag, dokumentiert):**

| # | Frage | Entscheid | Grund |
|---|---|---|---|
| F-1 | Form des Schritts | Neuer `typ: seite`. Felder: `url` (Pfad mit `/` oder `https://`), `label` je Sprache (Text des Chips), `text` (Satz über dem Chip), `ankunft` (Liste von Pfadmustern), `weiter`. Ohne `ankunft` zeigt der Schritt den Chip und geht sofort weiter, wie eine Nachricht. Mit `ankunft` wartet der Lauf (`wartet_seite`), bis die Person auf einer passenden Seite ist. | Ein Schritt deckt „Link anbieten“ und „auf Ankunft warten“ ab. Das gibt keine zweite Schrittart. |
| F-2 | Navigation | Ein Chip `__fuehrung__|Label|URL`. Das Widget zeigt ihn wie den Lotsen-Chip der Tour (`__guide__`): Er öffnet die Seite und übergibt die Sitzung. Ein eigenes Präfix, weil der Widget-Nachlauf `__guide__`-Chips außerhalb der Tour zu Markdown-Links macht oder entfernt. Wie Wahl-Chips übersteht er jede Höchstzahl (`ist_wahl_knopf`). Die Prüfung verlangt einen Pfad mit `/` oder eine `https://`-Adresse ohne Zugangsdaten, ohne `|` und ohne Leerraum. | Vorhandene Mechanik im Widget; der Nachlauf bleibt unberührt. |
| F-3 | Muster | Pfadmuster mit `*` als Platzhalter (fnmatch auf dem normalisierten Pfad, ohne Groß-/Kleinschreibung), höchstens 10 je Liste, je 200 Zeichen. Keine regulären Ausdrücke. | Wie die Wendungen der Text-Auslöser: für die Redaktion lesbar, kein ReDoS. |
| F-4 | Ankunft erkennen | Ein eigener **Seiten-Ping** (`page_event: ablauf_seite`, Hintergrund-Zug wie Tour-Tick und Kontext-Ping; ein eigener früher Knoten nach `tour` antwortet, ohne Nutzernachricht). Das Widget schickt ihn nach einem Seitenaufruf, wenn der zuletzt bekannte Stand `wartet_seite` ist; den Stand liest es aus dem wiederhergestellten Verlauf (`ui.ablauf` der jüngsten Antwort; `sessionStorage` ist unnötig, weil ein `seite`-Schritt immer Text trägt). Nach einer SPA-Navigation pingt es neu, und trifft der Ping auf einen laufenden Zug, holt es ihn nach (Review AS-7b). Passt die Seite, läuft der Lauf weiter, und die Antwort erscheint. Passt sie nicht, bleibt die Antwort leer und unsichtbar. | Der Kontext-Ping deckt allgemeine Seiten nicht ab; das Tour-Flag gehört der Tour. Ohne wartenden Lauf geht kein Ping hinaus, das kostet also keine Last auf jeder Seite. |
| F-5 | Getippter Text an `wartet_seite` | Wie bei `wartet_wahl`: Der Text geht an die KI, der Lauf wartet weiter, und der Chip des Schritts steht wieder unter der Antwort. | Gleiche Regel wie D2. Die Person verliert den Weg zum Ziel nicht. |
| F-6 | `wenn_seite` | Neue Regel der Verzweigung `wenn_seite: [Muster]`, gilt allein wie `wenn_wert`. Grundlage ist die Seite des Zuges (`Environment.page`). Die Simulation nimmt die Seite aus dem Testfall (`seite`, Vorgabe `/`). | D4. Der Wert kommt vom Widget, ist aber nur ein Vergleich und kein Recht. |
| F-7 | Auslöser `seite` | `{art: seite, muster: [...]}` startet nicht von selbst. Das Widget bietet den Ablauf als Chip unter der Begrüßung an, wenn die Seite beim Öffnen passt und kein Lauf wartet. Die Liste kommt im Boot-Bündel `GET /api/config/guide-mode` (Feld `ablauf_seiten`: `id`, `titel`, `muster`; ein Rundlauf weniger als ein eigener Endpunkt). Die Begrüßung rechnet die passenden Chips beim Zeigen aus dem aktuellen Pfad. | Ein Start ohne Zutun überrascht und verdrängt die Begrüßung. Ein Ping auf jeder Seite kostet Last; der Abgleich im Widget kostet nichts. |
| F-8 | Bestehende Tour | Bleibt unverändert. Der Beispiel-Ablauf „Führung“ (`seed`, `aktiv: false`) zeigt dieselben Schritte als Ablauf. | E3 A; der Umzug kommt später hinter einen Schalter (§6). |

**Teilpakete (je Review mit Befundbehebung, danach Querschnitt):**
1. **AS-7a (Backend):**
   - Modell `seite` (F-1), `wenn_seite` (F-6), Auslöser `seite` (F-7, nur Modell und Prüfung);
   - Treiber: Status `wartet_seite`, Weitergehen per Muster;
   - Direktaktion `ablauf_seite` als Hintergrund-Zug (F-4);
   - getippter Text (F-5), Prüfung (F-2, F-3), Simulation und Testfall `seite`;
   - Leistenstatus, Texte de/en; Tests zuerst.
2. **AS-7b (Widget):**
   - Seiten-Ping (F-4);
   - Status „wartet auf den Seitenwechsel“ in der Leiste;
   - Chip unter der Begrüßung (F-7) über das Feld `ablauf_seiten` im Boot-Bündel;
   - Specs, E2E.
3. **AS-7c:** Beispiel „Führung“ (F-8), Handbuch `docs/ablaeufe.md` (Kapitel Führungen), Vertragsliste.

**Stand (10.11., abends):** AS-7a, AS-7b und AS-7c sind umgesetzt und reviewt. AS-7a hatte zwei
Reviews (1 kritisch und 1 schwer, danach 1 schwer, alle behoben). Bei AS-7b traf der eine schwere
Befund nicht zu, alle mittleren sind behoben. Notizen `aenderungen/2026-11-10-paket-as-7a-…`, `…-7b-…`,
`…-7c-…`. Querschnitts-Review über AS-7 behoben (`…-querschnitt-as-7.md`), Browser-Abnahme
bestanden mit Befund L-3 (kein Kontext-Gruß neben einer wartenden Führung), behoben
(`…-browser-abnahme-as-7.md`). E2E für den Kernweg: `frontend/e2e/fuehrung.spec.ts` (10.11.).

## 5n. Aufgaben AS-8 — Im Widget ausprobieren (E4 B), Handbuch (D7)

**Ziel:** Die Redaktion startet einen Ablauf im echten Widget der Studio-Vorschau, auf Wunsch mit
Startdaten. Schreiben und Aufträge laufen dort nur als Trockenlauf.

**Ist (gemessen 10.11.):**
- Die Studio-Seite „Vorschau“ bettet das echte `<boerdi-chat>` ein (`persist-session="false"`,
  `api-url` = eigene Herkunft).
- Das Studio-Cookie (`path=/`, `SameSite=strict`, `httponly`) geht bei jeder Widget-Anfrage aus
  der Vorschau mit; eine fremde Seite kann es nicht mitschicken.
- Echte Wirkung entsteht nur an wenigen Stellen:
  - **MCP-Schreiben:** `services/mcp/client.call_mcp_tool_antwort`, wenn ein bestätigbares
    Werkzeug einen Schlüssel aus `SCHLUESSEL_FELDER` trägt. Das deckt Einlösen, Tool-Schleife,
    Agent-Schreiben und Plan-Fortsetzen ab.
  - **Ablage:** `services/ablage/mcp_ablage` (`wlo_store_batch_*` und das rohe
    `POST /api/uploads`) läuft am Client vorbei, aus den Endpunkten `api/ui_ablage.py`.
  - **Aufträge:** Start über `zug_basis.umgebung()` → `auftrag_zug.starter()`. Stand, Dateien und
    Abbruch laufen nur über `services/auftraege/client.py`.
- Es gibt weder ein Probe- noch ein Trockenlauf-Merkmal.

**Entscheide (selbst getroffen, änderbar):**

| # | Frage | Entscheid | Grund |
|---|---|---|---|
| P-1 | Wie erkennt das Backend eine Probe? | Das Widget-Attribut `probe` schickt `probe: true` in jeder Chat-Anfrage. Das Backend nimmt es nur mit gültigem Studio-Cookie an (`studio_auth.authorize`). Ohne Recht weist es den Zug ab (403 `probe_ohne_recht`), statt ihn echt laufen zu lassen (Review AS-8a, Befund 3). Die Sitzung merkt sich das als `entities._probe` und bleibt Probe (klebt). | Kein neues Ticket nötig. Das Cookie ist das Recht der Redaktion; `SameSite=strict` schließt fremde Seiten aus. |
| P-2 | Wie erreicht das Merkmal die tiefen Stellen? | Ein Zug-Merker, gebunden in `begin_turn` als geteiltes Objekt: Der Endpunkt setzt ihn aus Anfrage + Cookie, `setup` aus `entities._probe`. Die Endpunkte außerhalb des Graphen (`ui_ablage`, `ui_auftrag`, `ui_vorgaenge`) lesen `entities._probe`. Der Merker hat zwei Seiten (Review, Befund 4): `aktiv` schränkt ein und gilt auch aus der Marke; `recht` erweitert (P-6/P-7) und gilt nur mit dem Cookie dieses Zuges. `merge` verwirft `_`-Schlüssel aus der Ausgabe des Klassifikators. | LangGraph-Knoten laufen in Kontext-Kopien; ein geteiltes Objekt sehen alle (Paket 10). |
| P-3 | MCP-Schreiben im Trockenlauf | `call_mcp_tool_antwort` ruft ein bestätigbares Werkzeug mit Schlüssel nicht auf. Stattdessen kommt eine Antwort ohne Fehler, Text `probe.trocken` („Trockenlauf: Hier wäre jetzt <Werkzeug> gelaufen — geschrieben wurde nichts.“, de/en), strukturiert `{trockenlauf: true, werkzeug, complete: true}`. Vorschauen ohne Schlüssel laufen echt. | Eine Stelle deckt alle Schreibwege im Graphen ab. Die echte Vorschau zeigt den echten Plan. Ohne Aufruf entsteht auch kein `preparedRequest` (eingebetteter Modus). |
| P-4 | Ablage im Trockenlauf | `ui_ablage` `/datei` und `/abschluss` antworten in einer Probe-Sitzung mit 409 `trockenlauf`, `/vorbereiten` ebenso. Das Widget zeigt dazu einen eigenen Satz. | Das Nachbauen der Ablage-Antworten wäre eine zweite Attrappe ohne Nutzen; ehrlich abweisen genügt. |
| P-5 | Aufträge im Trockenlauf | Der Starter gibt `trocken-<hex>` zurück, ohne b-api und Schlüssel; die WLO-Anmeldung braucht er wie im Betrieb (Querschnitts-Review AS-8, Befund 3: P-8 geht vor). `client.stand` meldet für diese Kennung sofort `fertig` mit leeren `outputs`/`dateien`; `datei`/`abbrechen` fassen die b-api nicht an. „Stand prüfen“ und `/api/ui/auftrag/stand` brauchen dafür weder Schlüssel noch Anmeldung (Review, Befund 2). Ist die b-api eingerichtet, scheitert ein nicht freigeschalteter Flow wie im Betrieb (Befund 5). | Die Leiste und „Stand prüfen“ verhalten sich wie im Betrieb. Wer echte Ergebnisse durchspielen will, nimmt die Testfälle (E4 A). |
| P-6 | Inaktive Abläufe | In einer Probe darf jeder Ablauf des Katalogs starten, auch `aktiv: false`, und zwar per Direktaktion `ablauf_starten`, unabhängig von seinen Auslösern. Der Lauf trägt `probe: true`; die fünfzehn Prüfungen „Ablauf gilt noch“ gehen durch eine Funktion `treiber.gilt(ablauf, lauf)`. Vorgänge einer Probe gehören `probe:<Sitzung>` (Review, Befund 1): sie berühren keine echten Vorgänge der Person, und „Meine Vorgänge“ antwortet in der Probe 409 `trockenlauf`. | Ausprobieren vor dem Einschalten ist der Hauptzweck. Die eine Funktion ersetzt zehn gleiche Bedingungen. |
| P-7 | Startdaten in der Probe | Sie sind erlaubt, wenn der Ablauf ein Startschema hat, auch ohne Auslöser `extern`/`agent`; die Prüfung gegen das Schema bleibt. Herkunft wie von der Gastseite. | Die Probe spielt den Start von der Gastseite nach. |
| P-8 | Anmeldung | Voraussetzung `anmeldung` und Freigaben bleiben wie im Betrieb. | Die Probe zeigt, was die Person sieht; nur die Wirkung entfällt. |
| P-9 | Studio-Oberfläche | Auf der Vorschau-Seite steht ein Abschnitt „Ablauf ausprobieren“: Ablauf wählen, Startdaten (JSON, optional), „Ablauf starten“. Er baut ein neues Widget mit dem Attribut `probe` und startet den Ablauf über die Laufzeit-API `element.startAblauf(id, daten)` (Browser-Abnahme AS-8, B-1: das Attribut `ablauf-start` liest das Widget nur beim Verbinden und je Tab einmal). Am Ablauf steht der Knopf „Im Widget ausprobieren“ → `vorschau?ablauf=<id>`. Der Hinweis lautet: es gilt die gespeicherte Fassung. | Nutzt die vorhandene Vorschau statt einer zweiten Einbettung. |
| P-10 | Sichtbarkeit im Widget | Mit `probe` zeigt das Widget im Kopf das Etikett „Probe · Trockenlauf“ (de/en). | Niemand soll eine Probe für echt halten. |

**Teilpakete:**
1. **AS-8a (Backend):** `ChatRequest.probe`, Zug-Merker, Erkennung (P-1/P-2), MCP-Trockenlauf
   (P-3), Ablage (P-4), Aufträge (P-5), `treiber.gilt` + Start in der Probe (P-6/P-7). Tests
   zuerst, Vertragsliste + OpenAPI.
2. **AS-8b (Widget + Studio):** Attribut `probe` + Etikett, Ablage-Satz `trockenlauf` (P-10);
   Abschnitt in der Vorschau + Knopf am Ablauf (P-9). Specs, i18n de/en.
3. **AS-8c (Doku):** Handbuch `docs/ablaeufe.md` mit den Beispielen „Sammlung aus Ordnern“ und
   „Sammlung prüfen“ (D7) sowie Kapiteln Testen und Ausprobieren.

Je ein Review mit Befundbehebung, danach ein Querschnitts-Review über AS-8.

**Stand (10.11.):**
- **AS-8a:** umgesetzt, zwei Reviews behoben (4 schwer, dann 2 schwer; Notiz `…-as-8a-…`).
- **AS-8b:** umgesetzt, Browser-Abnahme bestanden mit drei Befunden B-1…B-3, Review (0 schwer,
  6 mittel, 5 klein) behoben (Notiz `…-as-8b-…`).
- **AS-8c:** Handbuch und Seed `sammlung_pruefen` (Notiz `…-as-8c-…`).
- **Querschnitts-Review AS-8:** 2 schwer (beide im Beispiel-Seed und Handbuch), 4 mittel, 3 klein,
  alle behoben (Notiz `…-querschnitt-as-8.md`).

## 5o. Für den nächsten Plan (Nutzer 2026-11-10)

- **Formeln im Widget:** Formeln werden für die Person nicht korrekt angezeigt. Eigenes Paket im
  nächsten Plan: Befund mit echten Antworten nachstellen, Lösungswege abwägen (Formel-Renderer im
  Bündel gegen das Budget, Text-Fallback, Vorgabe an das Modell; keine Netzquellen), entscheiden,
  umsetzen. Eintrag in `offene-befunde-und-todo.md` §1.
- **Lokale Tests ohne b-api:** Chat-Smokes und Browser-Abnahmen laufen mit nativer
  OpenAI-Anbindung (`gpt-6-luna`), weil die b-api ausfallen kann.

## 6. Nicht im Umfang

- grafischer Editor per Ziehen;
- Umzug der bestehenden Webseitenführung (nur vorbereitet);
- Hintergrund-Wächter für Aufträge (Plan 11-08 „Später“);
- signierter Start über die B-API (E2 C);
- Abläufe, die andere Abläufe aufrufen.

## 7. Risiken

- **Startdaten sind Fremdeingaben.** Abhilfe: Prüfung gegen das Schema, Größengrenzen, Platzhalter ohne Markdown-Wirkung, keine Rechte aus Startdaten.
- **Direkter Start durch die KI** kann Personen überraschen. Abhilfe: `direkt` nur für lesende Abläufe, sonst Knopf.
- **Übertragung des Katalogs** (E1 B): Laufende Läufe hängen an der Fassung der Schritte. Abhilfe: Fassung und `id` bleiben gleich; ein Test sichert das ab.
- **Schnellantworten neben getipptem Text:** unklar, ob die Person dem Ablauf antwortet oder der KI. Abhilfe: Text geht an die KI, der Lauf wartet weiter, die Chips der Wahl bleiben (der Weg zurück zum Ablauf).
