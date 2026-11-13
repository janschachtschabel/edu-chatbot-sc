# Paket R3: UI-Module und Widget, Restpunkte (2026-11-13)

Plan [`2026-11-12-restpakete-ablaeufe-kestra-ui.md`](../plans/2026-11-12-restpakete-ablaeufe-kestra-ui.md),
Abschnitt R3, Entscheid R-E5.

## Was

- **R3-a „Inhalte anzeigen“ prüft das Angebot:** Die Direktaktion `browse_collection` ruft
  `get_collection_contents` nur, wenn ein Zug das Werkzeug angeboten bekäme. Es zählen der
  Studio-Schalter, die Sperren dieses Zugs und der Modus der Einbettung, wie beim Themenbaum.
  Sonst sagt sie „Die Inhalte von … kann ich hier gerade nicht anzeigen.“
- **R3-b Upload-Feld nennt die Anmeldung:** Ist Lesen im Studio nur für Angemeldete freigegeben,
  steht gleich unter dem Hinweis der KI: „Ein Dokument lesen lassen geht erst, wenn du bei WLO
  angemeldet bist.“ Dafür gibt es den neuen Schalter `lesen_nach_anmeldung` im Block. Er erscheint
  nur, wenn er zutrifft.
- **R3-c Lücken mit ihrem Punkt:** Im Strukturabgleich nennt eine Lücke der Ebene 2 ihren Punkt
  („Optik › Linsen“). Das gilt im Modul und in der Textfassung für die KI.
- **R3-d Themenbaum:**
  - Ein langer Titel bricht in seiner eigenen Spalte um, statt unter den Pfeil zu rutschen. Die
    Regel steht im gemeinsamen Baum-Stil, sie gilt also auch für den Entwurf.
  - Bei 404 (Sitzung weg) und 422 (keine gültige Kennung) erscheint kein „Erneut laden“ mehr.
- **R3-g Studio:**
  - Nach dem Speichern steht der Fokus auf der Statuszeile statt auf `body` (WCAG 2.4.3). Das gilt
    in „UI-Module“, „Materialformate“ und „Werkzeuge“, aber nur, wenn der Fokus verloren ging.
  - `npm run module:neu` trägt das neue Modul in die Vorschau-Spec des Studios ein (Import und
    `MANIFESTE`).
  - Der Vergleich der Evaluation nennt je Gruppe die wirksamen UI-Module.
- **R3-h Vorlagen des Master-Skills:** `vorgehen.md` und `vorgehen-kompakt.md` zeigen Unterthemen
  mit `ui_themenbaum`. `browse_collection_tree` gilt nur noch zum eigenen Auswerten (Prüfen,
  Lücken) oder ohne UI-Module, wie in der Kurzfassung.

## Querschnitts-Review R1–R4 und Behebung

Unabhängiges Review über R3, R4 und die Nachbesserungen aus R1/R2: 1 MAJOR, 6 MINOR, 5 NIT. Behoben:

- **MAJOR 1:** `ui_module_wirksam` ist im Backend ein Objekt (`{module, agent_aus}` oder `{fehler}`),
  keine Liste. Der Vergleich warf sonst bei jedem Lauf seit U1-g. Er zeigt jetzt die wirksamen
  Module, „(für den Agenten aus)“, „(Wirkung unbekannt)“ und abweichend Gemeldetes. Die Spec nutzt
  die echte Form.
- **MINOR 2 und 3 (Fokus):**
  - Der eigene Helfer ist weg; `injectFocus` hat jetzt die Option `nurWennVerloren`.
  - Dazu gehört die Wache gegen eine zerstörte Ansicht (NG0911).
  - Nach einem Fehler geht der Fokus auf die Fehlermeldung (alle drei Panels).
- **MINOR 4:** Der Verlaufs-Abruf schreibt nach der Übernahme nur den Verweis in frisch gelesene
  Entities. Ein zweiter Tab verliert so nichts.
