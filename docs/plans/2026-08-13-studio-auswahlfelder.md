# Studio: Auswahlfelder statt Freitext (S1–S4)

**Anlass (Nutzer, 2026-08-13):** „TEils sind die interfaceoberflächen im studio sehr clean —
das ist gut aber unübersichtlich zu bedienen. sehr lange formulare. es fehlen teils vorgegebene
auswahlmöglichkeiten — alles nur freitext z.B. für wissensbereiche im rag — könnte doch die
bestehenden anbieten zur auswahl usw. auch bei anderen elementen die man angelegt hat wäre
eine direkte verlinkung denkbar."

Drei Beschwerden. Dieser Plan behandelt **zwei**: fehlende Auswahl und fehlende Verlinkung.
Die dritte (lange Formulare) steht in §6 als Folge-Vorschlag, weil sie einen anderen Schnitt
braucht und ohne Entscheid des Nutzers nicht sinnvoll zu bauen ist.

---

## 1 Befund (gemessen, nicht geraten)

Der Seed-Baum wurde am 2026-08-13 vollständig durchsucht
(`scan_choices.py`, 31 YAML + Pattern-Frontmatter). Ergebnis:

### 1a Geschlossene Wertevorräte — heute Freitext

Ein Vorrat gilt nur dann als geschlossen, wenn der **Code genau diese Werte
auswertet**. Der Seed allein reicht nicht: er zeigt, was jemand gepflegt hat,
nicht, was erlaubt ist.

| Feld | Vorrat | belegt durch |
|---|---|---|
| `sources` | `llm`, `mcp`, `rag` | Zugehörigkeitsprüfungen in `response_tool_selection`, `respond`, `route_head` |
| `quick_replies_mode` | `exact`, `speculative`, `none` | `quick_reply_policy.py:67` fällt sonst auf `exact` zurück; `PUT /config/patterns` weist mit 400 ab |
| `moderation` / `legal_classifier` | `never`, `smart`, `always` | `safety/service.py:85-87` verzweigt auf genau diese |
| `escalation.mode` / `.provider` | `off`/`smart`/`always` bzw. `openai`/`none` | `safety/service.py:75` + Seed-Kommentar |

**Nach Prüfung NICHT geschlossen** — hier wäre eine Auswahl eine Behauptung:

| Feld | warum nicht |
|---|---|
| `formality` | `completion_messages.py:126` akzeptiert `("sie","siezen","formal","foermlich")` — mehr, als jeder Kommentar nennt |
| `card_text_mode` | zwei WIDERSPRÜCHLICHE Dokumentationen: `config_areas.py:54` sagt `minimal\|kurz\|explanation\|ausfuehrlich`, `pattern_engine.py:55` sagt `minimal\|reference\|highlight` |
| `security_level` | zeigt auf einen Schlüssel in `presets`, und `presets` ist eine offene Zuordnung — eine eigene Stufe muss setzbar bleiben |
| `default_tone`, `default_length`, `response_type`, `output_mode` | redaktionelle Vokabulare; der Seed zeigt 3–8 Werte, aber nichts erzwingt sie |

### 1b Verweise auf anderswo Angelegtes — heute Freitext

| Feld | zeigt auf | Katalog-Quelle |
|---|---|---|
| `rag_areas` (Pattern) | 8 Wissensbereiche | Schlüssel von `05-knowledge/rag-config` |
| `tools` (Pattern) | 42 Werkzeugnamen | `TOOL_DEFINITIONS` + `05-knowledge/mcp-servers` |
| `crisis_pattern`, `threat_pattern` | Muster-IDs (`M01`/`M02`) | `03-patterns/*` |
| `persona_overrides[].persona` | Persona-IDs (`P-LEH` …, plus `*`) | `04-personas/*` |
| `intent_overrides[].intent`, `few_shot_examples[].intent` | Intent-IDs (`I01` …) | `04-intents/intents` |
| `few_shot_examples[].pattern` | Muster-IDs | `03-patterns/*` |
| `gold-flows[].persona` / `.intents` | Persona-/Intent-IDs | s.o. |

