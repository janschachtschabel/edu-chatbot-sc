# Plan: Kestra-Abläufe bequem — Studio, Ergebnisse, Fortsetzen (2026-11-08)

Auftrag des Nutzers (2026-11-08):
- Abläufe, die in Kestra abspringen, im Studio bequem editieren;
- Ergebnisse zurücknehmen;
- Job-IDs merken und mit Gesprächen verknüpfen, damit Gespräch und Ablauf später weitergehen;
- im Widget zeigen, dass ein Flow läuft, ggf. das Gespräch sperren oder einen Abbruch anbieten;
- Gespräche fortsetzen. Von außen geht das über die `bsid`; die Gesprächs-ID zum Eintippen ist eine
  mögliche, nicht die beste Lösung und kann später entschieden werden.

Der Chatbot steuert die Flows (Entscheid 2026-11-07). Grundlage ist der Plan
[`2026-11-05-vorgang-und-ablaeufe.md`](2026-11-05-vorgang-und-ablaeufe.md) §5 und die Bestandsaufnahme unten.

## 1 Bestand (geprüft 2026-11-08)

| Bereich | Stand | Lücke |
|---|---|---|
| **Studio-Editor** | Abläufe sind ein Abschnitt auf der Seite „UI-Module“ (Bereich `06-ablaeufe/katalog`, generisches Schema-Formular). `typ` ist eine Auswahl, `auftrag` gehört dazu. Geprüft wird erst beim Speichern (400 mit Befunden). | `flow` ist freier Text, keine Flow-Liste. `argumente` ist rohes JSON. Das Formular zeigt jedem Schritttyp alle Felder. Keine Vorschau des Ablaufs, kein „Prüfen“ vor dem Speichern. |
| **Ergebnis zurück** | `treiber.weiter_auftrag` legt `{outputs, dateien, warnungen}` als Teil `schreibt` ab; der Ablauf geht weiter. | `$teil` nimmt nur den ganzen Teil, ohne Pfad wie `outputs.markdown`. Dateien werden nicht geholt, nur Name, Größe und Verfügbarkeit gemerkt. Kein Zurückschreiben nach edu-sharing: das läuft über den MCP (Auftrag W1–W4) und Paket S (Freigabe). |
| **Job-ID ↔ Gespräch** | `vorgang_auftraege` (Job-ID) → `vorgaenge` (Besitzerin `aufrufer`, `session_id`) → Sitzung. Eine angemeldete Person bekommt in einer neuen Sitzung ihren jüngsten offenen Vorgang zurück (`vorgaenge.juengster`). | Nur der Vorgang kommt zurück, der Gesprächsverlauf nicht. Ein wartender Auftrag verlängert die Frist nicht (V-4, Vorgabe 3 Tage, die B-API hält 30). Verdrängen ab 3 Vorgängen nimmt einen wartenden Lauf mit. |
| **Widget** | `ui_fortschritt`: Balken, Status, „Jetzt prüfen“ und „Ergebnis abholen“. Es fragt nach 5/10/20/30/60 s nach, pausiert im versteckten Tab und wechselt nach 30 min auf Handbetrieb. Unter jeder Antwort steht „Stand prüfen“. | Kein Abbruch-Knopf. Das Gespräch geht normal weiter (keine Sperre). Nicht gemeldet wird: „Dein Auftrag ist fertig“, wenn die Person später wiederkommt. |
| **Fortsetzen** | `bsid` (Boerdi-Sitzungs-ID) per URL, Cookie oder localStorage; der Verlauf kommt über `GET /api/sessions/{id}/messages`. | Keine Liste „meine Gespräche“. Kein Wechsel auf das Gespräch, zu dem ein Auftrag gehört. Keine anzeigbare Gesprächs-ID. |

Wichtig für das Fortsetzen: **Aufträge starten nur angemeldete Personen** (Prüfung und `auftrag_zug.starter`). Wer
später wiederkommt und sich anmeldet, ist also über seine Kennung (`aufrufer`) eindeutig. Eine Gesprächs-ID zum
Eintippen braucht der Auftragsfall nicht. Sie wäre nur für anonyme Gespräche nötig, und die können keine Aufträge
starten.

## 2 Pakete

Jedes Paket ist klein, wird reviewt und bekommt eine Änderungsnotiz. Die Reihenfolge ist ein Vorschlag.

### K2a — Fortsetzen über die Person (Backend + Widget)

