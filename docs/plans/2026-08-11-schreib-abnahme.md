# Schreib-Abnahme — was der Nutzer vor einer Änderung sieht (Auftrag c)

**Stand 2026-08-11 — S0–S4 gebaut und belegt.**
Offen nur noch Nutzer-Domäne: **Seed-Import** (sonst wirkt S4 nur zur Hälfte),
Widget-Bundle neu bauen, Live-Smoke gegen einen angemeldeten MCP-Server.

## ⚠ Fund beim Bau: die Bestätigung konnte nie eingelöst werden

Beim Verdrahten von S2 stellte sich eine Frage, die die Messung nicht gestellt
hatte: *Wird die Sitzung vor oder nach dem Verbrauch geschrieben?* Die Antwort
deckte einen Fehler auf, der größer ist als alles in M1–M6.

`session_state` wird **jeden Zug neu aus fünf Spalten gebaut**
(`graph/nodes/setup.py:63`), und `update_session` schreibt genau diese fünf —
darunter `entities`, aber **keinen Sammeltopf für die oberste Ebene**
(`turn_persist.py:203-211`). Der Merkposten lag auf der obersten Ebene
(`session_state["_pending_write"]`). Er wurde also **nie gespeichert**.

Folge: `_pending_at_turn_start` war im Betrieb **immer `None`**. Kein „ja"
konnte je eine Änderung auslösen — jede Bestätigung fiel auf eine neue Vorschau
zurück, endlos. Der Wall war kein Wall, sondern eine Sackgasse.

**Warum 2888 grüne Tests das nicht fanden:** `test_bestaetigung_im_spaeteren_zug`
*speist* den Merkposten direkt in den Tool-Loop ein — auf derselben obersten
Ebene, die der Code annahm. Die Attrappe teilte die Annahme des Codes, statt die
Wirklichkeit abzubilden. Dieselbe Fehlerklasse wie bei den P11-Live-Funden
(LiteLLM-Antwortformen): *nach dem Code gebaut, nicht nach der Welt.*

**Behoben:** Der Merkposten wohnt jetzt in `entities` — dort, wo die übrigen
zugüberdauernden Merker schon liegen (`_last_pattern`, `_frame`,
`_canvas_material_type`) und wo der Debug-Auszug `_`-Schlüssel wieder
herausstreicht: gespeichert **und** unsichtbar. Neu gepinnt wird die
**Verbindung** und nicht eine der beiden Seiten
(`test_offener_schreibvorgang_ueberlebt_den_zug`), denn genau dazwischen lag
der Fehler.

Der Vorschautext bleibt bewusst auf der obersten Ebene: er darf den Zug **nicht**
überdauern, dort wird nichts gespeichert — hier ist das die gewünschte
Eigenschaft. Die beiden Nachbarn wohnen also aus demselben Grund verschieden.

## Der Auftrag, wörtlich

> „der flow sollte sein das man alles was geschrieben wird dem user zur abnahme
> anzeigt und um zustimmung oder anpasung fragt"

Drei Forderungen, und sie sind nicht dieselbe:

1. **alles was geschrieben wird** — vollständig, nicht ausgewählt.
2. **anzeigen** — der Nutzer sieht es, nicht ein Zwischenerzähler.
3. **um Zustimmung *oder Anpassung* fragen** — die Frage hat zwei Ausgänge,
   nicht einen.

## Messung

Gemessen am Code, nicht angenommen. Jede Zeile unten ist belegt.

### M1 — Der Server schreibt die Abnahme bereits, und zwar für einen Menschen

`previewReply` (`wlo-mcp-server-sc/src/tools/curation-shared.ts:219`) baut auf
jeden Aufruf ohne Schlüssel:

```
Bitte prüfen — bisher wurde nichts geändert:

<renderChangeSet>

⚠ <Hinweise>

<was als Nächstes passiert> Dazu denselben Aufruf mit confirmToken: <schlüssel> wiederholen.
Der Schlüssel gilt einmalig und zehn Minuten lang.
```

`renderChangeSet` (`services/write/change-set.ts:164`) ist ein fertiger
deutscher Unterschied, eine Änderung je Zeile:

* der Handlungssatz (`cs.action`),
* bei Löschungen `Löscht: <Titel> (<nodeId>)` — bewusst ungekürzt, weil ein
  stiller Schnitt hier am teuersten wäre,