**`rag_areas` deckt sich exakt mit den 8 Schlüsseln der `rag-config`** — die Beschwerde des
Nutzers ist also 1:1 belegt: die Liste existiert, sie wird nur nicht angeboten.

### 1c Der Befund, der den Entwurf entscheidet

`pattern` heißt an zwei Stellen etwas anderes:

* `01-base/classify-overrides` → `few_shot_examples[].pattern` = eine **Muster-ID** (`M06`)
* `02-domain/guide-rules` → `message_rules[].pattern` = ein **Regex** auf die Nutzer-Nachricht

Eine Tabelle „Schlüsselname → Katalog" im Studio würde dem Regex-Feld Muster-IDs vorschlagen.
**Die Angabe muss deshalb am Modellfeld hängen, nicht am Namen** — also im Backend, dort wo
das Feld definiert ist, und über das ohnehin ausgelieferte JSON-Schema zum Studio reisen.

### 1d Nebenbefund: die Schema-Fixture des Studios war veraltet

Beim Neuerzeugen von `area-schemas.fixture.ts` (S3) fiel auf, dass sie
`01-base/engine` gar nicht enthielt — den Umschalter **Muster/Agent** von A0–A6
(2026-08-12). Zwei Folgen, beide still:

* Der Kommentar in `json-schema.ts` führte „kein `enum`" als Messung. Seit `engine`
  stimmte das nicht mehr: `mode` und `agent.write_mode` sind `Literal`.
* Weil der Mapper `enum` nicht las, stand der Umschalter Muster/Agent im Studio als
  **Freitextfeld** — obwohl der Server jeden anderen Wert mit 422 abweist.

Behoben in S3: `enum` rendert als Auswahlfeld, die Abdeckungszusage steht auf 34 statt 33
und begründet die Zahl.

---

## 2 Entwurf

### 2a Drei Arten, bewusst getrennt

* **`enum`** — Standard-JSON-Schema, entsteht aus einem `Literal` im Modell. Geschlossen
  **und** vom Server erzwungen. Studio rendert ein Auswahlfeld. Nutzt `01-base/engine`.
* **`x-choices: [...]`** — geschlossener Vorrat. Studio rendert ein **Auswahlfeld**.
  Steht im Dokument ein Wert, der nicht in der Liste ist, wird er als zusätzliche Option
  mitgeführt und ausgewiesen — ein Auswahlfeld darf einen Bestandswert nie stillschweigend
  wegwerfen.
* **`x-catalog: "<name>"`** — offener Vorrat aus dem laufenden Betrieb. Studio rendert ein
  **Textfeld mit Vorschlagsliste** (`<datalist>`). Man kann weiterhin etwas Neues tippen,
  denn ein RAG-Bereich entsteht durch Einlesen und ein Muster durch Anlegen.

### 2b Keine neue Speicher-Sperre

Die Annotation ändert **nicht** den Typ (kein `Literal`). `PUT /api/config/data/{area}`
validiert gegen das Modell; ein `Literal` würde jeden Bestandswert außerhalb der Liste ab
sofort mit 422 abweisen und könnte einen Bereich unspeicherbar machen. Die Annotation ist
eine Bedienhilfe, keine Verschärfung. Ein Wächter hält dafür fest, dass keine `x-choices`-Liste
lügt: jeder im Seed vorkommende Wert eines annotierten Feldes muss in seiner Liste stehen.

### 2c Katalog-Endpunkt

`GET /api/config/choices` liefert alle Kataloge in einem Zug:

```json
{"patterns":  [{"value": "M06", "label": "Material-Suche",
                "area": "03-patterns/m06-material-suche"}],
 "rag_areas": [{"value": "FAQ", "label": "FAQ", "area": "05-knowledge/rag-config"}],
 "tools":     [{"value": "search_wlo_all", "label": "search_wlo_all", "area": ""}]}
```

`area` ist der Bereichsschlüssel für die **direkte Verlinkung**: das Studio hat schon die Route
`/bereich/**`, also wird aus dem Verweis ein Sprung. Leer heißt „dafür gibt es keine eigene
Seite" — dann entfällt der Link, statt einen toten anzubieten.

