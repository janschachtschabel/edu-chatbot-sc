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
| **S5** | **Die Abnahme einlösbar machen** — drei stille Stellen, siehe unten | ✅ (2026-08-15) |
| **S6** | **Zwischenspeicher nach Aufrufer trennen** — dabei gefunden, kein Schreib-Thema | ✅ (2026-08-15) |

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
(`i18n/catalogue.py:37`), und `preview_for_display` schneidet eine Zeichenkette
an einer gesuchten Stelle (seit S7 kein Regex mehr, aber ebenso wurffrei).
Ein Fangblock könnte hier nur einen echten Fehler stumm schlucken.

## S5 — die Abnahme war zeigbar, aber nicht einlösbar (2026-08-15)

Nutzer-Befund, live: *„selbst mit Anmeldung komme ich bei Erstellung und Upload
nur bis zu der Stelle, das er eine Bestätigung will — die aber immer wieder
gefragt wird und es geht nicht weiter."*

Alles bis zur Box war richtig. Der Rückweg lief über **drei** Stellen, und keine
davon meldete sich. Sie liegen in verschiedenen Schichten und wurden deshalb
einzeln gemessen, nicht erschlossen:

| # | Stelle | Wirkung | Messung |
|---|---|---|---|
| 1 | `mcp/tool_args.validate_tool_args` | `confirmToken` steht in **keinem** Argument-Modell (bewusst — er gehört nicht zu dem, was ein Modell bestimmen darf). Pydantic übergeht unbekannte Felder still, `_export_non_empty` gibt nur deklarierte zurück. Der Schlüssel fiel heraus ⇒ **jede Ausführung war wieder eine Vorschau**. | `validate_tool_args('wlo_create_collection', {'title':'Optik','confirmToken':'…'})` → `{'title': 'Optik'}` |
| 2 | `mcp/tool_cache._TOOL_CACHE_BLOCKLIST` | Vorgabe war „alles cachen", gesperrt nur `wlo_health_check`. Weil (1) den Schlüssel VOR `_cache_key` entfernte, hatten Vorschau und Ausführung **denselben** Cache-Schlüssel: der Ausführungsaufruf bekam die alte Vorschau zurück, ohne dass der Server je davon erfuhr. | Blocklist enthielt kein einziges kuratierendes Werkzeug |
| 3 | Der Merkposten war nur im Tool-Loop bekannt | Einlösen hing an zwei Modell-Entscheidungen: der Klassifikator musste auf ein „ja" hin M18 treffen (nur dieses Muster nennt die schreibenden Werkzeuge), und das Modell musste Argumente rekonstruieren, die es **nie gesehen hat** — die Historie trägt nur Texte, die Vorschau ist ein Inline-Dokument daneben. Bei einem Upload grundsätzlich unmöglich. | `_pending_write` kommt in `src/` an genau vier Stellen vor, alle in `tool_loop.py` |

**Warum (1) und (2) zusammen so schwer zu sehen waren:** sie erzeugten kein
Fehlerbild, sondern eine plausible Wiederholung. Kein 401, kein Timeout, keine
Warnung — und wegen (2) nicht einmal ein Eintrag im Server-Protokoll. Von aussen
sah es nach einem Anmeldeproblem aus. Es war keines: **eine Vorschau zu bekommen
setzt voraus, dass der Server den Schreibaufruf angenommen hat.**

**Der Schnitt.** (1) und (2) sind Reparaturen am Weg nach draussen. (3) ist die
Entwurfsentscheidung: eine Abnahme ist ein **bestimmter Zustand** — Werkzeug,
Argumente und Schlüssel liegen fertig im Merkposten, die Zustimmung steht in der
Nachricht des Menschen. Sie einzulösen braucht kein Modell. Deshalb
`services/write_approval`, eingehängt im `preflight`-Knoten vor dem
Klassifikator; dieselbe Bauart und dieselbe Begründung wie `content_text_action`
(wo der Wortlaut zählt, hat das Modell nichts zu suchen). Das ist zugleich die
**stärkere** Zusicherung: ausgeführt wird, was in der Box stand, Zeichen für
Zeichen — und nicht, was ein Modell daraus rekonstruiert.