* je Feld `Label: „alt" → „neu"`, leere Felder als `(leer)`,
* Sammelfelder als `Label: + <neu hinzugekommen>`,
* Werte über 600 Zeichen mit offengelegtem Schnitt:
  `… […] (Anfang gezeigt, insgesamt N Zeichen)` (`change-set.ts:132,147`).

Der Kommentar des Servers nennt den Adressaten selbst: *die deutsche Vorschau,
die der Nutzer vor dem Bestätigen liest.* Forderung 1 ist also **schon erfüllt**
— eine Ebene tiefer, als wir bisher hingesehen haben.

### M2 — Dieser Text erreicht den Nutzer nie

Die Kurationswerkzeuge stehen **nicht** in `CARD_YIELDING_TOOLS`
(`services/tool_loop.py:73`), erzeugen also keine Karte. Die Schleife gibt nur
`(text, cards, tools_called, outcomes)` zurück (`tool_loop.py:1122`). Der
Vorschautext landet ausschließlich hier:

```python
messages.append({"role": "tool", "tool_call_id": tc.id, "content": …})   # tool_loop.py:1038
```

— in der Nachrichtenkette des Modells. **Was der Nutzer liest, ist die
Nacherzählung des Modells.** Forderung 2 ist nicht erfüllt.

### M3 — Die einzige Zusage ist eine Prompt-Zusage, und sie sagt das Gegenteil

Zwei Stellen tragen sie, beide nur als Anweisung an das Modell:

* `_ZWEISTUFIG` (`services/mcp/tool_defs_curation.py:50`): „Zeige dem Nutzer,
  was sich aendern wuerde, und frage ihn."
* M18 `core_rule` (`seeds/03-patterns/m18-kuration.md:58`): „Diese Vorschau wird
  dem Nutzer VOLLSTÄNDIG und **in seinen Worten** vorgelegt."

„In seinen Worten" ist wörtlich eine Paraphrase-Anweisung — das Gegenteil von
„alles was geschrieben wird anzeigen". Und die zwei Bestandteile, die die
Ehrlichkeit der Vorschau tragen, sind genau die, die ein Zusammenfasser als
Erstes weglässt: die `⚠`-Hinweise und die Offenlegung des Schnitts.

Der Nutzer stimmt damit einer **Beschreibung** zu, nicht der Nutzlast.

### M4 — „Anpassung" ist mechanisch da, wird aber nie angeboten

Mechanisch trägt es: eine neue Vorschau überschreibt den offenen Vorgang
bedingungslos (`tool_loop.py:923`), der Fingerabdruck ist der neue. Ein Nutzer,
der von sich aus „nein, der Titel soll X heißen" sagt, bekommt also eine neue
Vorschau und kann die bestätigen.

Angeboten wird es nirgends. M18 Schritt 3 lautet „Dann fragen, ob es so stimmt"
— eine Ja/Nein-Frage. Weder Muster noch Oberfläche laden zum Ändern ein.
Forderung 3 ist halb erfüllt: der Weg existiert, das Angebot fehlt.

### M5 — Befund am Rande: die Bestätigung kann still zur Vorschau werden

`token_for` (`domain/write_confirm.py:162`) gibt den Schlüssel nur heraus, wenn
Werkzeug **und** Fingerabdruck übereinstimmen; der Fingerabdruck ist das
sortierte JSON der Argumente (`write_confirm.py:133`). Die Argumente kommen
für Kurationswerkzeuge unverändert vom Modell (`tool_loop.py:655`; die
Anreicherung ab Zeile 840 fasst nur Suchwerkzeuge an).

Nennt das Modell im Bestätigungszug ein optionales Feld mehr oder weniger als
im Vorschauzug, passt der Fingerabdruck nicht mehr. Dann passiert Folgendes:
kein Schlüssel → Aufruf ohne Bestätigung → der Server antwortet mit **einer
neuen Vorschau**. Der Nutzer hat „ja" gesagt und wird erneut gefragt.

Das ist nicht gefährlich (die Wall hält), aber es ist **stumm**: nichts wird
protokolliert. Der Schwesterfall — der Vorschautext des Servers hat sich
geändert — bekommt ausdrücklich eine Warnung (`tool_loop.py:941`). Dieser hier
nicht. Wer das im Betrieb sucht, findet nichts.

### M6 — Was schon da ist und den Bau billig macht