Ein eigener Endpunkt statt einer Erweiterung von `/config/elements`: der Element-Browser liefert
ganze Persona- und Muster-Dokumente, ein Formular braucht davon nur `id` und `label`.

---

## 3 Pakete

| Paket | Inhalt | Dateien |
|---|---|---|
| **S1** | Katalog-Endpunkt `GET /api/config/choices` | `api/config_choices.py` (neu), `main.py`, `tests/test_config_choices.py` (neu) |
| **S2** | Feld-Annotationen im Bereichsmodell + Wächter | `config_models/_shared.py`, `base_governance.py`, `base_widget.py`, `patterns.py`, `knowledge.py`, `tests/test_config_choices_annotations.py` (neu) |
| **S3** | `schema-form` lernt Auswahl + Vorschlag | `json-schema.ts`, `schema-to-fields.ts`, `schema-field.component.{ts,html}`, `schema-form.scss` |
| **S4** | Katalog-Dienst, Verdrahtung, „öffnen"-Link, i18n | `core/choices-api.service.ts` (neu), `schema-form.component.ts`, i18n-Katalog |
| **S5** | Aufklappbare Abschnitte (§6) | `schema-form/form-sections.ts` (neu), `schema-form.component.ts`, `schema-form.scss`, i18n-Katalog |

Jedes Paket: Schritt 0 = `/better-coding-workflow` laden. Test zuerst, dann Umsetzung.

---

## 3a Was der Vertrag dazu verlangte

`GET /api/config/choices` ist eine neue Route, und der Vertrag ist eingefroren.
Zwei Wächter schlugen an — beide zu Recht:

* `test_route_inventory_matches_spec_5_1` (Inventar der laufenden App)
* `test_openapi_additions.py` (Zahl der Operationen im **abgelegten** Vertrag)

Der zweite verlangt mehr als ein Neu-Erzeugen: eine Zeile mit Begründung in
`docs/api/bewusste-vertragszusaetze.md`, mindestens 40 Zeichen lang. Dort steht
sie jetzt. Erst danach wurde `openapi-v1.json` einmal neu erzeugt.

## 4 Abnahme

* Backend-Suite grün (Stand vor Beginn: **3213 passed, 4 skipped**), ruff sauber.
* Studio-Suite grün + `tsc` sauber.
* Am Bildschirm: Muster M06 öffnen → Reiter „Tools & Wissen" → `rag_areas` schlägt die
  8 Bereiche vor; `01-base/safety-config` → `crisis_pattern` schlägt Muster-IDs vor und
  bietet „öffnen"; `escalation.mode` ist ein Auswahlfeld mit drei Werten.
* Ein Bereich mit einem Wert außerhalb der Liste bleibt speicherbar und verliert ihn nicht.

## 5 Risiken

| Risiko | Gegenmaßnahme |
|---|---|
| Eine `x-choices`-Liste ist unvollständig → Bedienung wird schlechter statt besser | Wächter über den ganzen Seed-Baum (S2) |
| Katalog-Endpunkt wird bei jedem Feld erneut geholt | Ein Abruf je Formular, im Dienst gehalten; der Effekt sitzt am Formular, nicht am Feld |
| Auswahlfeld wirft einen Bestandswert weg | Fremdwert wird als Option mitgeführt (§2a), Test dafür |
| Der Katalog-Abruf schlägt fehl und das Formular bleibt hängen | `ChoicesApi` fängt und merkt sich das; das Feld ist dann ein normales Textfeld wie vor S3 |

## 6 S5 — die langen Formulare

**Nutzer-Entscheid 2026-08-13: aufklappbare Abschnitte.** Nicht Reiter, nicht Sprungliste.

`form-sections.ts` schneidet ein Bereichs-Formular allein aus der Form des Dokuments —
**keine Tabelle je Bereich**, damit ein neues Modellfeld von selbst am richtigen Platz
erscheint statt bis zur nächsten Tabellenpflege im Auffangkorb zu liegen:

* Jeder Block (Gruppe, Liste, Karte, JSON, Fließtext) wird ein `<details>`.
* Die einzeiligen Felder ziehen in **einen** führenden Abschnitt „Grundwerte".
* Ist die Wurzel eine einzelne Hülle (`display_rules:`, `context_actions:`, `welcome:` —
  so bauen die meisten Bereiche), wird eine Ebene tiefer geschnitten. Sonst gäbe es genau
  einen Abschnitt und die Wand bliebe, nur mit einem Klick davor.
* Unter zwei Blöcken wird gar nicht gegliedert.
* Nicht bei Mustern: dort schneidet A7b schon in Reiter.

Nur der Sammel-Abschnitt bricht die Schema-Reihenfolge, bewusst und einmalig — dieselbe
Freiheit, die sich der Reiter-Schnitt nimmt.

`<details>` statt Reiter hat einen Nebeneffekt, der zählt: der Reiter-Schnitt rendert nur
den aktiven Reiter, die übrigen Felder sind **gar nicht im Dokument**. Ein zugeklappter
Abschnitt ist da.

Gemessen: `01-base/safety-config` → „Grundwerte" plus 8 Blöcke statt einer Wand aus 11.
Der Wächter `verliert kein Feld` reicht alle Abschnitts-Pfade zusammen an `pickFields` und
verlangt den vollen Baum zurück — ein Schnitt, der etwas verschluckt, fällt damit auf,
ohne dass der Test die Gruppierungsregel nachbaut.

## 7 Review-Nachlauf (2026-08-13) — 7 Befunde behoben

Ein Review der Pakete S1–S5 fand 0 kritische, 2 schwere, 4 kleine Befunde und einen Nit.
Alle behoben; jeder mit einem Test, der ohne den Fix fällt (gegengeprüft, nicht behauptet).

| # | Befund | Behebung |
|---|---|---|
| 1 | **Hülle in jedem Abschnitt.** `pickFields` auf der Wurzel behielt den Hüllen-Knoten, also stand über jedem Abschnitt zusätzlich `display_rules` — samt Einrückung, die nichts gliedert. Traf 16 von 34 Bereichen. | Ein Abschnitt beginnt jetzt **hinter** der Hülle: `FormSection.basePath` sagt, wo im Dokument er sitzt, das Formular bindet `[path]="basePath"` + `valueAt(basePath)`. Der Abschnitts-Rumpf trägt keine eigene Beschriftung mehr. |
| 2 | **`%2F` im Sprung-Link.** `['/bereich', area]` reichte `03-patterns/m06-…` als EIN Segment; `areas.component.ts` macht es seit jeher anders. | `linkSegments()` splittet am Schrägstrich. Test prüft das gerenderte `href`. |
| 3 | `ChoicesApi.failed` wurde gesetzt, nie gelesen. | Gestrichen. Der Fehlschlag bleibt still — das Feld fällt auf Freitext zurück, wie vor S3. |
| 4 | Kennung `sec-basics` konnte mit einem Feld namens `basics` kollidieren (`track` wirft). | Der Sammel-Abschnitt heißt `sec`, ohne Pfad-Anhang. |
| 5 | Eine `<datalist>` **je Feld**: ein Muster mit 8 Werkzeugen schrieb 8 × 41 Optionen in die Seite. | Eine Liste **je Katalog**, gerendert vom Formular; die `id` kommt aus dem Katalog-Namen. |
| 6 | Kein Test deckte den Hüllen-Fall ab — genau dort saß Befund 1. | Zwei Komponententests: keine Hüllen-Legende, und ein Schreibvorgang landet trotzdem unter der Hülle. |
| 7 | Der `effect` stand vor den Eingaben, die er liest. | Verschoben; liest jetzt `catalogsInUse()`, das auch die Listen speist. |

Nachweis: Studio 957 grün, Backend 3235 grün, `ng build studio` sauber, ESLint sauber.

## 8 Nachtrag: die Länge der Schnellantwort-Pillen