Der Weg über das Modell (`tool_loop`) bleibt unangetastet: er trägt weiter den
Fall, in dem nichts gemerkt werden konnte (Argumente über
`MAX_REMEMBERED_ARGS_BYTES`).

**Die Zug-Regel wird dabei nicht weicher, sondern härter.** Der Tool-Loop braucht
einen Schnappschuss vom Zug-Eintritt, um eine im selben Zug erzeugte Vorschau
nicht sofort bestätigen zu können. `write_approval` braucht ihn nicht: sein
`session_state` kommt aus der Datenbank und enthält ausschliesslich Vorgänge
früherer Züge.

### S5-Nachlauf — was das Review am selben Tag fand

Drei Sachen, alle im neuen Pfad, alle mit einer gemeinsamen Wurzel: **wie ein
Fehlschlag aussieht.**

`call_mcp_tool` gibt *immer* einen String zurück, auch im Fehlerfall
(`"MCP error: …"`) — `transport.call_tool` fängt dafür jede Ausnahme ab, auch
Zeitüberschreitung und „Server weg". Für einen Aufrufer mit einem Modell
dahinter ist das richtig: das Modell liest den Text und ordnet ihn ein. Für
einen **deterministischen** Aufrufer ist es eine Falle — ein Fehlschlag sieht
aus wie ein Ergebnis.

| | Vorher | Jetzt |
|---|---|---|
| Fehler-String | lief in den Erfolgszweig: Protokoll meldete „eingelöst", der Nutzer bekam die rohe Servermeldung als Bot-Antwort, Merkposten verbraucht | `is_mcp_error` beim Erzeuger; führt in denselben ehrlichen Zweig wie eine Ausnahme |
| Fehlertext | „…und es wurde nichts geändert" — eine Behauptung, die niemand belegen kann | sagt, was feststeht, und schickt zum Nachsehen (`write.executeUnconfirmed`) |
| >1 vorbereitete Anfrage | still verworfen | Warnung, wortgleich zum Nachbarn `turn_persist` |

Die Prüfung auf den Präfix gab es schon **viermal als Literal**
(`page_context` 3×, `page_duplicate` 1×). Eine fünfte Kopie wäre genau die
Drift gewesen, die den Fehler erst möglich gemacht hat — deshalb wohnt die
Frage jetzt bei `services/mcp/client.is_mcp_error`, und die vier
Bestandsstellen nutzen sie.

**Warum ein Text für beide Fehlerwege und nicht zwei.** Ablehnung und
Zeitüberschreitung sind an dieser Naht nicht unterscheidbar. „Nichts geändert"
wäre im zweiten Fall falsch — und zwar teuer: die Person legt dieselbe Sache
erneut an. Konservativ in die richtige Richtung: nachsehen kostet eine Minute,
eine Dublette bleibt im Bestand. Wer die Fälle trennen will, muss zuerst den
Transport dazu bringen, sie zu unterscheiden.

### S5-Nachlauf 2 — die zwei offenen Punkte

**Punkt 1: die Fehlerarten sind jetzt unterscheidbar.** Der Text oben sagte,
das ginge nur, wenn der Transport die Fälle trennt — genau das ist gebaut.
`transport.call_tool` markiert sein Fehler-Dict mit `kind: "tool" | "transport"`
(nur dort liegt die Unterscheidung überhaupt noch vor), und
`client.call_mcp_tool_status` reicht sie als `(text, art)` weiter.
`call_mcp_tool` bleibt unverändert die Zeichenkette — der Vertrag für 25
Aufrufstellen und für das Modell, das den Text als gewöhnliches Ergebnis liest.

Damit hat die Abnahme zwei Texte statt einem:

| Lage | Beleg | Text |
|---|---|---|
| Server hat geantwortet und abgelehnt | seine Antwort | `write.executeRejected` — darf „es wurde nichts geändert" sagen |
| keine Antwort / Art unbekannt | — | `write.executeUnconfirmed` — „bitte nachsehen" |