* **`InlineDocument`** (`api/schemas_inline.py:13`): `kind` / `title` /
  `content` / `meta`, gerahmte Box im Verlauf, Markdown über denselben
  DOMPurify-Renderer. Steht bereits im eingefrorenen Vertrag.
* Das Widget hat für unbekannte `kind` **beide Male einen Rückfall**
  (`ui/src/inline-doc/inline-doc.ts:28,42`) — eine neue Art rendert also auch
  ohne Frontend-Änderung, nur ohne eigenes Symbol.
* Gebaut werden Inline-Dokumente heute in `turn_persist.py:441-481`, hart
  begrenzt auf M09/M10/M11 (Zeile 448). Die Kuration ist dort nicht vorgesehen.
* **`session_state` wird von der Schleife an Ort und Stelle geändert** (so
  überlebt `_pending_write` den Zug) und liegt im Antwortknoten vor
  (`graph/nodes/respond.py:65`). Das ist die Naht, die **keine
  Signaturänderung** kostet.

### Zusammenfassung der Messung

| Forderung | Stand |
|---|---|
| alles was geschrieben wird | ✅ der Server formuliert es bereits vollständig |
| dem Nutzer anzeigen | ❌ es endet in der Nachrichtenkette des Modells |
| um Zustimmung fragen | ⚠ nur als Prompt-Anweisung, unüberprüfbar |
| oder Anpassung | ⚠ Weg vorhanden, Angebot fehlt |

Der Auftrag ist damit **kein Neubau**, sondern eine fehlende Leitung: ein Text,
der für den Menschen geschrieben wurde, kommt beim Menschen nicht an.

## Ansätze

**A — Nur den Prompt schärfen.** M18 verlangt wörtliches Zitieren statt
„in seinen Worten".
*Kosten:* fast null. *Risiko:* unverbindlich. Ob das Modell zitiert hat, kann
der Nutzer nicht erkennen — er sieht ja nur, was das Modell geschrieben hat.
Löst Forderung 2 nicht, sondern formuliert sie nur strenger.

**B — Deterministische Vorschau-Box.** Die Schleife legt den (bereits vom
Schlüssel befreiten) Vorschautext in den offenen Vorgang; die Zug-Montage
rendert ihn als `InlineDocument`. Der Fließtext des Modells wird zum
Begleittext, die Box zur Wahrheit.
*Kosten:* klein, Naht existiert. *Zusicherung:* der Nutzer sieht den Text des
**Servers**, unverändert, unabhängig davon, was das Modell erzählt.

**C — B plus ausdrückliches Angebot.** Die Box endet mit der Doppelfrage, und
ein Quick-Reply „Ja, so ausführen" steht daneben. Erst damit ist „Zustimmung
**oder Anpassung**" beantwortet und nicht nur möglich.

**D — Felder im Widget bearbeitbar machen.** Der Nutzer ändert Werte im
Formular, das Widget schickt sie strukturiert zurück.
*Kosten:* neuer Vertrag, neue Oberfläche, neue Angriffsfläche. *Urteil:*
über den Auftrag hinaus. „Anpassung" heißt im Chat: es sagen können.

**Empfehlung: B, dann C.** B ist die Zusicherung, C das Angebot. A ist als
Beiwerk in B enthalten (M18 muss ohnehin von der Nacherzählung entlastet
werden), D ist YAGNI.

## Schnitt und Stand

| Scheibe | Inhalt | Stand |
|---|---|---|
| **S0** | M5 aufzeichnen, wenn ein offener Vorgang nicht bestätigt wurde | ✅ |
| **S1** | Vorschautext den Zug überleben lassen (`session_state["_write_preview"]`) | ✅ |
| **S2** | `InlineDocument(kind="schreib_vorschau")` in der Zug-Montage | ✅ |
| **S3** | Symbol, Titel, Doppelfrage im Kastenfuß, Quick-Reply „Ja, so ausführen" | ✅ |
| **P** | **Merkposten nach `entities`** — Fund oben, ohne ihn ist alles Übrige Zierde | ✅ |
| **S4** | M18 **und** die Werkzeug-Beschreibung entlasten: einordnen statt nacherzählen | ✅ (Seed wirkt erst nach Import) |

**Drei Entwurfsentscheidungen, die sich im Bau gegen den Plan geändert haben:**