Anlass (Nutzer, Bildschirmfoto 2026-08-13): eine Pille las
„Erstelle ein Arbeitsblatt zu Kompetenzen geometrischer Optik" und brach zweizeilig um.

Ursache, gemessen: die einzige Längenregel stand als Regel 2 unter elf in
`quick_replies_llm.py` — **„max 6-8 Woerter"**. Der Satz oben hat sieben Wörter und ist
damit regelkonform; er hat aber 60 Zeichen. Im Deutschen ist die Wortzahl kein Längenmaß.
Und niemand prüfte nach: `generate_quick_replies` gab zurück, was das Modell lieferte.

Behoben in drei Schritten, eine Zahl:

* `display_rules.quick_replies.max_chars` (Vorgabe **48**) — Studio-pflegbar, Geschwister
  von `max_count`. Die 48 ist gemessen: die Beispiel-Vorschläge im Prompt selbst reichen
  bis 47 Zeichen. `0` schaltet den Deckel ab.
* Der Prompt nennt die Zahl **zweimal** — im ersten Satz und als Regel 2 mit Gegen-Beispiel
  — statt der Wortregel.
* `generate_quick_replies` **verwirft**, was darüber liegt. Verworfen und nicht gekürzt:
  der Pillentext IST die Nachricht, die der Klick abschickt; ein abgeschnittener Satz wäre
  schlimmer als eine Pille weniger. Beim Lotsen-Chip (`__guide__|Text|URL`) zählt nur die
  Beschriftung — im Knopf steht die URL nicht.

Nicht in `turn_persist` neben den Anzahl-Deckel gelegt, obwohl dort alle Quellen
zusammenlaufen: dort liefen auch die **redaktionell gepflegten** Chips durch (Zustimmung
zur Schreib-Abnahme, Kontext-Aktionen). Einen funktionalen Knopf wegen seiner Länge
verschwinden zu lassen wäre schlimmer als der Umbruch. Der Deckel greift dort, wo die
Prosa entsteht.

## 9 Nachlauf 2 (Nutzer-Befunde am laufenden Studio, 2026-08-13)

### 9a Vier Preset-Schlüssel fehlten im Modell

Das Formular meldete unter „Identität & Schutz": *4 Schlüssel werden hier nicht
angezeigt* — `presets.strict.legal_trigger_override`, `presets.paranoid.double_check`,
`presets.paranoid.threshold_multiplier`, `presets.paranoid.legal_trigger_override`.

Kein Datenmüll: alle drei Namen werden von `services/safety/service.py:66-68` ausgewertet
(`legal_trigger_override` entscheidet, ob der Rechts-Klassifikator überhaupt auslösen darf;
`threshold_multiplier` halbiert bei „paranoid" die Schwellen; `double_check` schaltet die
zweite Prüfung). Sie fehlten schlicht in `SafetyPreset` und waren damit nur im
Rohtext-Reiter erreichbar.

Nachgetragen mit **genau den Vorgaben, die `_resolve_preset` einsetzt**, wenn ein Preset
den Schlüssel weglässt (`False` / `1.0` / `False`) — eine andere Zahl im Formular hiesse,
die Oberfläche verspricht etwas anderes als der Code tut. Wächter dagegen:
`test_safety_presets_sind_vollstaendig_modelliert` vergleicht die Preset-Schlüssel des
Seeds gegen `SafetyPreset.model_fields`.

### 9b Fließtext in einer Zeile

`structure` in den Material-Formaten (bis 729 Zeichen) stand in einem einzeiligen Feld.
`MULTILINE_KEYS` kannte nur `body`.

Gemessen statt geraten — jeder Schlüssel, unter dem im Seed-Baum ein String über 120
Zeichen steht:

```
cd backend && python -c "import pathlib,yaml,collections; c=collections.Counter(); \
walk=lambda n,k='': [walk(v,str(kk)) for kk,v in n.items()] if isinstance(n,dict) else \
([walk(v,k) for v in n] if isinstance(n,list) else (c.update([k]) if isinstance(n,str) and len(n)>120 else None)); \
[walk(yaml.safe_load(p.read_text(encoding='utf-8'))) for p in pathlib.Path('seeds').rglob('*.yaml')]; print(sorted(c))"
```

