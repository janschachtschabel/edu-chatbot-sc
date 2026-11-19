# Paket N3: Zuordnung Datei → Punkt im Themenbaum-Entwurf (2026-11-19)

Plan: `docs/plans/2026-11-19-nachbesserungen-themenbaum-betrieb.md`, Abschnitt N3. Grundlage:
TG-3f (`inhalte` je Punkt beim Ordner-Weg), Paket U (lokaler Teil `metadaten`), Paket K
(`metadaten_lesen` mit `node_id`). Reviewt am 19.11. (3 MAJOR, 6 MINOR, 3 NIT), alle Befunde
behoben (Abschnitt „Review behoben“); zweites Review (3 MINOR, 4 NIT) ebenso.

## Warum

Ein Entwurf aus den Materialien der Person (`ui_strukturentwurf` mit `aus_inhalten`) sagte nicht,
welches Material zu welchem Punkt gehört. Das Modell nannte die Kennungen schon (`abschnitte`, `aN`),
sie wurden aber nur als Fundstelle genutzt. Fürs spätere Befüllen der Sammlungen braucht der Entwurf
die Verweise – mit `node_id`, damit die Inhalte in edu-sharing wiederzufinden sind.

## Was

### Zuordnung (`services/strukturentwurf_zuordnung.py`, `strukturentwurf_naehe.py`, neu)

- **Übernehmen, was das Modell liefert:** je oberem Punkt werden die bekannten `abschnitte` zu
  `inhalte: [{i, name, node_id?}]` – dasselbe Format wie beim Ordner-Weg (TG-3f). Die Kennung `aN`
  zählt wie `metadaten.als_dokument` (neu: `metadaten.materialien`, von beiden gelesen). `name` ist
  immer der Titel des Materials. Unbekannte Kennungen (`a99`, `x`) zählen nicht. Ein Material darf
  an zwei Punkten hängen (so erlaubt es der Prompt).
- **`node_id` geht vor:** aus dem Teil `metadaten` (nach `metadaten_lesen`), sonst aus der Ablage
  derselben Auswahl über `i` (`node_ids_der_auswahl`: `struktur`, `ablage` und `metadaten` mit
  derselben `block_id`, wie beim Ordner-Weg). Sonst trägt der Eintrag nur `i` (Chat-Weg, nur Namen).
- **Nachziehen über Einbettungen** (`strukturentwurf_naehe`): Materialien ohne Punkt gehen an den
  ähnlichsten oberen Punkt. Material = Titel, Beschreibung, Schlagworte; Punkt = Titel,
  Beschreibung, Titel der Unterpunkte. Nur ab der gemessenen Schwelle des Modells
  (`SCHWELLEN = {"text-embedding-3-small": 0.36}`), darunter in der Wurzel unter
  **`nicht_zugeordnet`** (dasselbe Format). Ein Aufruf für alle Texte, in der Frist des Dienstes.
  Rechnen mit numpy: einmal normieren, Matrix Materialien × Punkte, `argmax`. Bei Gleichstand gewinnt
  der zuerst stehende Punkt. Fällt die Einbettung aus (Frist, Last, Fehler, falsche Zahl von
  Vektoren): ohne Nachziehen, kein Fehler, nur die Art ins Log.
- Grenze `HOECHSTENS_INHALTE` (500) gilt für Punkte und `nicht_zugeordnet` zusammen; darüber
  `gekuerzt`.
- Der Entwurf trägt `quelle_block` = `block_id` des Teils `metadaten`. Beim Speichern verknüpft der
  Server darüber node_ids.

### Einbettung (`services/llm_einbettungen.py`, neu)

`einbettungen(texte, usage_acc, phase, platz_frist_s)`: eine Liste als `input`, dasselbe Modell,
dieselbe Route und Frist wie `llm.embedding`, derselbe Deckel (`platz`) mit eigener kurzer Geduld.
Die Reihenfolge gilt nach `index`. Der Verbrauch geht in den Zähler des Zugs (Phase
`strukturentwurf_zuordnung`, je Modell `text-embedding-3-small`), wie bei `chat_completion`. Immer
der Anbieter-Weg; `EMBED_BACKEND=local` gilt nur für die Wissensbasis.

### Dienst und Format

- `ui_module/dienst.py`: nach dem Entwurf `aus_inhalten` die Zuordnung (Naht `_einbetten`, Tests
  setzen eine Attrappe), danach bei jedem Entwurf der Abgleich von Fach und Stufe mit dem Vokabular.
  Die Quittung an die KI nennt nur Zahlen („n Materialien keinem Punkt zugeordnet“), nie Namen. Die
  Fehlertexte stehen seit dem Review in `ui_module/dienst_fehler.py`.