**Stand 2026-11-08: umgesetzt und reviewt (2 hoch, 4 mittel behoben)** — Notiz [`aenderungen/2026-11-08-paket-k2a-fortsetzen.md`](../aenderungen/2026-11-08-paket-k2a-fortsetzen.md). Abweichungen: `POST /api/ui/vorgaenge/offen` statt `GET /api/vorgaenge/offen` (wie die übrigen Widget-Abrufe); „Ergebnis liegt bereit“ ist der automatische „Stand prüfen“ nach dem Wechsel; die Frist ist ein fester Wert (8 Tage) statt `deadlineAt` je Job.

- **Backend:** Neu ist `GET /api/vorgaenge/offen`. Nur mit bestätigter Anmeldung; geprüft wird die Kennung,
  nicht eine mitgeschickte ID. Er liefert die offenen Vorgänge der Person: Titel, Ablauf, Status
  (`wartet_auftrag`, fertig noch nicht abgeholt), `session_id` und Zeitpunkt.
- **Widget:** Nach der Anmeldung oder beim Öffnen fragt das Widget, ob ein Vorgang in einem **anderen** Gespräch
  wartet. Dann erscheint ein Hinweis mit dem Knopf „Gespräch vom … fortsetzen“. Er wechselt die `session_id` auf
  das Gespräch des Vorgangs und lädt dessen Verlauf.
  - Der Wechsel geschieht nur, wenn der Vorgang der Person gehört.
  - Die alte `bsid` bleibt das Geheimnis des Verlaufs: Wer sie hat, liest mit. Deshalb kommt sie nur aus der
    geprüften Antwort für die angemeldete Person.
- **Meldung:** Ist ein Auftrag fertig, aber nicht abgeholt, sagt der erste Zug im wiederaufgenommenen Gespräch
  „Ergebnis liegt bereit“ und zeigt „Ergebnis abholen“.
- **Frist (V-4):** Solange ein Lauf wartet, gilt die Frist bis zum `deadlineAt` des Jobs plus 7 Tage, höchstens
  30 Tage. Verdrängen lässt wartende Vorgänge aus.

### K2b — Abbrechen und Sperre im Widget

**Stand 2026-11-08: umgesetzt und zweimal reviewt (erst 1 hoch, 4 mittel; dann 2 hoch, 6 mittel — alles behoben)** — Notiz [`aenderungen/2026-11-08-paket-k2b-abbruch-und-sperre.md`](../aenderungen/2026-11-08-paket-k2b-abbruch-und-sperre.md). Abweichungen vom Plan: Ein Abbruch folgt nicht `bei_fehler`, der Lauf endet als `abgebrochen`. Die Sperre ist **weich** — das Eingabefeld bleibt bedienbar und zeigt nur den Hinweis, damit eine Krisennachricht immer getippt werden kann; das Backend weist anderes Getippte ab. Nach einer Krise ruht die Sperre für dieses Warten.

- Neue Direktaktion `ablauf_auftrag_abbrechen` mit Rückfrage. Sie setzt den Lauf auf `abgebrochen`, beendet den
  Auftrag bei der B-API (schon gebaut, `zug_basis.abbrechen`) und folgt danach `bei_fehler` oder endet.
- `ui_fortschritt` bekommt einen Knopf „Abbrechen“. Unter einer Antwort steht neben „Stand prüfen“ auch
  „Abbrechen“.
- **Sperre je Schritt** (Studio-Feld `warten`):
  - `frei`: wie heute, das Gespräch geht weiter;
  - `gesperrt`: Eingabe aus, nur Prüfen, Abholen und Abbrechen; das Backend weist Texte in diesem Gespräch höflich
    ab, solange der Lauf wartet.
  - Entscheid F1.

### K2c — Studio-Editor für Auftragsschritte

- **Flow-Auswahl:** Neu ist `GET /api/config/ablauf-flows`. Er liefert die Schnittmenge aus `B_API_JOBS_FLOWS` und
  `GET /api/v1/jobs/flows` der B-API, dort mit `B_API_KEY`. Wo die B-API die Eingaben eines Flows nennt, kommen
  sie mit. Ohne B-API-Antwort gilt nur die Freischaltliste.
- **Formular je Schritttyp:** Ein Schritt zeigt nur die Felder seines Typs.
- **`argumente`:** Statt rohem JSON eine Tabelle Name → Wert, wobei der Wert ein fester Text oder ein Teil ist.
  Die Teile kommen aus `schreibt` der vorigen Schritte und den Teilen der Module, als Auswahl. Rohes JSON bleibt
  als „Experte“.