Unbekannt zählt wie „keine Antwort": „abgelehnt" ist die stärkere Behauptung
und braucht einen Beleg.

**Nebenbefund derselben Familie.** `outcome_service.call_with_outcome` prüfte
nur „ist der Text leer?" und verbuchte damit jeden `"MCP error: …"` als
`status="success"`. Folgen: `adjust_confidence` **hob** die Zuversicht um 0.05
statt sie um 0.20 zu senken, und `derive_state_hint` schickte den Zug nach `S3`
(„Ergebnisse kuratieren"), obwohl es keine gab — beides genau dann, wenn etwas
schiefging. ⚠️ **Das ändert Tool-Loop-Telemetrie und rechtfertigt einen
Golden-Referenzlauf.**

**Punkt 2: der Qualitäts-Eintrag für früh endende Züge.** Tor und Aufruf wohnen
jetzt in `services/turn_quality.log_turn_quality`; `turn_persist` nutzt ihn
(verhaltensgleich), und der `preflight`-Knoten bucht **an einer Stelle** für
alle Züge, die dort enden. Die drei Direkt-Aktions-Handler haben zusammen zehn
Rückgabepunkte — den Aufruf dort einzeln zu verteilen hiesse, ihn beim elften zu
vergessen; der Verteiler dagegen sieht jede fertige Antwort.

Bewusst **nicht** gebucht: Tour-Takte und der Kontext-Gruss (kein Muster, keine
Frage beantwortet) sowie abgewiesene Züge (Drosselung, Sicherheits-Block) — die
führen bereits ein *Sicherheits*-Ereignis, und ein zweiter Datensatz daneben
machte die Zählung mehrdeutig.

## S6 — der Zwischenspeicher kannte den Aufrufer nicht (2026-08-15)

Beim Absichern der Cache-Sperre für S5 fiel der allgemeinere Fall auf. Er ist
**kein** Schreib-Thema und hätte auch ohne S5 bestanden.

**Gemessen, nicht angenommen.** Der MCP-Server sagt in seiner eigenen
Werkzeug-Beschreibung (`wlo_auth_status`), was er unterscheidet:

> `mode="anonymous"` = nur öffentliche Daten · `mode="service"` = ein
> Dienstkonto, dieselben Rechte für alle Nutzenden · `mode="user"` = die Rechte
> der angemeldeten Person

— und nennt als Einsatzzweck ausdrücklich „warum sie bestimmte Inhalte **(nicht)
sieht**". Live gegen den Server geprüft:

```
{"mode":"user","authenticated":true,"configuredAs":"janschachtschabel", …}
```

Der Server handelt also als **bestimmter Mensch**; was gelesen wird, hängt an
der Identität.

**Der Befund.** `_TOOL_CACHE` ist prozessweit, überlebt Sitzungen und fasst
1024 Einträge. Sein Schlüssel war `(tool_name, json(arguments))` — **ohne
Identität**. Zwei Personen mit derselben Suchanfrage teilten sich damit einen
Eintrag; die zweite bekam die Treffer der ersten, auch solche, die sie selbst
nie hätte sehen dürfen. Reproduziert als Test (rot vor dem Fix):

```
test_zwei_personen_teilen_sich_keinen_treffer
  → Person B bekommt den Treffer von Person A aus dem Zwischenspeicher
```

**Der Fix.** `auth.caller_fingerprint()` — SHA-256 des geltenden Blocks,
gekürzt — geht in den Schlüssel. Die drei Fälle fallen dabei genau richtig:

| Betriebsart | Kennzeichen | Topf | warum richtig |
|---|---|---|---|
| kein Block | `""` | einer für alle | alle sehen dasselbe Öffentliche |
| `MCP_AUTH_TOKEN` (Dienstkonto) | ein Wert | einer für alle | „dieselben Rechte für alle Nutzenden" |
| persönlicher Block | eigener Wert | eigener | eigene Rechte |

Zwei Entwurfsentscheidungen dabei:

1. **Ein Streuwert, nicht der Block.** Der Block verschlüsselt ein
   WLO-Passwort (`docs/AUTH.md` §1); als Klartext-Schlüssel läge er in einem
   prozessweiten Dict und damit in jedem Speicherauszug.
2. **`_cache_key` holt die Identität selbst**, statt sie sich reichen zu lassen.
   Ein Aufrufer, der sie vergisst, öffnet das Loch wieder — und die eine
   Produktions-Aufrufstelle soll gar nicht daran denken müssen.

Der Speicher bleibt dabei erhalten: dieselbe Person bekommt ihren Eintrag
wieder, anonyme Züge teilen sich weiter einen Topf. Gepinnt von sechs Tests in
`test_mcp_tool_cache.py`.

## S7 — der Anschlusssatz aus fremdem Text (2026-08-15, live gemessen)

**Der Anlass war eine Prüfung, keine Vermutung.** `extract_confirm_token` und
`preview_for_display` lesen **deutschen Servertext**; die Vorlage in den Tests
war am 10.08. abgeschrieben. Formuliert der Server um, findet die Extraktion
nichts — und dann lässt sich gar nichts mehr bestätigen. Die Testsuite kann das
nicht sehen: sie kappt die Leitung an der MCP-Naht.

Gemessen wurde deshalb am echten Server, mit dem einen Aufruf, der nichts
kostet: `wlo_create_collection` **ohne** `confirmToken` ist per Bauart reine
Vorschau. Die Antwort (Schlüssel hier durch `‹…›` ersetzt):

```
Bitte prüfen — bisher wurde nichts geändert:

Legt die Sammlung „Messprobe Abnahme 2026-08-15“ auf oberster Ebene an.
Titel: (leer) → „Messprobe Abnahme 2026-08-15“
Beschreibung: (leer) → „…“

Zum Anlegen bitte bestätigen. Dazu denselben Aufruf mit confirmToken: ‹…› wiederholen.
Der Schlüssel gilt einmalig und zehn Minuten lang.
```

**Befund 1 — die Muster tragen.** Der Anschlusssatz steht wortgleich da;
Extraktion, Schwärzung und Schnitt greifen alle. Die Prosa **davor** hat sich
gedreht („Zum Anlegen bitte bestätigen." statt „Die Sammlung wird angelegt.",
und das Änderungsformat ist jetzt `alt → neu`). Daran hängt nichts, deshalb
bleibt `_ECHTE_VORSCHAU` in den Tests als Stand vom 10.08. stehen — die neue
Form ist über `_VORSCHAU_MIT_FREMDEM_ANSCHLUSS` mit abgedeckt.

**Befund 2 — und der war nicht gesucht.** Der Server gibt Titel und
Beschreibung des Vorhabens **wörtlich** in die Vorschau. Zweite Probe, mit dem
Anschlusssatz in der Beschreibung: er steht danach **zweimal** im Text. Beide
Funktionen nahmen das *erste* Vorkommen — der Server hängt seinen Block aber
immer **hinten** an. Gemessen an diesem Text:

| | vor dem Fix | nach dem Fix |
|---|---|---|
| `extract_confirm_token` | der **fremde** Schlüssel | der des Servers |
| `preview_for_display` | 5 von 8 Zeilen sichtbar, mitten im Wert gekappt | 7 von 8, geschnitten am Block des Servers |

Zwei verschiedene Folgen, beide unerwünscht:

* **Sackgasse.** Die Abnahme setzt einen Schlüssel ab, den der Server nie
  geprägt hat → er lehnt ab → nichts passiert. Kein Loch (fälschen lässt sich
  ein Schlüssel damit nicht), aber fremder Text kann jeden Schreibvorgang an
  einem Knoten lahmlegen.
* **Zu wenig in der Box.** Der Mensch stimmt einem Vorhaben zu, dessen vollen
  Umfang er nicht gesehen hat — genau die Richtung, die der Docstring von
  `preview_for_display` bis dahin ausschloss („zu VIEL, nie zu wenig").

**Wer das auslösen kann.** Bei `wlo_create_collection` schreibt die
zustimmende Person den Wert selbst — dort ist es folgenlos. Die Grenze, die
zählt, ist `wlo_update_content`: die Vorschau zeigt die **alten** Werte des
Knotens, und die kann jemand anderes geschrieben haben. Das ist aus dem
gemessenen Format `alt → neu` gefolgert, nicht an einem Fremdknoten
nachgemessen; der Fix hängt nicht daran, denn er stellt nur die Zusicherung
her, die der Docstring ohnehin behauptet.

**Der Fix.** Eine Wurzel, zwei Stellen: am **letzten** Anschluss ansetzen.
`extract_confirm_token` nimmt `finditer(…)[-1]` statt `search(…)`;
`preview_for_display` schneidet mit `rfind` auf `_DISPLAY_TAIL_MARKER` statt mit
einem Regex, der von links greift. Das Token-Muster bleibt bewusst weit
(`confirmToken:` plus Schlüssel, ohne den Satz drumherum): enger wäre es an den
Wortlaut gekettet, und eine Umformulierung nähme uns die Extraktion ganz — der
Ausfall, vor dem der Modulkopf warnt. Drei Tests in `test_write_confirm.py`,
zwei davon rot vor dem Fix.

### Die Klasse abgesucht

Der Fund ist eine **Klasse**, keine Einzelstelle: *wir lesen Servertext, in den
fremder Text wörtlich eingeht, und greifen das falsche Vorkommen*. Drei weitere
Stellen geprüft — zwei entlastet, eine offen:

* **`parsers/cards.py::parse_total_count`** — liest den JSON-Umschlag zuerst und
  kehrt dort zurück; die Prosa-Muster laufen nur ohne Umschlag. Genau dieser
  Fall steht schon im Docstring (W2-1: „on an envelope whose card descriptions
  contain prose digits the regex scraped *those* instead"). **Kein Fund.**
* **`arg_resolvers.py:232`** — der Regex auf das *erste* `"nodeId"` greift nur,
  wenn `json.loads` scheitert. `search_wlo_collections` steht in
  `_JSON_CAPABLE_TOOLS`, `call_mcp_tool` setzt dort `outputFormat: "json"`
  zentral (`client.py:271`), und der Server antwortet live mit einem Umschlag
  (gemessen 2026-08-15). Toter v1-Rückfall. **Kein Fund.**
* **`services/agent_write.py::WriteGate`** — die **zweite** Naht, mit eigenem
  Merkposten und schärfer als die Chat-Naht: sie bestätigt im *selben Lauf*, ein
  falsch gemerkter Schlüssel geht also sofort hinaus. Sie ruft die Muster aus
  `write_confirm` auf und erbt den Fix — war aber nirgends gepinnt. Jetzt
  gepinnt (`test_agent_loop.py`, rot vor dem Fix mit `AAAA… ≠ aBcD…`).

Beim Pinnen fiel eine Sache auf, die wie ein Leck aussieht und keines ist: der
erfundene Schlüssel aus dem *Namen* steht sehr wohl in der Nachrichtenkette —
weil das **Modell ihn selbst getippt hat**, in seinen eigenen Aufruf-Argumenten.
Die Schwärzung kann die Worte des Modells nicht entfernen und soll es nicht: ein
selbst erfundener Schlüssel autorisiert nichts, und `strip_confirm_token` hält
ihn auf dem Hinweg aus jedem Aufruf heraus. Der Test sagt beides ausdrücklich,
damit niemand später das eine für das andere hält.

## Risiken

* **Doppelung.** Modell erzählt nach *und* Box zeigt → derselbe Inhalt zweimal.
  Gegenmittel: S4 (M18 auf Einordnen statt Wiedergeben umstellen). Bis der Seed
  importiert ist, bleibt die Doppelung bestehen — sichtbar, nicht falsch.
* **Länge.** Ein Kompendiumtext darf 100 000 Zeichen haben; der Server zeigt
  600 davon und sagt es. Die Box erbt diese Grenze, erfindet keine eigene.
* **Fremdtext in der Box.** Der Vorschautext enthält Werte aus dem Bestand.
  Er wird wie jedes Inline-Dokument über DOMPurify gerendert — kein neuer Pfad.