Ergebnis: 22 Schlüssel, `structure` bis 729, `description` bis 671, `pattern` bis 1013.

Entschieden wird nach dem **Schlüsselnamen**, nicht nach dem Wert: eine Entscheidung am
Wert liesse ein Feld beim Tippen die Bauart wechseln und den Fokus verlieren. Ein zu
großzügiger Treffer kostet nur Höhe, ein verpasster die Bearbeitbarkeit.

Zwei Ergänzungen:

* `rules:` ist eine **Liste** langer Sätze; das Element hat keinen eigenen Schlüssel.
  `inheritMultiline` vererbt die Entscheidung deshalb vom Listen-Schlüssel.
* Die Höhe kommt aus dem Inhalt (`rows()`, 3–20 Zeilen à ~70 Zeichen) statt fest bei 14 zu
  stehen. Ein Attribut, kein Elementwechsel — wächst also beim Tippen mit, ohne Fokusverlust.

Zwei Bestandstests nutzten zufällig echte Fließtext-Schlüssel (`greeting`, `pattern`) als
Beispiel und erwarteten `text`. Ihr Thema ist `$ref`-Auflösung bzw. Listen-Abbildung, nicht
die Feldart — Beispielschlüssel auf `label` geändert, Zusage unverändert.

### 9c Was der frontmatter bei den Domänen-Regeln tut (Nutzer-Frage)

Nachgesehen statt geraten, und die Antwort ist zweigeteilt:

* **`02-domain/*` (Domain-Wissen):** `load_domain_rules()`
  (`config_loader/personas.py:87-97`) setzt Frontmatter **und** Body wieder zu einem
  Dokument zusammen (`join_frontmatter`) und reicht das komplett in den System-Prompt —
  ALT las die Datei roh, das ist verbatim portiert. Der YAML-Kopf steht also wörtlich im
  Prompt und kostet Tokens; das Modell liest ihn mit.
* **`01-base/base-persona`, `01-base/guardrails`:** `load_base_persona()` /
  `load_guardrails()` nehmen **nur** `body`. Dort ist der Frontmatter reine Buchhaltung.

Von den Feldern selbst wertet **kein** Code eines aus: `always_active`, `layer`,
`priority`, `variant`, `version` haben im ganzen Backend keinen Leser (nur die
Modelldefinition). Sie sind Herkunfts- und Sortier-Notiz aus der ALT-Dateiablage — im
Domain-Fall zusätzlich Prompt-Text.

Keine Änderung daran: die Prompt-Gleichheit zu ALT ist eine Zusage des Neubaus. Wer den
Kopf aus dem Prompt nehmen will, ändert damit die Antworten und braucht einen Golden-Lauf.

**Randnotiz zur Gliederung (S5):** ein LayerDoc hat genau zwei Abschnitte —
`frontmatter` und `body`. Offen ist der erste, also die Metadaten; der eigentliche Text
liegt einen Klick tiefer. Bewusst nicht angefasst: „welcher Abschnitt ist der wichtigste"
ist nicht aus dem Schema ableitbar, und eine Tabelle je Bereich war der Entwurfsfehler,
den §6 gerade vermeidet.

### 9d Der Element-Browser hat den Bereich eingefärbt

Nutzer-Befund: `04-intents/intents` meldete **11** unbekannte Schlüssel
(`intents[0].file` … `intents[10].file`), `04-states/states` drei, `04-entities/entities`
fünf — jeweils genau so viele, wie der Bereich Einträge hat.

Kein fehlendes Modellfeld. `GET /api/config/elements` hängte jedem Eintrag seine
Quelldatei an — **in die Objekte hinein**, die die Lade-Fassade herausreicht:

```python
intents = cl.load_intents()          # == area("04-intents/intents")["intents"]
for i in intents:
    i["file"] = "04-intents/intents.yaml"   # schreibt in den Prozess-Cache
```