- Manifest `ui-strukturentwurf/manifest.json` (Eingabe und Antwort): `nicht_zugeordnet[]`
  (≤ 500, `$defs/inhalt`); `$defs/stufe` um vier Labels des Vokabulars erweitert (Review, MINOR 7).
  `manifeste.json` ist neu erzeugt.
- `ui_module/strukturentwurf.py`: `RESTE`, `hat_inhalte`. `mit_knoten_ids`, `knoten_ids_im_entwurf`,
  `ohne_inhalte`, `normalisiert` und `fehler` kennen `nicht_zugeordnet`.
- Merken (`strukturentwurf_merken._FELDER`) und Vertiefen einer Vorlage
  (`strukturentwurf_dienst._WURZEL_FELDER`) behalten `nicht_zugeordnet`. Ein zu großer gemerkter
  Entwurf verliert es wie die `inhalte`; beides steht im Teil `draft`.

### Fach und Stufe über das WLO-Vokabular (Anschluss N2, `services/strukturentwurf_vokabular.py`)

- Der Dienst gleicht jeden Entwurf an: Fach und Stufe an der Wurzel und an jedem Punkt über
  `vokabular_labels.fach_geprueft`/`stufe_geprueft` (nur genau oder Alias): „Erdkunde“ →
  „Geografie“. Je Wert ein Aufruf, gemerkt.
- Kein Treffer → leer, mit Hinweis an die KI („Hinweis für die Person: Fach „Wirtschaft“ ist nicht im
  WLO-Vokabular – deshalb leer.“). Das Schema hat kein Hinweisfeld, deshalb kein neues Feld.
- Ein Punkt mit demselben Wert wie die Wurzel verliert ihn, wie bei `knoten_aus`. Ohne Vokabular
  ändert sich nichts.

### Anzeige (`ui-strukturentwurf`)

- Der Baum zeigt je Punkt die Zahl („3 Materialien“, aus Ordnern „3 Dateien“; Beschreibung des
  Eintrags, TG-3f).
- `entwurf-inhalte.ts`: die Titel aufklappbar als natives `<details>`/`<summary>` (Disclosure), beim
  gewählten Punkt im Detailfeld bzw. in der Leseansicht („Inhalte dieses Punkts: n Materialien“) und
  unter dem Baum („Nicht zugeordnet: n Materialien“). Zugeklappt, „aufgeklappt“ bleibt über das
  Neuzeichnen. Titel als `textContent` mit `dir="auto"`, Liste in der Höhe begrenzt und rollbar.
  Texte de/en.
- Löschen eines Punkts schiebt seine Inhalte (samt Unterpunkten) nach „nicht zugeordnet“;
  „Rückgängig“ holt sie zurück (abgeleitet aus Ausgangs- und jetzigem Stand, `verwaisteInhalte`).
- Antwort und JSON-Export behalten `nicht_zugeordnet` und die `inhalte` mit `node_id`.

### Export und Übernahme

- `strukturentwurf_bestand.mit_kennungen` (nach `wlo_create_collection_tree`) kopiert tief: `inhalte`
  mit `node_id` und `nicht_zugeordnet` bleiben (Test). `baum_aus_entwurf` schickt nur Titel an den
  MCP. Der Strukturabgleich liest den Entwurf nur.
- Beim Speichern als `draft` setzt der Server node_ids nur selbst. Quellen: die gebundene Ablage über
  `i`, der Teil `metadaten` derselben Auswahl (Review, MINOR 6), sonst der zuletzt gespeicherte
  Entwurf derselben Auswahl. Das gilt auch für `nicht_zugeordnet`.

## Entscheide

1. **Kein Veto gegen Zuordnungen des Modells** (optionaler Teil des Auftrags). Fachfremde Materialien
   liegen bei bis zu 0,37 gegen jeden Punkt, richtige Paare ab 0,39. Ein Veto „deutlich unter der
   Schwelle“ fiele praktisch nie. Es kostete die Einbettung aller Materialien und könnte richtige
   Zuordnungen von Materialien mit knappen Angaben verwerfen. Das Modell sieht dieselben Texte und
   dazu alle anderen.
2. **Nur obere Punkte:** Das Modell ordnet oben zu, die Einbettung ebenso. Die Unterpunkte gehen in
   den Text des Punkts ein.
3. **Einträge ohne `i`** (Stapel vor TG-3b) fallen weg. Das Format verlangt `i`, und node_ids
   verknüpft der Server nur über `i`. Sie stehen auch nicht unter „nicht zugeordnet“.