- **„Prüfen“-Knopf:** Er führt `pruefung.pruefe` ohne Speichern aus und zeigt die Befunde am Schritt.
- **Schrittfolge als kleine Liste mit Pfeilen:** Schritt → nächster, bei Fehler → … Nur lesend, kein
  Grafik-Editor.

**Stand 2026-11-08:** K2c-1 und K2c-2 umgesetzt und reviewt (Notizen [`aenderungen/2026-11-08-paket-k2c1-ablauf-editor-backend.md`](../aenderungen/2026-11-08-paket-k2c1-ablauf-editor-backend.md), [`aenderungen/2026-11-08-paket-k2c2-felder-je-schritttyp.md`](../aenderungen/2026-11-08-paket-k2c2-felder-je-schritttyp.md)); K2c-3 umgesetzt und zweimal reviewt (Notiz [`aenderungen/2026-11-08-paket-k2c3-argumente-als-tabelle.md`](../aenderungen/2026-11-08-paket-k2c3-argumente-als-tabelle.md)); K2c-4 umgesetzt und reviewt (Notiz [`aenderungen/2026-11-08-paket-k2c4-pruefen-und-schrittfolge.md`](../aenderungen/2026-11-08-paket-k2c4-pruefen-und-schrittfolge.md)). Abweichung: die Schrittfolge rechnet das Studio live aus dem Entwurf (dieselben Regeln wie `pruefung.nachfolger`), der Endpunkt bleibt unverändert.

**Zuschnitt (2026-11-08, nach der Bestandsaufnahme).** Das Studio baut das Formular aus dem pydantic-Schema
(`schema-form`); Auswahllisten kommen über Kataloge (`Catalog(name)` → `api/config_choices`), feste Werte über
`Choices`. Felder, die nur bei einem Wert eines Nachbarfelds gelten, kennt es noch nicht. Daraus vier Teilpakete,
jedes mit Review:

| Teil | Inhalt | Wo |
|---|---|---|
| **K2c-1** | Katalog `ablauf_flows` (die Freischaltliste `B_API_JOBS_FLOWS`) an `Schritt.flow`; neuer Endpunkt `POST /api/config/ablauf-pruefen` (Studio, mit Schlüssel): ein Ablauf → Befunde von `pruefung.pruefe` je Schritt, ohne zu speichern; Auszeichnung `NurBei("typ", …)` (`x-nur-bei`) an den Schritt-Feldern | Backend |
| **K2c-2** | `schema-form` blendet Felder mit `x-nur-bei` aus, wenn das Nachbarfeld einen anderen Wert hat (gesetzte Werte bleiben erhalten und sichtbar markiert, damit nichts still verschwindet) | Studio |
| **K2c-3** | `argumente` (und `daten`) als Tabelle Name → fester Text oder Teil; die Teile aus `schreibt` der vorigen Schritte, `agent.ausgabe` und den Modul-Teilen; rohes JSON bleibt als „Experte“ | Studio |
| **K2c-4** | Knopf „Prüfen“ an einem Ablauf (Befunde am Schritt) und die Schrittfolge als Liste (Schritt → weiter, bei Fehler → …) | Studio |

Abweichung vom Plan oben: Die Flow-Liste ist zunächst nur die Freischaltliste, ohne Abruf von
`GET /api/v1/jobs/flows`. Der Katalog-Endpunkt lädt alle Kataloge eines Formulars in einem Zug und ruft keinen
Fremddienst; die Eingaben eines Flows kommen erst, wenn die B-API sie nennt (dann eigener Abruf).

Felder je Schritttyp (aus `treiber`/`pruefung`): `nachricht` text, weiter · `modul` text, modul, daten, weiter,
bei_fehler · `werkzeug` werkzeug, argumente, schreibt, weiter, bei_fehler · `verzweigung` weiter · `agent` text,
agent, weiter, bei_fehler · `auftrag` text, flow, argumente, schreibt, warten, weiter, bei_fehler · `ende` text;
`id` und `typ` immer.

### K2d — Ergebnisse weiterverwenden

- **Pfad in `$teil`:** `{"$teil": "volltext", "pfad": "outputs.markdown"}`. Geprüft wird beim Speichern, soweit
  das Schema der Ausgabe bekannt ist.