1. **S0 wurde INFO statt WARNING.** „Offener Vorgang, gleiches Werkzeug, anderer
   Fingerabdruck" ist nicht zwingend ein Fehler — es ist auch genau der Weg,
   den eine *Anpassung* nimmt. Von innen sind beide nicht unterscheidbar. Eine
   Warnung hätte auf dem Glücksfall des Auftrags Lärm gemacht. Aufgezeichnet,
   nicht angeklagt — mit einer Gegenprobe, die verbietet, dass ein *anderes*
   Werkzeug die Zeile auslöst (sonst stünde sie in jedem zweiten Protokoll).
2. **Der Vorschautext wohnt nicht im Merkposten** (so stand es in S1). Der
   Bestätigungspfad *entfernt* den Merkposten; läge der Text darin, risse eine
   Bestätigung in demselben Zug eine frisch erzeugte Vorschau mit. Eigener,
   zug-eigener Schlüssel, von der Antwort **verbraucht** statt gelesen.
3. **`kind` heißt `schreib_vorschau`, nicht `write_preview`.** Die bestehenden
   Werte sind deutsch (`lernpfad`, `ki_material`, `bericht`) — es sind Daten,
   keine Bezeichner.

Kein neues Symbol gezeichnet: `edit_note` gab es bereits und trifft genau —
vorgeschlagene Änderungen. Bewusst **nicht** `check`: ein Haken behauptete, es
sei schon geschehen, und das ist der Punkt der Box nicht.

### S4 — die Anweisung stand an ZWEI Orten, nicht an einem

Der Plan nannte nur M18. Gemessen wurde ein zweiter, gleichrangiger Ort:
`_ZWEISTUFIG` in `services/mcp/tool_defs_curation.py:50` — der Satz, der an
jeder Werkzeug-Beschreibung hängt und ebenfalls sagte *„Zeige dem Nutzer, was
sich ändern würde"*. Nur den Seed zu ändern hätte die Doppelung von der einen
Stelle an die andere verschoben.

Die beiden **müssen** dasselbe sagen: sie sprechen zum selben Modell im selben
Zug. Widersprechen sie sich, bekommt es zwei Aufträge — dieselbe Falle wie bei
C1-f1, wo eine Sprachdirektive dreimal wortgleich im Prompt stand. Deshalb ein
Wächter **je Ort**, und beide nennen einander:
`test_m18_laesst_die_vorschau_zeigen_statt_nacherzaehlen` (Seed) ·
`test_keine_beschreibung_verlangt_die_nacherzaehlung` (Code).

Vor dem Schreiben zwei Dinge nachgesehen statt angenommen:

* **`core_rule` hat Verbraucher** — `response_prompt_pattern.py:161` rendert
  sie als „### Kernregel (HART)". Kein neunter Fall von „dokumentiert ohne
  Konsumenten".
* **Der längere Text bläht den Klassifikator nicht auf.** Dort ist `core_rule`
  nur der *Rückfall*, wenn `short_purpose` fehlt (`classify_prompt_blocks.py:322`)
  — und auf 100 Zeichen gedeckelt. M18 hat eine `short_purpose`, der neue Text
  landet also ausschließlich im Antwort-Prompt.

Neu in der Kernregel, und seit dem Fingerabdruck-Fund die tragende Zeile: nach
dem Ja wird **mit denselben Argumenten** aufgerufen, Feld für Feld. Bisher
stand das nur in der Werkzeug-Beschreibung.

Die Groß-/Kleinschreibung hat den Wächter zuerst zu Fall gebracht: der Seed
betont per Versalien (`DENSELBEN ARGUMENTEN`), also vergleicht die Prüfung
kleingeschrieben — ob eine Regel dasteht, darf nicht an der Schreibweise hängen.

## Offene Entscheidungen (Nutzer)