4. **`upload_id` nicht im Entwurf** (Abweichung vom Wortlaut „sonst `upload_id` bzw. `i`“). Auf dem
   Chat-Weg trägt der Eintrag `i`. Eine `upload_id` verfällt mit Löschen und Aufbewahrung
   (`metadaten_lokal.ohne_uploads`) und müsste dann aus jedem Entwurf entfernt werden.
5. **Verbrauch der Einbettung im Zähler des Zugs** (Abweichung: „gebucht wie andere Einbettungen“
   gab es nicht; `llm.embedding` bucht nichts). So erscheint sie in der Kostenschau.
6. **Titel nicht im Baumeintrag:** Ein `treeitem` trägt keine eigenen Bedienelemente (APG); die Zahl
   bleibt am Eintrag, die Liste beim gewählten Punkt.
7. **Sicherheitslücke geschlossen:** `arbeitsstand._hat_inhalte` nimmt `se.hat_inhalte`. Ein
   Entwurf, der nur `nicht_zugeordnet` trug, hätte beim Speichern node_ids des Clients behalten.
8. **Schwelle je Modell, 0,36 für text-embedding-3-small:** gewählt NUR an der Kalibrierhälfte
   der echten Materialien (Mitte des besten Bereichs, zweites Review). Unabhängig geprüft an der
   Prüfhälfte (97 %) und am Beispielsatz (100 %). Die zuvor eingestellte 0,38 war die Mitte der
   Lücke über ALLE Daten, also nicht unabhängig geprüft. Ungemessene Modelle ziehen nicht nach
   (eine Log-Zeile).
9. **Fach und Stufe: kein Treffer → leer, mit Hinweis.** Wie die Vorbelegung (N2: nur ein Treffer
   belegt vor); ein unbekanntes Fach ginge auch beim Anlegen nicht an den MCP (SW-2). Ein Fach, das
   die Person im Auftrag nennt, steht dann nur noch in Thema und Hinweisen.
10. **Bildungsstufen des Entwurfs um die übrigen Vokabular-Labels erweitert** (Schule, Förderschule,
    Fernunterricht, Informelles Lernen). Der Schnappschuss vom Staging-MCP zeigte, dass das Schema
    sonst echte Treffer verwürfe. Der Prompt nennt sie jetzt mit.
11. **Löschen schiebt nach „nicht zugeordnet“** statt die Verweise zu verlieren (ändert TG-3f).
    Abgeleitet statt gespeichert, damit „Rückgängig“ ohne eigenen Stapel stimmt.
12. **Fristen der Einbettung:** höchstens `OBERGRENZE_S` (10 s) insgesamt, auch bei langer Frist
    des Dienstes; auf einen Platz höchstens `PLATZ_S` (2,5 s), höchstens die Hälfte von
    `LLM_SLOT_WAIT_S` und nie länger als die Restzeit. Nur so nimmt `llm_parallel._anstellen` den Weg
    der eigenen Frist und setzt den Zug bei Last nicht auf „ausgelastet“. Hängt der Anbieter, kommt
    der Entwurf ohne Nachziehen.

## Messergebnis (19.11., lokal, OpenAI nativ, text-embedding-3-small / gpt-6-luna)

### Beispielsatz (`scripts/zuordnung_messen.py --entwurf`, `tests/zuordnung_beispiel.py`)

16 Materialien, je 3–4 zu Vulkane, Plattentektonik, Erdbeben und Klima, dazu 2 fachfremde.

| Schwelle | 0,20 | 0,25 | 0,30 | 0,35 | **0,36** | 0,40 | 0,45 | 0,50 |
|---|---|---|---|---|---|---|---|---|
| richtig | 88 % | 88 % | 88 % | 100 % | **100 %** | 100 % | 94 % | 94 % |

Der Beispielsatz ging nicht in die Wahl der Schwelle ein — 100 % bei 0,36 ist unabhängig.

Ganzer Entwurf (zwei Läufe, gleiches Ergebnis): Modell 14, Einbettung 0, übrig 2 (die
fachfremden), Reinheit 100 %. Gegenprobe ohne die Kennungen des Modells: Die Einbettung allein
ordnet 14 von 14 wie das Modell zu. Verbrauch rund 8 000 Token, 6–7 Aufrufe.

### Echte WLO-Materialien (`scripts/zuordnung_messen_echt.py --entwurf`, Review MINOR 4)

