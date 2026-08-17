# Die Ergebnis-Box als Werkzeug statt als Vermutung

**Befund des Nutzers (2026-08-17):** „Die generierte Stundenplanung wird erzeugt,
aber landet nicht in der Box. Prinzipiell sollte die Anzahl der Schritte keine
Rolle spielen — es kann ja durch Rückfragen zu Zwischenschritten kommen. Es
braucht eine saubere Möglichkeit, die Box-Ergebnisse strukturiert auszugeben,
und die entsprechende Anweisung dazu."

Betrifft **beide** Maschinen. Live gemessen (Muster-Modus, Sammlung
`9e7ae956-…`, Skill „Stunde planen" `5b29f470-…`):

| Zug | Muster | Antwort | Box |
|---|---|---|---|
| 1 „Plane eine Stunde zur Optik" | M03 | 98 Z. Rückfrage | – |
| 2 „45 Minuten, Einführung" | M09 | **318 Z. Zusammenfassung** | **keine** |
| 3 „Gib mir jetzt den vollständigen Verlaufsplan" | M11 | 129 Z. Vorspann | 8.059 Z. ✓ |

## 1. Warum es heute bricht

`turn_persist.py:474` entscheidet über die Box **aus dem Antworttext**:

```python
_winner_id in {"M09", "M10", "M11"} and _final_text and len(_final_text.strip()) >= 200
```

danach sucht `inline_rendering._build_inline_document` ein H1 und trennt daran
Vorspann von Rumpf. Vier Bedingungen müssen zusammentreffen — Muster, Text,
Länge, Überschrift. In Zug 2 stimmte nur das Muster.

**Die Box ist damit eine Vermutung über den Text, keine Zusage.** Sie hängt an
drei Dingen, die das Modell frei wählt (wie lang, mit welcher Überschrift, in
welchem Zug), und an einem, das der Klassifikator rät (welches Muster). Genau
deshalb spielt die Schrittzahl heute eine Rolle, obwohl sie es nicht dürfte.

## 2. Der saubere Weg: ein Werkzeug, das das Dokument liefert

Dieselbe Mechanik, die `submit_result` und (seit H2/H3) `waehle_vorgehen` schon
benutzen — ein **virtuelles Werkzeug**, am Namen abgefangen, bevor irgendein
MCP-Aufruf passiert:

```
zeige_dokument(titel: str, art: enum, markdown: str)
  → Ergebnis an das Modell: „Dokument übernommen."
  → Nebenwirkung: die Box dieses Zuges steht fest
```

Was das löst:

| Heute | Mit dem Werkzeug |
|---|---|
| Box nur bei M09/M10/M11 | Box, wenn das Modell eine liefert — in **jedem** Muster und **jedem** Zug |
| ≥200 Zeichen nötig | Länge ist gleichgültig |
| H1 im Text nötig | Titel kommt als Argument |
| Vorspann/Rumpf per Regex getrennt | sauber getrennt: `content` = Vorspann, `markdown` = Box |
| Zwischenschritte zerstören die Box | Rückfragen sind folgenlos — geliefert wird, wenn fertig |

**Die Anweisung gehört an das Werkzeug**, nicht in den Fließtext eines Musters:
seine `description` sagt, wann es zu rufen ist („sobald du ein Arbeitsergebnis
erzeugt hast — Verlaufsplan, Arbeitsblatt, Lernpfad, Bericht"), und die
`art`-Aufzählung nennt die zulässigen Formen. Ein Muster- oder Skill-Text kann
sie verstärken, muss es aber nicht — genau das macht sie unabhängig von der
Redaktion.

## 3. Schnitt

| Paket | Inhalt |
|---|---|
| **D1** | **Neu `domain/inline_documents.py`** (rein): `ZEIGE_DOKUMENT`, `dokument_werkzeug()`, `dokument_aus_argumenten(args)` mit Prüfung (Titel/Markdown nicht leer, `art` aus der Erlaubnisliste, Längendeckel). Keine I/O. |
| **D2** | Dispatch in `agent_loop.py` neben `waehle_vorgehen`; `AgentRun.dokumente`; `respond_agent` reicht sie an `ctx`. Gilt für `agent` **und** `hybrid`. |
| **D3** | Dispatch in `tool_loop.py` neben `select_top_cards` (dort sitzen die virtuellen Werkzeuge des Bestandswegs) + Aufnahme in `response_tool_selection`. Damit ist der Muster-Modus mit repariert. |
| **D4** | `turn_persist`: **geliefertes Dokument schlägt die Vermutung.** Die Heuristik bleibt als Rückfall stehen — ruft das Modell das Werkzeug nicht, ändert sich nichts am heutigen Verhalten. |
| **D5** | Wächter: ein Test, der belegt, dass ein Zug mit `zeige_dokument` eine Box bekommt, **ohne** dass Muster, Länge oder H1 stimmen. Das ist die Zusage, um die es geht. |

## 4. Bewusst additiv

D4 ist der Kern der Rückbau-Sicherheit: ohne Werkzeug-Aufruf greift die alte
Heuristik unverändert. Die 20 Muster, die Seeds und das Studio bleiben
unangetastet; `display_rules.inline_documents.per_pattern` behält seine Wirkung
für den Rückfall-Weg.

## 4a. Umgesetzt (2026-08-17): D1, D2, D4, D5

**Entscheide des Nutzers:** die fünf Bestandsformen plus `stundenplanung`,
`unterrichtsreihe`, `zeugnis`, `dokument` (Brief), `kompendialtext`. Eine Box
muss gehen, mehrere sind die Option → `MAX_DOKUMENTE_JE_ZUG = 3`.

**Kein Frontend-Zwang** — gemessen statt vermutet: die Box zeigt
`doc.title || fallbackLabel(doc.kind)`, und `fallbackLabel` hat einen
`default`-Zweig („Inhalt"), das Icon ebenso
(`ui/src/inline-doc/inline-doc.ts:45`). Unbekannte Arten rendern sauber mit dem
gelieferten Titel. Eigene Etiketten je neuer Art wären Kür und kosteten einen
Widget-Neubau.

| Paket | Stand |
|---|---|
| D1 `domain/inline_documents.py` (176 Z., rein) | ✅ 10 Tests |
| D2 Dispatch in `agent_loop` + `AgentRun.dokumente` + `respond_agent` → `ctx` | ✅ 5 Tests |
| D4 `turn_persist`: Lieferung schlägt Vermutung, Heuristik als Rückfall | ✅ 3 Tests |
| D5 Wächter „Box ohne passendes Muster, ohne 200 Zeichen, ohne H1" | ✅ Teil von D4 |
| D3 Dispatch im `tool_loop` + Angebot in `response_tool_selection` | ✅ 8 Tests (§4b) |

**Verifikation.** `pytest -q` → 3778 passed, 1 failed (`test_auth`,
vorbestehend), 4 skipped · `ruff check .` → All checks passed · `export_openapi
--check` → unchanged.

Live, genau der gemeldete Fall, mit Zwischenschritt (`hybrid`):

| Zug | Muster | Box |
|---|---|---|
| 1 „Plane eine Stunde zur Optik" | M09 | – (Rückfrage) |
| 2 „45 Minuten, Einführung" | **HYBRID** | ✅ `stundenplanung`, „Stundenplanung: Einführung in die Optik", **4.395 Zeichen**, `meta.source = tool` |

Der zweite Zug ist der Beleg: das Muster war **HYBRID**, nicht M09/M10/M11 — der
geratene Weg hätte die Box verworfen. Der Begleitsatz in der Blase blieb bei 139
Zeichen, wie die Werkzeugbeschreibung es verlangt.

**Ein Fund beim Bauen, der fast durchgerutscht wäre:** ein zu breiter
Textersatz hängte `gelieferte_dokumente=` an **alle drei** Aufrufe in
`persist.py` statt nur an `persist_and_build_response` — die Suite blieb grün
(die anderen beiden Pfade laufen dort nicht), erst der Live-Zug warf
`TypeError: build_debug_and_update_session() got an unexpected keyword
argument`. Ein Beleg dafür, dass die Live-Probe die Suite nicht ersetzt und
umgekehrt.

## 4b. D3 und der Review-Durchlauf (2026-08-17, nachmittags)

Ein `/better-coding-review` gegen den Auftrag ergab **Spec compliance: FAIL** —
aus einem Grund: `mode: pattern` ist die Vorgabe (`seeds/01-base/engine.yaml`),
und `zeige_dokument` fehlte dort. Der gemeldete Befund bestand für jede Anlage
fort, die die Maschine nicht umstellt. Zehn Befunde, alle behoben:

| # | Befund | Behebung |
|---|---|---|
| 1 (MAJOR) | Musterweg rät weiter | `zeige_dokument` in `response_tool_selection` (dritte dokumentierte Abweichung des Byte-Parität-Ports) + Dispatch in `tool_loop` |
| 2 | `inline_documents.enabled: false` galt nur für den geratenen Weg | `_boxen_erlaubt()`; bei „aus" wandert das Markdown in den Fließtext statt zu verschwinden |
| 3 | Ersatzsatz „zu umfangreich" über einer fertigen Box | `agent.delivered` — ein Lauf mit Lieferung ist nicht gescheitert |
| 4 | Titel bekam den Kürzungs-Hinweis des Rumpfes (`\n\n*(gekuerzt…)*`) | eigener glatter Schnitt; die Box interpoliert den Titel, sie rendert ihn nicht |
| 5 | Titel im Server-Log — bei `art: zeugnis` ein Personenname | Art und Länge bleiben, der Titel fällt raus (beide Schleifen) |
| 6 | Test baute den Doppel-Ausgabe-Fall und prüfte nur die Hälfte | `resp.content` mitgepinnt: der Fließtext bleibt unangetastet — kürzen hieße raten |
| 7 | Müllkarten-Schutz für Schleifen-Läufe ganz aus | **nicht nachgebaut** (Begründung unten), stattdessen im Protokoll sichtbar gemacht |
| 8 | `include_dokument` ohne Docstring-Absatz | ergänzt |
| 9 | Test sicherte eine Konstante zu (`MAX_DOKUMENTE_JE_ZUG >= 2`) | gelöscht; der Deckel ist dort gepinnt, wo er greift |
| 10 | §5 stellte Fragen, die §4a beantwortet | dieser Abschnitt |

**Der Transportweg im Musterweg** ist `session_state`, nicht das 4-Tupel des
Loops: dessen Rückgabe zu verbreitern träfe jede Attrappe, und der Loop hat für
virtuelle Werkzeuge längst eine Konvention (`_selected_card_ids`,
`_write_preview`). `graph/nodes/persist` holt den Merker mit `pop` ab — dort
laufen beide Zuflüsse zu **einer** Naht zusammen.

**Eine Vorrunde statt eines Zweigs:** `respond_to_user` verlässt die Runde mit
`break`. Stünde die finale Antwort vor dem Dokument in derselben Runde, ginge
ein fertiges Ergebnis verloren — wieder eine Abhängigkeit von der Laune des
Modells. Die Vorrunde nimmt sie heraus.

**Live im Muster-Modus** (`mode: pattern`, Vorgabe, 2026-08-17):

| Zug | Muster | Weg | Box |
|---|---|---|---|
| „Welche Materialien zur Optik für Klasse 8?" | M06 | Schleife, 6 Werkzeuge | – (7 Karten) |
| „Bau mir daraus einen Verlaufsplan für 45 Minuten" | M09 | Schleife, `get_skill` ausgeführt | **–** (328 Z. Zusammenfassung) |
| „Gib mir jetzt den vollständigen Verlaufsplan" | M11 | Schleife | ✅ `stundenplanung`, **7.347 Zeichen**, `meta.source = tool`, Begleitsatz 146 Z. |

Der dritte Zug ist der Beleg: das Modell ruft `zeige_dokument`, die Box trägt
`source: tool` (nicht die geratene Herkunft), und `tools_called` bleibt leer —
das Werkzeug geht richtigerweise nie an den MCP.

**Der zweite Zug ist der ehrlichere Befund.** Er reproduziert den gemeldeten
Fall wörtlich („\[edu-sharing Skill\] Stunde planen – wird geladen" + eine
Zusammenfassung) — aber hier fehlt die Box nicht am Transport, sondern am
Inhalt: das Modell hat den Plan gar nicht erst erzeugt. Das Werkzeug lag bereit
(unbedingtes Anhängen, keine Degradation — sieben Werkzeuge liefen). Was
diesem Zug fehlt, ist eine Anweisung im Muster- oder Skill-Text, das Ergebnis
im selben Zug zu LIEFERN statt es anzukündigen. Das ist Redaktionsarbeit im
Studio, keine Code-Änderung — und jetzt erstmals sauber trennbar, weil der
Transportweg nicht mehr als Ursache in Frage kommt.

**Zwei Schnellwege liegen vor der Schleife:** „Plane eine Stunde zur Optik"
läuft in den M09-LP-Schnellweg, „Schreibe einen Elternbrief" in den
M10-Canvas-Schnellweg. Beide erzeugen ihre Box deterministisch und sind von
diesem Umbau unberührt — gemessen, nicht vermutet.

**Zu Befund 7, ausdrücklich nicht gebaut:** der Filter schließt von „kein Slot"
auf „die Suche lief ohne Thema". In der Schleife gibt es dafür kein Gegenstück
— `search_wlo_content` verlangt ohnehin eine nichtleere `query`, ein Wächter
„hat das Modell einen Suchbegriff übergeben?" wäre also praktisch immer wahr
und kostete Verdrahtung durch vier Dateien. Ein echter Ersatz hieße, die
Modell-Anfrage nachzuklassifizieren — eine neue Funktion, keine Behebung.
Stattdessen protokolliert `turn_assembly` jetzt, **wenn** die Ausnahme Karten
rettet, die der Filter verworfen hätte. Damit ist der Handel zählbar und beim
nächsten Golden-Lauf zu bewerten, statt unsichtbar zu bleiben.

## 5. Offen — gehört dem Nutzer

* **Eigene Etiketten und Icons je neuer `art`** (`inlineDocFallbackLabel` /
  `inlineDocIcon`, `ui/src/inline-doc/inline-doc.ts`). Kür: unbekannte Arten
  rendern sauber mit dem gelieferten Titel und dem Standard-Icon. Kostete einen
  Widget-Neubau.
* **Der A/B-Golden-Lauf über die drei Maschinen** — er entscheidet, ob der
  Hybrid schneller ist und wie oft die Karten-Ausnahme aus Befund 7 zuschlägt.
* Commit, Docker-Build, Deploy, Seed-Import.