Ein Aufruf des Element-Browsers genügte, und der Bereich trug den Schlüssel für die
Lebensdauer des Prozesses mit. Das Formular meldete ihn korrekt als unbekannt — und wäre
gespeichert worden, wie der Hinweis dort sagt („Beim Speichern bleiben sie erhalten").
Aus einer Anzeige-Angabe wäre ein Konfigurationswert geworden.

Bemerkenswert: zwei Zeilen darüber macht derselbe Endpunkt es richtig — Personas werden
über `entry = dict(p)` kopiert, Patterns frisch aufgebaut. Nur diese drei Listen wurden
in place beschrieben.

Behoben mit `_with_source()` (Kopie statt Mutation) plus einem Wächter, der nach einem
`/elements`-Aufruf die drei Bereiche zurückliest. Die eigentliche Falle steht aber im
Vertrag der Fassade, also jetzt auch dort: `_store.area()` sagt im Docstring, dass es das
Cache-Objekt herausgibt und niemand hineinschreiben darf.

Ein Streifzug über alle `load_*`-Verbraucher fand keinen zweiten Fall. Der einzige
Kandidat (`api/config.py:327`, `cfg["header_nav"] = …`) ist harmlos:
`load_guide_mode_config()` baut ein frisches Dict.

**Für den laufenden Server:** ein Neustart räumt den vergifteten Cache. Wurde einer der
drei Bereiche im Studio gespeichert, solange er vergiftet war, steht `file:` jetzt in der
DB — im Rohtext-Reiter sichtbar und dort zu entfernen.

## 10 Abnahme am ruhenden Stand (2026-08-13, nach der Prompt-Auslagerung)

Der Prompt-Split lief in derselben Arbeitskopie, also erst danach geprüft — sonst hätten
sich zwei pytest-Läufe dieselben Postgres-Testdatenbanken weggezogen.

| Prüfung | Befehl | Ergebnis |
|---|---|---|
| Backend-Lint | `uv run ruff check src tests` | All checks passed |
| Backend-Tests | `uv run pytest -q` | 3237 passed, 4 skipped (2:18) |
| Vertrag + Pakete des Tages | `pytest test_quick_replies_llm test_config_area_endpoints test_config_seed_tree test_openapi_contract` | 75 passed |
| Schema-Fixture aktuell | `export_area_schemas.py` + Hash-Vergleich | unverändert (64340544f6a925e2) |
| Frontend-Lint | `eslint .` | 0 |
| Gates | `check:tokens` · `check:a11y` · `check:radii` | alle drei grün |
| Tests | `ng test ui` / `widget` / `studio` | 757 / 56 / 961 |
| Typprüfung | `ng build studio` + `ng run widget:build-widget` | beide sauber |
| Widget-Budget | `check-widget-budget.mjs` | roh 89,6 % · gzip 89,4 % von §5.5 |

Zusammen **5011 Tests grün**.

**Ein Befund aus der eigenen Checkliste, sofort behoben:** `schema-field.component.ts` war
durch die mitwachsende Textflächen-Höhe auf **315 Zeilen** gewachsen — über die
300er-Schwelle. Die beiden reinen Helfer (`safeIdPart`, `nextFreeKey`) sind nach
`field-ids.ts` gezogen; die Komponente steht bei 297, das neue Modul bei 28. Reiner
Umzug, keine Logikänderung — Studio danach erneut 961 grün, Build sauber.

**Die Prompt-Auslagerung war verhaltensgleich.** Nicht geglaubt, sondern nachgerechnet:
der System-Prompt aus dem Git-Index gegen den in `quick_replies_prompt.py` gestellt, 159
gegen 165 Zeilen, **8 geänderte Zeilen — und zwar genau die aus §8** (der neue erste Satz
und die umgeschriebene Regel 2). Der ganze Rest ist Zeile für Zeile identisch. Die Tests
allein hätten das nicht gezeigt: sie pinnen den Prompt nur an Stichproben.

Der Schnitt selbst ist sauber gelegt — `quick_replies_prompt` liest **keine** Config, jeder
Wert kommt als Argument; der Zeichen-Deckel und sein Filter bleiben zusammen in
`quick_replies_llm`.