`tests/zuordnung_wlo_echt.json`: 57 öffentliche Materialien aus der WLO-Suche (`search_wlo_content`,
Staging-MCP, lesend, anonym). Themen: Vulkane, Plattentektonik, Erdbeben, Klimawandel und Wetter,
dazu 7 fachfremde (Bruchrechnung, Satzglieder). Abgeleitet sind 6 Einträge nur mit Titel und 6 nur
mit einem Dateinamen (einer davon fachfremd, „Scan 2023-04-12 Seite 3“), zusammen 69. Gespeichert
sind nur Titel, gekürzte Beschreibungen ohne Links und höchstens 6 Schlagworte. Mehrdeutige Treffer
(„Erdbeben, Vulkanismus, Plattentektonik“) und Fremdthemen („Migrationspolitik“) habe ich
verworfen. Für Störer zwischen Wetter und Klima sind beide Punkte zulässig.

**Unabhängige Messung (zweites Review):** Kalibrierung und Prüfung sind nach Originalgruppen
getrennt; ein Eintrag „nur Titel“ liegt in derselben Hälfte wie sein Original. Die Schwelle ist nur
an der Kalibrierhälfte gewählt.

| | Ergebnis |
|---|---|
| Kalibrierung (35): beste Schwelle | **0,36** (Mitte des besten Bereichs) → 100 % |
| **Prüfung (34) bei 0,36 — unabhängig** | **97 %** (1 Fehler: „Satzglieder“, fachfremd, 0,367 → Wetter) |
| Fehlzuordnungen (alle 69, bei 0,36) | 1 (dieselbe) |
| nicht zugeordnet (alle 69, bei 0,36) | 7 von 69 (10 %), alle fachfremd; 1 fachfremdes zugeordnet |
| nur Titel / nur Dateiname | je 6, 100 % |
| Ähnlichkeit (alle) | richtige Paare 0,392–0,783, fachfremd höchstens 0,368 |

**Nicht unabhängig:** Die Zahl „100 % bei 0,38“ der ersten Fassung beruht auf einer Schwelle, die
aus ALLEN Daten gewählt war (Mitte der Lücke über alle 69). Sie ist darum keine Prüfung. Die erste
Teilung (jedes zweite Material) trennte zudem „nur Titel“ nicht von seinem Original.

Ganzer Entwurf „Erdkunde: Naturgefahren und Klimawandel“ über alle 69: Modell 55, Einbettung 6,
übrig 8. Das sind die 7 fachfremden und der Scan. Die Punkte: Vulkanismus 14 (alle Vulkane),
Plattentektonik 10, Erdbeben und Tsunamis 11, Klimawandel 13, Wetter und Klima 13 (11 Wetter, 2
Wetter/Klima-Störer). Verbrauch 16 713 Token, 7 Aufrufe.

**Hinweis:** Die Lücke zwischen fachfremd (0,368) und richtig (0,392) ist schmal; bei 0,36 kann ein
fachfremdes Material mit Allerweltstitel („Satzglieder“) einem Punkt zufallen. Ein anderes Modell
oder andere Fächer: mit beiden Skripten neu messen und `SCHWELLEN` ergänzen.

## Review behoben (19.11.)