1. **Box statt Nacherzählung, oder Box zusätzlich?** Empfehlung: zusätzlich —
   das Modell ordnet ein („Ich würde folgendes ändern:"), die Box zeigt. Ein
   reiner Box-Zug ohne Worte wirkt im Chat abweisend.
2. **Quick-Reply „Ja, so ausführen"?** Empfehlung: ja. Ein Chip ist die
   kürzeste Zustimmung und macht zugleich sichtbar, dass es eine Entscheidung
   ist. Ein „Ändern"-Chip dagegen **nicht**: er könnte nur einen Satz senden,
   den der Nutzer besser selbst formuliert.
3. **Gilt die Box auch für `wlo_list_suggestions`?** Nein — es ändert nichts
   und führt keinen Schlüssel (`write_confirm.py:80`).

## Belegt (2026-08-11)

| Gate | Ergebnis |
|---|---|
| `uv run pytest -q` | **2905 passed, 4 skipped, 0 failed** (vorher 2888; +17) |
| `uv run ruff check src/boerdi tests/` | All checks passed |
| `scripts/export_openapi.py --check` | **openapi contract unchanged** |
| `npx ng test ui` | 69 Dateien, **701 passed** |
| `npm run build:widget` | 523,25 kB raw / 129,27 kB transfer |
| `node scripts/check-widget-budget.mjs` | **§5.5-Budget eingehalten** (87,2 % raw · 87,3 % gzip) |
| `npx playwright test` | **46 passed** (44 vorher + 2 neue) |

Jede Scheibe rot-grün gefahren, mit dem Fehlschlag als Beleg:
`assert 'wlo_create_collection' in ''` (S0) · `KeyError: '_write_preview'` (S1)
· `assert resp.inline_documents == []` bzw. `'A' == 'Ja, so ausführen'` (S2/S3)
· `KeyError: 'entities'` (P) · Frontend `expect(inlineDocIcon('schreib_vorschau'))`.

## Verifikation (vor dem Bau festgelegt)

* S0: Test, der einen offenen Vorgang mit **abweichenden** Argumenten fährt und
  die Warnung erwartet — muss ohne die Änderung fallen (rot-grün belegen).
* S1: die Vorschau steht im Zustand, **ohne** Schlüssel; der Schlüssel taucht
  in keinem der beiden Felder auf.
* S2: ein Zug mit Vorschau liefert genau ein `InlineDocument`; ein Zug mit
  Ausführung keines; der Inhalt ist byte-gleich mit dem redigierten Servertext.
* S3: `npx ng test ui`, Tastaturbedienung, Kontrast; 320 px.
* Gesamt: `uv run pytest -q`, `uv run ruff check`,
  `scripts/export_openapi.py --check` (der Vertrag darf sich **nicht** ändern —
  `inline_documents` gibt es bereits), `npm run budget`.

### Was der e2e-Beleg zeigt — und was nicht

`e2e/write-preview.spec.ts` fährt die gerenderte Seite: der Kasten erscheint,
trägt seinen Titel, enthält **jede** Änderungszeile (nicht eine Auswahl), zeigt
die Doppelfrage im Fuß, der Chip ist da, der Begleittext des Bots steht daneben
— und ein Klick auf den Chip geht als gewöhnliche Nutzer-Nachricht heraus, was
die Voraussetzung dafür ist, dass der Folgezug bestätigen kann.

**Nicht** gezeigt: dass Backend und Widget dieselbe `kind`-Zeichenkette meinen.
Der Test *liefert* die Nutzlast selbst; er wäre auch mit `write_preview` auf
beiden Seiten grün. Die Übereinstimmung ruht auf zwei Tests, die dasselbe Wort
nennen (`test_persist_schreib_vorschau_wird_eine_box` ·
`inline-doc.spec.ts`). Bewusst keine Maschinerie dagegen gebaut: driftet es,
fällt der Kasten auf das allgemeine Symbol zurück — kosmetisch, nicht kaputt,
weil `inlineDocIcon` und `inlineDocFallbackLabel` beide einen Rückfall haben.

Kein `try/except` um den Box-Block, anders als beim M09-Nachbarn: `render`
gibt bei unbekanntem Schlüssel den Schlüssel zurück statt zu werfen
(`i18n/catalogue.py:37`), und `preview_for_display` ist ein Regex-Ersetzen.
Ein Fangblock könnte hier nur einen echten Fehler stumm schlucken.

## Risiken

* **Doppelung.** Modell erzählt nach *und* Box zeigt → derselbe Inhalt zweimal.
  Gegenmittel: S4 (M18 auf Einordnen statt Wiedergeben umstellen). Bis der Seed
  importiert ist, bleibt die Doppelung bestehen — sichtbar, nicht falsch.
* **Länge.** Ein Kompendiumtext darf 100 000 Zeichen haben; der Server zeigt
  600 davon und sagt es. Die Box erbt diese Grenze, erfindet keine eigene.
* **Fremdtext in der Box.** Der Vorschautext enthält Werte aus dem Bestand.
  Er wird wie jedes Inline-Dokument über DOMPurify gerendert — kein neuer Pfad.