- **Dateien holen:** Beim Abholen lädt das Backend die Dateien, die ein Schritt nennt (Feld `dateien_holen:
  [outputId]`). Dafür nutzt es den Schlüssel der Person und die Adresse `/api/v1/jobs/{jobId}/files/{outputId}`,
  die es aus der ID selbst bildet. Entscheid F3. Umgesetzt (K2d-2): gedeckelt wie ein Upload und durch dessen
  Aufbereitung; der Text steht im Ergebnis-Teil unter `texte.<outputId>` — nicht in der Ablage `dokumente`
  (die hält ein Dokument je Sitzung).
- **Zurückschreiben nach edu-sharing:** kein eigener Weg. Es ist ein `werkzeug`-Schritt mit MCP-Werkzeug und
  Freigabe. Der MCP liefert seit 2026-11-08 W1–W3 (`wlo_attach_fulltext(s)`, `wlo_update_contents`); sie werden mit
  diesem Paket angebunden (Nutzer-Entscheid 2026-11-08), W4 ist schon angebunden. Datensätze mit Datei lehnt W1/W2
  bis zur Messung des MCP-Teams ab (`would_replace_file` → „vorgemerkt“).

**Zuschnitt (2026-11-08).** Drei Teilpakete, jedes mit Review:

| Teil | Inhalt | Wo |
|---|---|---|
| **K2d-1** | `$teil` mit `pfad` (Treiber, Werkzeuge der KI, Prüfung der Form, Studio-Tabelle `name.pfad`) | Backend + Studio |
| **K2d-2** | `dateien_holen: [outputId]` am Auftragsschritt: beim Abholen die genannten Dateien holen (Schlüssel der Person, Adresse aus der Job-ID gebildet), gedeckelt und aufbereitet wie ein Upload; Text im Ergebnis unter `texte.<outputId>` | Backend |
| **K2d-3** | W1–W3 anbinden (`wlo_attach_fulltext(s)`, `wlo_update_contents`) als schreibende Werkzeuge mit Vorschau und Abnahme; `would_replace_file` → „vorgemerkt“ | Backend |

**Stand 2026-11-08:** K2d-1 und K2d-2 umgesetzt und reviewt (Notizen [`aenderungen/2026-11-08-paket-k2d1-teil-mit-pfad.md`](../aenderungen/2026-11-08-paket-k2d1-teil-mit-pfad.md), [`aenderungen/2026-11-08-paket-k2d2-dateien-holen.md`](../aenderungen/2026-11-08-paket-k2d2-dateien-holen.md)); K2d-3 umgesetzt (Notiz [`aenderungen/2026-11-08-paket-k2d3-volltexte-und-metadaten.md`](../aenderungen/2026-11-08-paket-k2d3-volltexte-und-metadaten.md)). Abweichungen: Dateien landen als Text im Ergebnis-Teil (`texte.<outputId>`), nicht in `dokument_uploads`; W1–W3 sind Werkzeuge des Agent-Modus und von M18, keine Ablaufschritte (schreibende Schritte = Paket S).

### Später

- Benachrichtigung über edu-sharing, wenn ein Flow fertig ist (Nutzer: später klären).
- Anzeigbare Gesprächs-ID zum Eintippen, nur falls anonyme Abläufe einmal Aufträge dürfen.
- Ein Wächter im Backend, der Aufträge ohne offenes Widget abfragt. Er bräuchte den Schlüssel der Person; der wird
  nicht gespeichert (K22), deshalb nicht vorgesehen.

## 3 Entscheide (Nutzer 2026-11-08: alle vier wie empfohlen)

| # | Frage | Empfehlung |
|---|---|---|
| F1 | Gespräch sperren, während ein Flow läuft? | Je Schritt im Studio wählbar, Vorgabe `frei` mit Abbruch-Knopf. |
| F2 | Fortsetzen von außen | Über die Anmeldung (K2a), keine Gesprächs-ID zum Eintippen. |
| F3 | Dateien eines Flows holen? | Ja, gedeckelt und nur die im Schritt genannten (K2d). |
| F4 | Reihenfolge | K2b → K2a → K2c → K2d (zuerst, was ein laufender Flow im Widget braucht). |

## 4 Prüfung

- Je Paket Tests für Backend und Widget bzw. Studio, Review mit Befundbehebung, Änderungsnotiz und volle Suite.
- Browser-Abnahme nur gegen eine Wegwerf-DB, mit dem Demo-Flow `edusharing.support/test-mit-jan` am Staging
  (Testuser, nicht destruktiv).