| Nr. | Befund | Behebung | Test |
|---|---|---|---|
| 1 | MAJOR Frist der Einbettung | `zuordnen(frist_ende=…)`: `asyncio.timeout_at`, unter 1 s Rest kein Aufruf; `einbetten_mit(usage_acc, frist_ende)` setzt `platz(…, frist_s=…)` unter `LLM_SLOT_WAIT_S` | `test_n3_review`: hängende Einbettung, ohne Restzeit, alle Plätze belegt (Zug bleibt frei), Platzfrist < Betrieb |
| 2 | MAJOR Kosinus blockiert | numpy (`strukturentwurf_naehe.beste_punkte`) | 500 × 30 × 1536 unter 1 s |
| 3 | MAJOR Schwelle je Modell | `SCHWELLEN`, `schwelle(modell)`; ungemessen → kein Nachziehen, Log-Zeile; Messen steht im Modulkopf | gemessen/ungemessen, mit Präfix |
| 4 | MINOR echte Daten | Fixture + `scripts/zuordnung_messen_echt.py`, Ergebnis oben (Schwelle später 0,36, zweites Review) | Messlauf |
| 5 | MINOR Grenzfälle | Toleranz 1e-9; Gleichstand: der erste Punkt | an der echten Schwelle (jetzt 0,360 / 0,359), Gleichstand |
| 6 | MINOR node_id beim Speichern | `_entwurf_mit_knoten` nimmt `metadaten_ids` derselben Auswahl dazu | gleiche / fremde Auswahl |
| 7 | MINOR Stufen still weg | Log-Zeile und Hinweis; `BILDUNGSSTUFEN` + Manifest um 4 Labels erweitert | Schnappschuss `tests/schnappschuss_bildungsstufen.json` ⊆ `BILDUNGSSTUFEN`, Enum = Liste |
| 8 | MINOR Dateigröße | Fehlertexte in `ui_module/dienst_fehler.py`, die alten Namen bleiben; `dienst.py` 355 → 291 Zeilen | bestehende Tests (`dienst._FEHLER`) |
| 9 | MINOR Löschen verliert Verweise | `verwaisteInhalte` (abgeleitet), Antwort, Export und Anzeige | Spec: Löschen samt Unterpunkten, Rückgängig, Material an zwei Punkten; TG-3f-Fall angepasst |
| 10 | NIT Satz bei Kürzung | `gekuerztInhalte` für `quelle: ki` | Spec |
| 11 | NIT Notiz | durchnummeriert, alle Entscheide samt Sicherheitslücke | – |
| 12 | NIT Texte, Höhe | „Materialien“ (Ordner: „Dateien“); Liste `max-block-size` über `--mat-sys-body-small-line-height`, rollbar | Spec (Stil und Texte) |
| N1/N2-Review, Befund 3 | verworfenes Fach unsichtbar | `fach_geprueft`/`stufe_geprueft` (nur genau oder Alias), Hinweis an die KI | „Wirtschaft“ → leer + Hinweis, unscharf zählt nicht, ohne Vokabular kein Hinweis |

Der Mess-Wächter auf `llm._aembedding` war nur ein pytest-Plugin im Scratchpad einer Sitzung. Er
steht nicht im Repository. `tests/test_llm_wiederholungen.py`: 6 passed.

## Tests

- Backend: `test_n3_zuordnung.py` (15), `test_n3_zuordnung_dienst.py` (10), `test_n3_einbettungen.py`
  (3), `test_n3_review.py` (14), `test_n3_vokabular_entwurf.py` (10). Fixtures:
  `zuordnung_beispiel.py`, `zuordnung_wlo_echt.json`, `schnappschuss_bildungsstufen.json`. In
  `test_paket_k_durchtest.py` und `test_tg7_durchtest.py` ist die Einbettung abgeschaltet
  (`_einbetten` → `None`).
- Frontend: `ui-strukturentwurf.inhalte.spec.ts` (15), `entwurf-regeln.spec.ts` (+1). TG-3f-Fälle angepasst: Namen nicht im Baum,
  Löschen nach „nicht zugeordnet“.

## Offen

- Durchtest gegen eine Wegwerf-DB und eine Browser-Abnahme der Anzeige stehen aus.

## Zweites Review behoben (19.11.)

| Nr. | Befund | Behebung | Test |
|---|---|---|---|
| 1 | MINOR eigene Obergrenze | `naechste`: Ende = `min(frist_ende, jetzt + OBERGRENZE_S)` (10 s), auch ohne Frist; Platzfrist `PLATZ_S` 2,5 s | hängender Anbieter bei 300 s Frist und ohne Frist endet an der Obergrenze; Platzfrist 2–3 s |
| 2 | MINOR Messung ehrlich trennen | `_haelften` nach Originalgruppen, Schwelle nur aus der Kalibrierhälfte; neu gemessen (ein Einbettungsaufruf, 5 584 Token); `SCHWELLEN` 0,38 → 0,36 (Entscheid 8), „100 % bei 0,38“ als nicht unabhängig gekennzeichnet | Messlauf, Grenzfall-Test auf 0,36 |
| 3 | MINOR doppelt nach „Rückgängig“ | `verwaisteInhalte` filtert `rest` gegen den jetzigen Baum | `entwurf-regeln.spec.ts` |
| 4 | NIT Link in der Fixture | Linkreste (`www.…`, „Sprechertext-Download unter:“) aus den Beschreibungen entfernt | – |
| 5 | NIT veraltete Doku | Skriptkopf „69 Materialien (57 echte, 12 abgeleitet)“; Modulkopf `strukturentwurf_naehe` nennt beide Skripte | – |
| 6 | NIT „Dateien“ beim Ordner | `inhalteTitel`/`nichtZugeordnet(n, dateien)`; aus Ordnern „Dateien“ | Spec |
| 7 | NIT rollbare Liste per Tastatur | `ul` mit `tabindex="0"` und `aria-label` (= Zusammenfassung), sichtbarer Fokus (`:focus-visible`) | Spec |