- **MINOR 5:** Die Überschrift der Struktur-Hinweise zählt alle, auch die nicht gezeigten.
- **MINOR 6:** Jahreszahlen sind nur noch als Schuljahr („2024/25“, „Schuljahr“) oder allein ein
  Hinweis. „Revolution 1848“ ist ein Thema.
- **MINOR 7, NIT 12:** Befundliste nachgezogen. Die Muster-Prompts nennen `browse_collection_tree`
  bewusst weiter.
- **NIT 8:** Kein doppelter Fokus-Sprung beim Löschen in „Materialformate“.
- **NIT 9:** Ein fester Satz an einer festen Antwort bleibt ohne KI-Etikett.
- **NIT 10:** Die Richtwerte im Hinweistext kommen aus den Konstanten.
- **NIT 11:** `module:neu` weicht einem Namen aus, den die Spec schon trägt (`manifestText`).

## Durchtest im Browser (13.11.)

Lokal mit Wegwerf-DB und frisch gebautem Widget auf der Demo-Seite `/widget/inline` (gpt-6-luna):

- **„Themenbaum zu einem Thema“ → „Gleich entwerfen“ → Entwurf:** Der Entwurf folgt dem Leitfaden,
  also gibt es keine Hinweise.
  - Ein einzelner Unterpunkt löst sofort „Hinweise zur Struktur (1)“ aus, mit dem richtigen Satz.
  - Der Abschnitt ist zugeklappt, öffnet sich und ist gut lesbar.
- **Themenbaum Physik (WLO):**
  - Ein langer Titel bricht neben dem Pfeil um (gemessen: gleiche Zeile, zwei Zeilen hoch).
  - Nachgebessert: Ein kurzer Titel schob die Zahl der Inhalte ganz nach rechts. Jetzt gilt
    `max-width: max-content`, die Zahl steht direkt dahinter.
  - Kein waagerechter Überlauf.
- **Gefunden und behoben, älter als R1–R4:**
  - Kam Enter im selben Frame wie die letzte Eingabe, blieb der Text im Feld stehen. `[value]`
    hatte noch '' gerendert, das Signal änderte für Angular nichts.
  - Jetzt leert `clearInput` auch das Feld selbst (Test `chat-shell-turn.spec.ts`).
  - Im Browser nachgeprüft: Das Feld ist sofort leer.

## Geprüft, nicht geändert

- **R3-e `ui_upload` („Vorgang herunterladen“, doppelte Ablage nach abgelaufener Freigabe):**
  zurückgestellt.
  - Das Übertragen nach WLO wirkt erst mit `WLO_BATCH_UPLOAD_ENABLED` am MCP und nach der Messung
    MA-0. Beides sind externe Stellen.
  - Gegen doppelte Ablage zeigt das Modul seit M6 die letzten eigenen Ablagen.
- **R3-f `runCardAction` bei gewechselter Sitzung:** Kein Fehler. `restart()` und `wechseln()` setzen
  den Ladezustand selbst zurück (`shell/lifecycle.ts`). Ein `setLoading(false)` im veralteten Pfad
  beendete sogar das Laden der neuen Sitzung.
- **Studio-Probelauf meldet keine Module:** zurückgestellt. Die Evaluation meldet sie seit U1-g. Im
  Probelauf bräuchte es eine neue Backend-Ausgabe bei geringem Nutzen.

## Tests

- Backend:
  - `test_direct_actions.py` (R3-a);
  - `test_ui_upload.py` (R3-b);
  - `test_strukturabgleich_u4.py` (R3-c).
- UI-Module:
  - `ui-upload.element.spec.ts`;
  - `ui-strukturabgleich.element.spec.ts`;
  - `ui-themenbaum.component.spec.ts` (404/422).
- Studio:
  - `ui-module.component.spec.ts` (Fokus);
  - `core/inject-focus-verloren.spec.ts`;
  - `eval-compare.component.spec.ts`.
- Skripte: `module-register.test.mjs`.

## Deploy

- Keine Migration. Image neu bauen und den Browser hart neu laden.
- Das Modulregister ist neu erzeugt (Schalter `lesen_nach_anmeldung`).
