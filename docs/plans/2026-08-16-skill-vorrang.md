# Plan: Skill-Vorrang vor den mitgelieferten Mustern

**Datum:** 2026-08-16 · **Auslöser:** Live-Befund in der Sammlung „Optik" (28 freigegebene
Skills): „ich will einen stundenentwurf zu optik erstellen" erzeugte einen Lernpfad aus der
Systemvorlage, ohne den redaktionell freigegebenen Skill „Stunde planen" zu laden.

---

## Ziel

Deckt ein an der Sammlung freigegebener Skill die Anfrage ab, arbeitet der Chatbot nach dessen
Anleitung statt nach seinem mitgelieferten Muster — und sagt das sichtbar.

## Kontext: was heute passiert

Gemessen am laufenden Backend (Protokoll 2026-08-16, 13:04–13:05):

```
13:04:34  get_skill_registry returned 34321 chars
13:04:34  page_context_enrich: Bestandsfakten geladen: 36 Materialien, 28 Skills
13:05:05  lp_fast_path: LP topic switch → fresh search for 'Optik'
13:05:05  search_wlo_collections + 3× get_collection_contents   … kein Skill-Werkzeug
```

Drei Tatsachen, alle am Quelltext bzw. am Protokoll belegt:

1. **Die Auslöserwörter kollidieren wörtlich mit den Skill-Stichworten.**
   `domain/lp_intent.py:43` führt `"stundenentwurf"`, `"unterrichtsstunde"`,
   `"unterrichtsplanung"`, `"unterrichtseinheit"`, `"unterrichtsvorbereitung"`.
   Die Registry der Sammlung nennt für **Stunde planen** das Stichwort
   „Stundenentwurf für die 8b", für **Unterrichtsreihe planen** „Unterrichtsvorhaben fürs
   Halbjahr", für **Unterrichtsentwurf begründen** „Ich muss einen Unterrichtsentwurf
   schreiben". Die Redaktion hat also bereits erklärt, wer zuständig ist.
2. **Der Lernpfad-Schnellweg ist bauartbedingt skill-blind.** `grep -c skill
   services/lp_fast_path.py` → 0. Er betritt die Werkzeugschleife nie, also kann dort kein
   `get_skill` fallen. Sein einziges Tor ist `fast_paths_on = engine != "agent"`
   (`graph/nodes/route.py:191`) — der Seitenkontext spielt keine Rolle.
3. **Die Anweisung existiert bereits, ist auf diesem Weg aber unerreichbar.**
   `services/page_context.py:459-492` baut den Block „### Freigegebene Anleitungen (Skills)
   dieser Sammlung — N" samt Aufforderung, über `get_skill_registry` → `get_skill` zu gehen.
   Dieser Block steht im **Antwort-Prompt**, den der Schnellweg nie baut.

**Der glückliche Umstand:** `page_context_enrich` läuft im Graphen **vor** `assess`, und
`classify_prompt.py` zieht bereits `page_context.render_for_prompt`. Der Klassifikator
**sieht die Skill-Liste heute schon** — er wird nur nicht danach gefragt.

---

## Richtigstellung 2026-08-16 (beim Umsetzen an der Quelle gemessen)

**Der Satz direkt darüber ist falsch, und mit ihm der ursprünglich gewählte Ansatz A.**
Beides geprüft in Schritt 0 der Phase 1, bevor eine Zeile Code entstand.

**1. Der Klassifikator sieht die Skill-Liste NICHT.** `classify_prompt.py:248-249` ruft
`render_for_prompt(…, include_stock=False)`. Genau dieser Schalter lässt den
Bestandsabschnitt — den Skill-Katalog — weg; `page_context.py:520-525` begründet es:
gemessene 2 232 Zeichen je Zug, und eine Änderung am Klassifikator-Prompt verlangt laut
Plan einen Golden-Lauf. Dieselbe Absicht steht ein zweites Mal in
`classify_prompt.py:262-273` — der Entities-Dump wurde gefiltert, *weil* der Skillkatalog
sonst als Roh-JSON mitfloss. Mein Fehler: ich hatte gesehen, dass `classify_prompt`
`render_for_prompt` zieht, und das Schlüsselwort-Argument nicht gelesen.

**2. Es gibt keine Node-IDs, die das Modell nennen könnte.** Die Bestandsfakten führen
`skills` (Anzahl) und `skill_titles` (Titel) — `context_facts.py:140`. Node-IDs fehlen
**absichtlich**: Nutzer-Vorgabe 2026-08-14 („nur die Übersicht … nicht mehr als eine A4
Seite"), nachgerechnet in `_skill_fakten` und `_bestands_zeilen`. Ein Feld
`skill_node_id` hätte das Modell also zum Erfinden aufgefordert — und der eigens
erdachte Halluzinations-Riegel hätte danach jeden Zug abgelehnt.

**Folge:** Ansatz A wäre nur zu retten, indem man **zwei dokumentierte Entscheide
zurückdreht** — den Klassifikator-Deckel und die A4-Zusage des Nutzers. Das ist nichts,
was man beim Bauen stillschweigend mitnimmt.

### Ansatz D (jetzt gewählt): der Entscheid bleibt beim Modell — dort, wo es die Skills sieht

Der **Antwort**-Prompt zeigt den Katalog bereits: `response_prompt_builder.py:119` ruft
`render_for_prompt` mit der Vorgabe `include_stock=True`, und der Block sagt seit W5-4
auch den Weg an (`get_skill_registry` → `get_skill`). Dort hat das Modell die Liste, die
Anleitung zum Zwei-Schritt und die Werkzeuge in der Hand. Es erreicht diesen Prompt nur
nicht — der Schnellweg kürzt vorher ab.

**Trägt die Seite freigegebene Anleitungen, treten die mitgelieferten Schnellwege
zurück.** Ein Schnellweg kann bauartbedingt keinen Skill lesen; der Nutzer-Entscheid
„Skills stehen über den mitgelieferten Mustern" gilt damit zuallererst ihm. Der Zug läuft
dann den gewöhnlichen Weg über Muster-Engine und Werkzeugschleife, und dort entscheidet
das Modell — angeleitet durch die Vorrang-Regel im Block.

Damit **entfällt** gegenüber A: das Feld im Klassifikations-Schema (Task 2), die Änderung
am Klassifikator-Prompt samt Golden-Lauf (Task 3) und `services/skill_loader.py` (Task 5)
— das Modell lädt den Skill über den Werkzeugweg, den es ohnehin hat (Rung 5 der
Entscheidungsleiter: vorhandener Code löst es). Es **kostet** keinen Zeichen-Zuschlag je
Zug; der Preis ist eng umrissen und steht unten unter „Bekannte Grenze".

Die vier Nutzer-Entscheide bleiben unverändert gültig — D erfüllt sie alle vier, nur an
einer anderen Stelle im Ablauf.

**Bekannte Grenze (bewusst in Kauf genommen):** Auf einer Seite mit Anleitungen kostet
ein Zug, der sonst den Schnellweg genommen hätte, jetzt eine Werkzeugschleife — auch
dann, wenn am Ende keine Anleitung passt. Enger geht es nicht, ohne vorab zu wissen, was
die Anleitungen abdecken; und genau dieses Vorwissen ist es, was Ansatz A teuer machte.
Zweite Folge: `detect_lp_intent` läuft dann nicht und seine beiden Nebenwirkungen
(Garbage-Thema-Reset, Muster-Degradation) bleiben aus — dieselbe Lage wie im
Agent-Modus, wo das Tor seit A4c ebenso schließt.

## Umfang

**In scope**

- Klassifikation entscheidet, ob ein Skill die Anfrage abdeckt (Nutzer-Entscheid: das Modell
  entscheidet, angeleitet durch eine ausdrückliche „Skill zuerst"-Regel im Prompt).
- Vorrang gegenüber **allen** mitgelieferten Mustern — Schnellwege *und* Musterwahl.
- Laden der Anleitung (`get_skill`) und Einspeisen in den Antwort-Prompt.
- Sichtbare Aktivierung: Vorspann-Zeile + Herkunftshinweis, über Studio pflegbar.
- Ausfallverhalten: Systemvorlage + offener Hinweis.

**Out of scope**

- Änderungen am MCP-Server (bleibt unberührt).
- Der Agent-Modus — er hat mit `agent_tools`/`agent_prefetch` eine eigene Skill-Verdrahtung.
- Die Markdown-Vorlage selbst: sie bleibt unverändert nutzbar (ausdrücklicher Nutzer-Wunsch).
- Der `max_items: 4`-Deckel aus dem Optik-Smoke — eigener Befund, eigenes Paket.

## Entscheidungen (Nutzer, 2026-08-16)

| Frage | Entscheid |
|---|---|
| Erkennung | **Modell entscheidet**, mit „Skill zuerst"-Regel im Prompt |
| Reichweite | **Alle mitgelieferten Muster** (Schnellwege + Musterwahl) |
| Anzeige | **Vorspann-Zeile + Herkunftshinweis**, Studio-pflegbar |
| Ausfall | **Systemvorlage + offener Hinweis** |

## Ansatz

Drei Ansätze standen zur Wahl, weil „das Modell entscheidet" einen Modell-Entscheid **vor**
dem Routing verlangt:

- **A — Entscheid im Klassifikator (gewählt).** `assess` läuft ohnehin, sieht den
  Seitenkontext bereits und liefert strukturiert. Ein zusätzliches Feld kostet **keinen**
  weiteren LLM-Aufruf und keine Latenz. Sein Ergebnis steuert schon heute das Routing.
- **B — eigener Vorab-Aufruf.** Ein kleiner LLM-Aufruf vor `route`. Klar getrennt, kostet
  aber einen Roundtrip pro Zug — bei einem Muster, das in jedem Zug greift.
- **C — Schnellweg-Tor hinter den Antwort-Prompt schieben.** Größter Umbau, verliert den
  Geschwindigkeitsvorteil der Schnellwege genau dort, wo er gedacht war.

**Gewählt: A.** Kleinste Änderung an der echten Entscheidungsstelle, keine Zusatzkosten,
und der Entscheid steht dort, wo die übrigen Routing-Entscheide schon stehen.

## Architektur

### Dateien

| Datei | Verantwortung |
|---|---|
| `domain/skill_precedence.py` **(neu, rein)** | Aus Klassifikation + Bestandsfakten den `SkillEntscheid` bilden: greift ein Skill, welcher, warum nicht. Framework-frei, testbar ohne LLM. |
| `services/classify.py` | Feld `skill_node_id` + `skill_title` im Schema; leer = kein Skill. |
| `services/classify_prompt.py` | „Skill zuerst"-Regel + Ausfüllanweisung für das neue Feld. |
| `graph/nodes/route.py:191` | `fast_paths_on` zusätzlich am `SkillEntscheid`; Musterwahl tritt zurück. |
| `services/skill_loader.py` **(neu)** | `get_skill` holen, Anleitung parsen, deckeln, Fehler als Ausfall melden. |
| `services/response_prompt_builder.py` | Anleitung als eigenen Prompt-Block einsetzen, mit Untrusted-Rahmen. |
| `i18n/bot_text.py` | Zwei Schlüssel: `skill.activated`, `skill.unavailable`. |
| `backend/seeds/…` | Muster-Texte um die Vorrangregel ergänzen (Wächter beachten). |

### Datenfluss

```
page_context_enrich   Registry → Bestandsfakten (Titel + Stichworte) in _page_metadata
        ↓
assess/classify       sieht den Skill-Block (schon heute) → füllt skill_node_id
        ↓
domain/skill_precedence   SkillEntscheid: greift / greift nicht / Grund
        ↓
route                 greift → fast_paths_on=False, Musterwahl tritt zurück
        ↓
skill_loader          get_skill(node_id) → Anleitung ODER Ausfall
        ↓
response_prompt_builder   Anleitung als Block; Vorspann-Zeile in die Antwort
```

### Schnittstellen

```python
# domain/skill_precedence.py
@dataclass(frozen=True)
class SkillEntscheid:
    greift: bool
    node_id: str          # "" wenn nicht
    titel: str            # "" wenn nicht
    grund: str            # für Debug/Quality-Event, nie für den Nutzer

def skill_entscheid(classification: dict, page_facts: dict) -> SkillEntscheid: ...

# services/skill_loader.py
@dataclass(frozen=True)
class SkillAnleitung:
    node_id: str
    titel: str
    text: str             # gedeckelt
    geladen: bool         # False = Ausfall → Systemvorlage + Hinweis

async def lade_skill(node_id: str, *, titel: str = "") -> SkillAnleitung: ...
```

### Abhängigkeitsrichtung

`domain/skill_precedence.py` bleibt framework-frei und importiert **nichts** aus `services`
— es bekommt Klassifikation und Fakten als einfache Dicts. Der MCP-Zugriff wohnt in
`services/skill_loader.py`. Damit zeigt die Kante nach innen, anders als bei
`domain/tool_result_redaction.py` (dort bewusst in Kauf genommen, siehe dessen Kopf).

## Querschnitt

- **i18n:** Beide neuen Texte über `bot_text` mit semantischen Schlüsseln, DE + EN, keine
  Zeichenketten im Code.
- **Untrusted:** Die Anleitung stammt aus dem WLO-Repository. Sie geht durch denselben
  Rahmen wie der Registry-Text (`domain/untrusted_text.frame_untrusted`) — kuratierter
  Inhalt, keine Systemanweisung.
- **Deckel:** Die Anleitung wird gedeckelt (Vorschlag 12.000 Zeichen, an
  `get_wlo_content_text`s 20.000er-Deckel orientiert, aber knapper, weil sie zum Prompt
  hinzukommt statt ihn zu ersetzen).
- **Dateigrößen:** Beide neuen Dateien bleiben unter 300 Zeilen; `route.py` wächst um
  ~10 Zeilen.
- **Observability:** Der `SkillEntscheid` landet in `DebugInfo` und im Quality-Event —
  damit ist „hat er den Skill benutzt?" künftig eine Systemtatsache statt einer
  Selbstauskunft des Modells (die im Befund unzuverlässig war).

## Risiken

| Risiko | Gegenmittel |
|---|---|
| Das Modell nennt einen Skill, der nicht in der Registry steht (Halluzination) | `skill_precedence` prüft die `node_id` gegen die Bestandsfakten; unbekannt ⇒ greift nicht |
| Skill-Vorrang greift zu oft und verlangsamt gewohnte Wege | Vorrang nur, wenn der Klassifikator eine ID nennt; Deckel + Zeitmessung im Quality-Event |
| Prompt wächst um die Anleitung | Deckel; Anleitung ersetzt in der Regel die Muster-Vorlage im Prompt, kommt nicht additiv dazu |
| Seed-Wächter schlägt an (Muster-Tool-Nennungen) | Task 8 passt Seed **und** Wächter gemeinsam an |

## Offene Fragen

Keine — die vier Produktentscheide sind gefallen.

---

# Aufgaben (Fassung D, 2026-08-16 — ersetzt die Fassung A darunter)

## Phase 1 — Vorrang (rein, ohne LLM testbar)

**Schritt 0: `/better-coding-workflow` laden.**

**Task 1 — `domain/skill_precedence.py`**
Neu, rein. `SkillEntscheid(greift, anzahl, grund)` + `skill_vorrang(fakten)`. Regeln:
keine/kaputte Fakten ⇒ `"keine-fakten"`; `skills` fehlt, ist keine Zahl oder 0 ⇒
`"keine-skills"`; sonst greift der Vorrang. Kein `services`-Import.
*Test zuerst:* `tests/test_skill_precedence.py` — leer, kaputt, ohne Skills, 0, 28.
*Prüfung:* `uv run --directory backend pytest tests/test_skill_precedence.py -q`.

**Task 2 — Tor in `route.py`**
`fast_paths_on = engine != "agent" and not vorrang.greift`; Fakten über
`page_context.get_cached(ss)["context_facts"]`. Ein `logger.info`, wenn der Vorrang greift.
*Test zuerst:* `tests/test_route_skill_vorrang.py` — mit „stundenentwurf" **und** 28 Skills
an der Seite läuft `detect_lp_intent` nicht und `run_lp_fast_path` bekommt
`has_lp_intent=False`; die Gegenrichtung (dieselbe Nachricht, **ohne** Skills) nimmt den
Schnellweg wie bisher. Das ist die Regressionsprüfung für den gemeldeten Fehler.

**Task 3 — Vorrang-Satz im Skill-Block**
`services/page_context._bestands_zeilen`: dem bestehenden Hinweis den Vorrang ausdrücklich
voranstellen — die freigegebenen Anleitungen gehen den mitgelieferten Vorlagen vor, und die
Nutzung ist anzusagen. Das ist die „Skill zuerst"-Anweisung aus dem Nutzer-Entscheid.
*Test zuerst:* Der Block nennt den Vorrang; der bestehende Zwei-Schritt-Wächter
(`test_der_block_nennt_den_weg_den_das_modell_auch_gehen_kann`) bleibt grün.

## Phase 2 — Sichtbarkeit (die Aktivierung als Systemtatsache)

**Schritt 0: `/better-coding-workflow` laden.**

**Task 4 — `get_skill` im Zug erkennen**
Am `tools_called` des Zuges ablesen, ob eine Anleitung wirklich geladen wurde. Das ist der
Nachweis, den die Selbstauskunft des Modells im Befund nicht liefern konnte.
*Test zuerst:* erkannt / nicht erkannt an einer Werkzeugliste.

**Task 5 — Zwei Bot-Texte**
`i18n/bot_text.py`: `skill.activated` und `skill.unavailable`, DE + EN.
*Test zuerst:* Beide Schlüssel in beiden Sprachen, Platzhalter vorhanden.

**Task 6 — Vorspann verdrahten**
Vorspann-Zeile voranstellen, wenn `get_skill` lief; lief der Vorrang, aber kein `get_skill`,
der offene Hinweis („Systemvorlage genutzt").
*Test zuerst:* Beide Wege am zusammengesetzten Antworttext.

## Phase 3 — Nachweis und Saat

**Schritt 0: `/better-coding-workflow` laden.**

**Task 7 — `SkillEntscheid` in `DebugInfo` + Quality-Event**
*Test zuerst:* Der Debug-Block trägt Vorrang und Grund.

**Task 8 — Seed + Wächter**
Muster-Texte um die Vorrangregel ergänzen; den Wächter aus W5-4a mitziehen.
*Prüfung:* volle Suite + `ruff` + `export_openapi.py --check`.

<details>
<summary>Fassung A (überholt — die Richtigstellung oben nennt den Grund)</summary>

Task 1 `skill_entscheid()` an `skill_node_id` · Task 2 Klassifikations-Schema ·
Task 3 „Skill zuerst" im Klassifikator-Prompt · Task 4 Tor an diesem Entscheid ·
Task 5 `services/skill_loader.py` · Task 6 Anleitung in den Antwort-Prompt ·
Task 7-9 wie Phase 2/3 oben. Tasks 2, 3 und 5 entfallen ersatzlos.

</details>

## Abnahme

Abnahme der **Fassung D**; die Zeilen zu `skill_loader` sind entfallen (das Modell
lädt die Anleitung über den Werkzeugweg, den es ohnehin hat).

| Kriterium | Prüfung | Erfolg | Stand |
|---|---|---|---|
| Der gemeldete Fehler ist weg | `test_route_skill_vorrang.py` | Schnellweg läuft nicht, obwohl `detect_lp_intent` „stundenentwurf" bejaht | ✅ Phase 1 |
| Wo nichts freigegeben ist, ändert sich nichts | Gegenrichtung im selben Test | Schnellweg läuft wie bisher | ✅ Phase 1 |
| Der Vorrang steht im Prompt | `test_page_context.py` | Block nennt Rang und Gleichstands-Fall | ✅ Phase 1 |
| Aktivierung sichtbar | Task-6-Test | Vorspann im Antworttext | Phase 2 |
| Ausfall ehrlich | Task-6-Test | Hinweis statt stiller Systemvorlage | Phase 2 |
| Nachweisbar statt Selbstauskunft | `DebugInfo` | `SkillEntscheid` im Debug-Block | Phase 3 |
| Keine Regression | `pytest -q` · `ruff` · `export_openapi.py --check` | grün, Vertrag unverändert | ✅ Phase 1 |
| Live | Ein Zug in der Optik-Sammlung | `get_skill` im Protokoll statt `lp_fast_path` | ⚠️ **teilweise** — siehe unten |

### Live-Messung 2026-08-16, 13:51 + 13:53 (Sammlung „Optik", zwei Züge)

Wörtlich die Nachricht aus dem Befund, danach der Anschlusszug „Reflexion, 8. Klasse".

```
13:51:38  route: Skill-Vorrang: 28 freigegebene Anleitungen … → Schnellwege treten zurück
          lp_fast_path: 0 Treffer im ganzen Protokoll        ← der Fehler ist weg
          Muster M09 (Lernpfad-Erstellung) + Werkzeugschleife statt Schnellweg
Zug 1     get_skill_registry ×2 (vom Modell selbst gewählt) → Rückfrage nach dem Teilbereich
Zug 2     get_skill_registry ×2, get_collection_contents, search_wlo_content ×2
          → belegte Antwort mit 4 Karten (statt Vorlagen-Lernpfad)
```

**Was erreicht ist:** Der Schnellweg kapert den Zug nicht mehr, das Modell erreicht den
Prompt mit dem Katalog, und es geht **Schritt 1** des Zwei-Schritt-Wegs von sich aus
(`get_skill_registry`, in beiden Zügen).

**Was fehlt:** `get_skill` — **Schritt 2 fällt nicht**. Das Modell liest die Registry
(32 855 Zeichen) und arbeitet dann ohne den Wortlaut der Anleitung weiter. Der Vorrang
ist damit hergestellt, die Nutzung noch nicht.

**Folge für Phase 2:** Sie ist mehr als eine Vorspann-Zeile. Der zweite Schritt muss
erzwungen oder deterministisch gemacht werden. Die Messung dazu ist unten.

### Messung 2026-08-16 zum ausbleibenden zweiten Schritt

Vier Größen, alle über den MCP-Client der App bzw. am Seed gemessen:

| Gemessen | Ergebnis |
|---|---|
| `get_skill_registry` (markdown, so ruft der Bot) | **32 855 Zeichen** |
| dieselbe Antwort als JSON | 34 321 = 16 717 Markdown **+** 17 379 `entries` — dieselben 28 Skills **zweimal** |
| `get_skill` „Stunde planen" | **14 290 Zeichen** — also 2,3× kleiner als der Katalog davor |
| `get_skill` in M09s Werkzeugliste? | **ja**, `seeds/03-patterns/m09-lernpfad-erstellung.md:20` |

**Damit sind drei Erklärungen ausgeschlossen.** Das Werkzeug fehlt nicht. Die `nodeId`
fehlt nicht — das Modell hatte sie nach dem Registry-Aufruf. Und die Anweisung fehlt nicht:
Sie steht **dreifach** — im Seitenblock („geh die zwei Stufen weiter … arbeite danach,
statt den Ablauf selbst zu erfinden"), in der Beschreibung von `get_skill_registry` („die
Anleitung selbst kommt NICHT mit") und in der von `get_skill` („der zweite Schritt nach
get_skill_registry").

**Was bleibt:** Die Registry liefert je Eintrag eine Beschreibung, die wie ein
ausreichender Auftrag liest — für „Stunde planen" etwa „tabellarischer Verlaufsplan mit
Phasen, Minuten, Sozialform und Material je Phase". Nach 32 855 Zeichen Katalog hat das
Modell etwas in der Hand, das sich vollständig anfühlt, und der Grenznutzen eines weiteren
Aufrufs sieht klein aus. Eine **vierte** Prompt-Formulierung ist nach drei erfolglosen die
falsche Antwort (Drei-Schlag-Regel).

### Nebenbefund, der zwei geplante Aufgaben streicht

`get_skill` liefert die Aktivierungszeile **selbst mit** — als erste Zeile des Textes,
ausdrücklich servererzeugt:

```
## Aktivierung
Gib diese Zeile — vom Server erzeugt, nicht aus dem Dokument — wörtlich als erste
Zeile deiner nächsten Antwort aus:

[ edu-sharing Skill ] Stunde planen - aktiv
```

Das ist genau die geforderte Anzeige („der muss die aktivierung anzeigen"). **Task 5 und 6
der Fassung D entfallen deshalb**: eigene `i18n`-Schlüssel plus Vorspann-Verdrahtung wären
eine zweite, konkurrierende Anzeige — und die schlechtere. Die servererzeugte Zeile ist ein
**Beleg** (sie existiert nur, wenn `get_skill` wirklich lief); eine selbstgebaute Zeile
wäre eine **Behauptung**. Bleibt Task 6 nur als Ausfall-Hinweis, wenn der Vorrang griff und
trotzdem keine Anleitung geladen wurde.

### Umgesetzt: Nachfassen am Werkzeug-Ergebnis (Nutzer-Entscheid 2026-08-16)

Gewählt wurde die Nachfass-Zeile: Liefert `get_skill_registry` einen Katalog **mit**
Einträgen, hängt `skill_registry.\_nachfassen` unter das Werkzeug-Ergebnis, dass die Liste
nicht die Anleitung ist und `get_skill` der zweite Schritt bleibt. Untergebracht im
bestehenden Modul, das genau diese Aufgabe schon hat (`_anstoss` für den Schwester-Fall) —
kein neuer Mechanismus.

**Live gemessen, fünf Züge mit derselben Nachricht:**

| Lauf | Wortlaut | `get_skill` | geladen |
|---|---|---|---|
| 3 | ohne Feldangabe | 2× | Katalog (Fehlgriff) **+ „Stunde planen" 14 290 Z. ✔** |
| 4 | mit Feldangabe | – | – |
| 5 | mit Feldangabe | 1× | 100 Z. — ID in keiner Registry ✗ |
| 6 | mit Feldangabe | 1× | 67 Z. — `nodeId='???'` ✗ |
| 7 | mit Feldangabe | – | – |

Davor, ohne jede Nachfass-Zeile: 2 Züge, 0 Aufrufe.

**Zwei Schlüsse, beide unbequem.** Erstens: die Zeile bewegt etwas — aus 0/2 wurden
Aufrufe. Zweitens: **sie trägt nicht.** In fünf Zügen wurde die Anleitung genau **einmal**
wirklich geladen. Und die Verschärfung („Feld `entries[].nodeId`, nicht `registryNodeId`"),
die einen beobachteten Fehlgriff beheben sollte, machte es schlimmer: das Modell erfand
danach IDs. Sie ist zurückgenommen; der Zwischenstand steht als Kommentar im Test, damit
niemand denselben Anlauf wiederholt.

**Damit ist Variante A ausgereizt.** Zwei Anläufe derselben Art sind erfolglos geblieben
(Drei-Schlag-Regel). Wer Verlässlichkeit will, braucht **Variante B — deterministisches
Laden**: greift der Vorrang, gleicht das Backend die Anfrage gegen die Registry-Stichworte
ab und legt den Wortlaut selbst in den Prompt. Die Nachfass-Zeile bleibt dabei sinnvoll als
Weg für die Fälle ohne Stichwort-Treffer.

---

## Die eigentliche Wurzel — gefunden 2026-08-16 beim Prüfen der Mustertexte

Variante B war nicht nötig. Der Nutzer-Verdacht („zwingen die Mustertexte zur Vorlage?")
führte auf einen **Code-Fehler**, und alles Vorherige erklärt sich daraus.

```
get_skill_registry („Optik")     32 855 Zeichen
_ROH_DECKEL (blindes Abschneiden) 4 000     ← das Modell sah 12 %
„Stunde planen" beginnt bei      13 091     ← weit dahinter
```

**Das Modell hat die IDs nie gesehen.** Es bekam einen Katalog-Anfang mit sieben IDs
fremder Skills, in dem der gesuchte Eintrag nicht vorkam. Daher jede Beobachtung dieses
Tages: das Ausbleiben des Aufrufs, die erfundenen IDs (`e6bcb2e0…`, `7f2c8b94…`), das
wörtliche `'???'`, die 67–100-Zeichen-Fehlerantworten. Keine Modell-Laune — ein
abgeschnittener Werkzeugtext.

Der Kommentar am Deckel sagte es vorweg: *„Wo die Antwortform bekannt ist, wird sie
strukturell gekürzt statt abgeschnitten."* Für diese Form war sie bekannt und wurde
trotzdem abgeschnitten.

**Behoben** in `domain/tool_result_redaction._redigiere_skill_registry`: aus dem Katalog
wird eine Auswahlliste — je Eintrag `nodeId — Titel — Zweck`, alle 28, gedeckelte
Beschreibungen, ohne das doppelte `markdown`-Feld. Beide Antwortformen werden gelesen
(JSON und die vorgabegemäße Markdown-Form). Gemessen: **32 855 → 7 297 Zeichen, alle 28
IDs sichtbar, „Stunde planen" darunter.**

**Live danach, fünf Züge, dieselbe Nachricht:**

| | vorher | nachher |
|---|---|---|
| `get_skill` gerufen | 3 von 5 | **5 von 5** |
| mit gültiger nodeId | 1 von 5 | **5 von 5** (`5b29f470…`, je 14 290 Z.) |
| Aktivierungszeile sichtbar | 1× | 2× wörtlich, 5× skill-geführte Rückfragen |

Die beiden Änderungen davor bleiben sinnvoll und wurden nicht zurückgenommen: der
Vorrang in `route.py` bringt den Zug überhaupt erst in die Werkzeugschleife, die
Nachfass-Zeile und der Muster-Schritt 0 sagen dort, was zu tun ist. Sie waren nur nicht
hinreichend, solange der Katalog abgeschnitten ankam.

**Offen:** Ein Zug von fünf endete mit „Ich konnte leider keine Antwort generieren."
(ohne Fehlermarke im Protokoll) — eigener Befund, noch nicht untersucht.

## Zweite Wurzel — die Sammlung kam nie an (Testlauf 2026-08-16)

Der Nutzer-Testlauf „erst zu Optik suchen, dann Stunde planen" fiel durch: gefunden wurde
`Geometrische Optik`, **nicht** die Sammlung `9e7ae956-…` („Optik") — und nur an ihr hängen
die Skills. Mein erster Bericht („Zug 1 bestanden") war falsch: ich hatte geprüft, *ob* eine
Sammlung kommt, nicht *welche*.

Der Server war sauber. `search_wlo_all("Optik")` legt Sammlungen **mit** Themenseite in den
`topicPages`-Topf — dort steht „Optik" auf Platz 1, mit und ohne `discipline`-Filter.

Gemessen an der echten Antwort, Töpfe einzeln durch die Karten-Weiche:

```
content      results=10  →  10 Karten
collections  results= 2  →   2 Karten
topicPages   results= 2  →   0 Karten     ← 69 599 Zeichen, nichts kam an
```

**Ursache:** Der Prefetch zerlegt das `search_wlo_all`-Envelope (`graph/nodes/respond.py`
:196-201) und etikettiert den `topicPages`-Topf mit `search_wlo_topic_pages`. Damit ging er
in `parse_wlo_topic_page_cards`, der `collectionId` + `variants` erwartet — der Topf trägt
aber `nodeId` + `topicPageUrl`. `if not cid: continue` verwarf jeden Eintrag.

Die Falle stand seit dem 01.08. wörtlich im Haus, in `parsers/cards.py`:280-286 — „der
dedizierte Themenseiten-Parser gehört deshalb NICHT hierher (er würde jeden Eintrag
verwerfen, weil `collectionId` fehlt)". Genau dorthin schickte ihn die Etikettierung.

**Behoben** in `services/card_collect.parse_cards_for_tool`: unter diesem Werkzeugnamen
kommen zwei Antwortformen an, deshalb entscheidet jetzt die **Form**, nicht allein der Name.
Ein leeres Ergebnis kostet nichts — bei wirklich leerem Topf geben beide Parser `[]`.

**Folge fürs Produktivsystem:** Dort ist das Reranking aus, und ohne Reranker kürzt
`card_reranker`:143-150 nur auf Top-N, ohne zu bewerten (MCP-Reihenfolge bleibt). Der
Parser-Fehler war produktiv damit die **ganze** Ursache.

### Reranker-Pfad: Namensgleichheit und Schwelle (Nutzer-Vorgabe 2026-08-16)

Mit Reranker fiel „Optik" ein zweites Mal heraus — nicht am Parser, am Tor:

```
+0.52  Geometrische Optik   klarer Treffer
-0.27  Optik                die GESUCHTE Sammlung   ← Tor stand auf 0.0
-2.46  off-topic            das Rauschen, gegen das 0.0 gebaut war
```

Kuratierte Sammlungen tragen oft eine leere `description`; der CE urteilt dann über Titel +
Stichworte und landet knapp negativ, ohne off-topic zu sein. Zwei Änderungen in
`services/card_reranker.py`:

* `CARD_CE_GATE_COLLECTION` 0.0 → **-1.0** (trennt Treffer von Rauschen, bleibt strenger als
  das Inhalts-Tor -1.5; die Regression vom 2026-06-02 greift weiter, Wächter-Test dazu).
* **`CARD_CE_EXACT_BONUS` (2.0)** auf Treffer, deren Titel GENAU dem Suchbegriff entspricht
  (normalisiert: Groß/Klein und Leerraum egal, bewusst keine Teilstring-Suche). Der Zuschlag
  geht in dieselbe Zahl, die das Tor prüft — der gleichnamige Treffer steht damit vorn UND
  überlebt.

Live danach, `search_wlo_all("Optik")` mit Reranker:
`topic_pages 2→2 (gate=-1.0) scores=[1.71, -0.27]`, `collections 2→1 (dropped=1, -2.46)`.
„Optik" ist Karte 2 der Antwort. Ohne Reranker: Karte 3, LLM-Auswahl setzt sie auf Platz 1.

### Dritte Wurzel: der Vorrang hing allein am Seitenkontext — behoben

Zug 2 griff auch nach den beiden Karten-Fixes nicht auf den Skill zu: M09, Werkzeug
`generate_learning_path`, kein `get_skill`, Antwort aus der Vorlage. Grund: `skill_vorrang`
las nur die Bestandsfakten des **Seitenkontexts**. Wer über die Suche kommt, steht auf
keiner Sammlungsseite — dort war die Vorrang-Regel wirkungslos, obwohl der Treffer die
Anleitungen längst meldete (`skill_count = 28` auf der Karte, Paket #194).

**Behoben** mit einer zweiten Quelle, in vier kleinen Schritten:

| Was | Wo |
|---|---|
| `merke_skill_sammlung(entities, karten)` — Notiz `_skill_bestand` (rein) | `domain/skill_precedence.py` |
| `skill_vorrang(fakten, entities)` — Seite hat Vorfahrt, Gespräch ist der Rückfall | dieselbe |
| Notiz schreiben, sobald die Karten stehen | `graph/nodes/assemble.py` |
| Zweite Quelle am Tor lesen + Quelle protokollieren | `graph/nodes/route.py` |

Die Notiz reist in `session_state['entities']['_skill_bestand']` — die `_`-Konvention, die
`turn_persist` ohnehin als JSONB schreibt, also weder Spalte noch Migration (dieselbe
Begründung wie bei `domain/turn_frame`). Gemerkt wird die **reichste** Sammlung des Zuges;
sie **bleibt** stehen, bis eine neue sie überschreibt (`simplify:` — kein Verfall gebaut;
der Preis ist ein Zug über die Werkzeugschleife statt über den Schnellweg, langsamer statt
falsch).

**Live, beide Züge, beide Lagen:**

```
Skill-Vorrang (gespraech): 28 freigegebene Anleitungen → Schnellwege treten zurück
Werkzeuge: lookup_wlo_vocabulary ×2 · get_skill_registry ×2 · get_skill ·
           get_node_details ×3 · search_wlo_content
Antwort:   „⸠ stunde-planen aktiv — Verlaufsplan für 45 oder 90 Minuten"
Dokument:  # Stundenentwurf: Geradlinige Lichtausbreitung
           Lernziele · Bleibender Kern · Stundenbogen · Verlaufsplan (Tabelle) ·
           Tafelbild/Merksatz · Ergebnissicherung · Sollbruchstelle · Nachbereitung
```

Das ist **nicht** die M09-Vorlage (die schreibt „# Lernpfad: <Thema>" mit nummerierten
Schritten und „## Quellen/Lizenz" vor). Begriffe wie „Sollbruchstelle" und „Look-for"
stehen ausschliesslich im Skill-Text. Mit Reranker fragt das Modell stattdessen die im
Skill angebotene Dauer nach („45 oder 90 Minuten?") — ebenfalls skill-konform, mit
Aktivierungszeile.

### Der Titel der Dokument-Box: neutral (Nutzer-Entscheid 2026-08-16)

Die Box hiess **„Lernpfad: Optik"**, obwohl ein Stundenentwurf darin stand — der M09-Zweig
in `domain/inline_rendering._inline_doc_title_for_pattern` setzte das Label vor das Thema.

Entschieden wurde der neutrale Titel: **nur das Thema**, also „Optik". Er ist in beiden
Fällen wahr — Lernpfad wie Stundenentwurf — und braucht keinen Skill-Marker durch die
Schichten. Die ART der Box geht nicht verloren: das Widget zeichnet sein Symbol aus
`kind` (`inline-documents.component.ts`:37) und hält für den titellosen Fall ein eigenes
Label bereit; das Wort im Titel war Doppelung. Nebeneffekt: ein blosses Thema braucht kein
Label und damit keine Übersetzung.

Der `**Lernpfad: …**`-Kopf der Systemvorlage gewinnt weiterhin, wenn das Dokument ihn
selbst trägt — geändert wurde nur der Rückfall. Vier Test-Pins zogen mit
(`test_title_m09_topic_fallback_when_no_bold` und die drei Geschwister, je mit Begründung).

### Review-Befunde (2026-08-16, behoben)

Ein Review über die Änderungen dieser Sitzung fand drei Punkte:

**1 [MAJOR] Die Themenseite war da, aber am falschen Platz.** Die Karten aus dem
`topicPages`-Topf trugen `node_type='collection'` ohne Varianten — damit erkannte
`_is_themenseite_card` (`domain/cards/build`:211) sie nicht. Sie landeten im
Sammlungs-Kasten und teilten sich dessen Deckel (3), während der Themenseiten-Kasten leer
blieb; bei einer vierten Sammlung wäre die gesuchte wieder herausgefallen. Der Mangel steckte
**nicht nur** im neuen Fallback, sondern ebenso im direkten `search_wlo_all`-Pfad — dieselbe
Fehlerklasse an zwei Aufrufstellen (gemessen an der echten Optik-Antwort: beide Wege
`_is_themenseite_card → False`).

Behoben mit einem gemeinsamen Schritt `_als_themenseiten_karten`
(`parsers/cards.py`), angewandt in `parse_search_all_cards` und im Fallback von
`card_collect.parse_cards_for_tool`. Er erzeugt die Form des dedizierten Parsers:
`node_type='topic_page'` plus EINE Variante; fehlt `topicPageUrl`, wird sie aus der
Knoten-ID abgeleitet. `wlo_url` bleibt unangetastet — es zeigt auf das konfigurierte
Repositorium (#195), `topicPageUrl` kommt roh vom MCP und wird von
`_normalize_card_repo_hosts` nicht erfasst.

Live danach, beide Lagen: `[topic_page] Optik` und `[topic_page] Wellenoptik` im
Themenseiten-Kasten, die Sammlungen daneben — **7 Karten statt 6**, weil die Budgets nicht
mehr konkurrieren.

**2 [MINOR] Doppelter Kartenfeld-Leser.** `skill_precedence._feld` war eine Kopie von
`domain/cards/build._feld`. Meine Kopie ist gelöscht; das Modul nutzt die vorhandene. Der
`domain->schema`-Import ist im Ziel-Modul ausdrücklich ausgewiesen, der Docstring-Satz
„Framework-frei (nur stdlib)" entsprechend richtiggestellt.

**3 [MINOR] Die Mitte der Kette war ungetestet.** Reine Entscheidung und Leser hatten
Tests, der Aufruf in `graph/nodes/assemble` nicht — wer ihn entfernt, sieht eine grüne Suite
und einen stillschweigend kaputten Anwendungsfall. Zwei Tests in `test_assemble_node.py`
schliessen die Lücke (Notiz wird geschrieben / bleibt aus).

### Beobachtung: die Ausgabe schwankt, der Weg nicht

Drei Live-Läufe desselben Zuges, alle mit greifendem Vorrang und gerufenem `get_skill`:

| Lauf | Ergebnis |
|---|---|
| ohne Reranker | voller Verlaufsplan im Skill-Format, mit Aktivierungszeile |
| mit Reranker | skill-eigene Rückfrage „45 oder 90 Minuten?", mit Aktivierungszeile |
| ohne Reranker (2.) | nur ein Vorspann, 260 Zeichen, ohne Aktivierungszeile |

Der **Mechanismus** ist stabil (3/3 Vorrang + `get_skill`), die **Ausführung** schwankt.
`/api/health` meldet `verbosity: low` und `reasoning_effort: low` — eine Anleitung, die
einen vollen Verlaufsplan samt Tabelle vorgibt, hat darunter wenig Raum. Nächster
Ansatzpunkt, falls die dünnen Läufe stören: diese beiden Knöpfe, nicht der Code.

---

### Zwei gemeldete Befunde, nachgemessen 2026-08-16 abends

Beide stammten aus meinen eigenen Nachstellungen, nicht aus dem Nutzer-Test.
Nachgemessen mit dem Payload, den das Widget wirklich schickt.

**Befund 1 „erster Zug auf einer Seite hat keine Bestandszahlen" — widerlegt,
mein Messfehler.** Meine Sonde `pk-01` schickte `page_context` mit
`collection_id`, aber **ohne** `page_kind`. `page_context_enrich._bestand_anhaengen`
prüft in Zeile 109 auf `page_kind ∈ {collection, topic}` und steigt sonst sofort
aus; `_decide_host_kind` konnte ihn nicht nachtragen, weil auch `page_host`
fehlte (`classify_page_host(None, …)` gibt `""` zurück). Der echte Detektor
(`frontend/…/page-context-detector.ts:116,138`) setzt ihn immer. Mit
realistischem Payload trägt schon der erste Zug:

```
21:02:29  Bestandsfakten geladen: 36 Materialien, 28 Skills
21:02:31  Skill-Vorrang (seite): 28 freigegebene Anleitungen → Schnellwege treten zurück
21:02:41  MCP tool get_skill args: {'nodeId': '5b29f470-…'}        ← „Stunde planen"
          Antwort: M09, inline_documents[0] kind=lernpfad titel='Optik' 4674 Zeichen
```

Kein Code geändert. Die Lehre ist die Sonde: eine Nachstellung, die ein Feld
weglässt, das die echte Oberfläche immer mitschickt, misst den eigenen Aufbau.

**Befund 2 „der Skill wird nicht zuverlässig gezogen" — echte Lücke, behoben.**
Der Skill-Hinweis entsteht in `page_context._bestands_zeilen`, und der hängt an
`meta["context_facts"]`. Über die **Suche** gibt es keine Seiten-Metadaten →
`render_for_prompt` liefert `""` → im Prompt stand über Anleitungen **nichts**.
Der Vorrang griff zwar seit heute Mittag aus der Gesprächs-Notiz
(`_skill_bestand`, Quelle `gespraech`), aber danach stand das Modell vor einer
Aufgabe ohne Weg: es kannte weder die Anleitungen noch die `collectionId`, mit
der `get_skill_registry` (Stufe 2 der Muster M08/M09/M10/M18/M19) beginnt. Die
Notiz führt `{anzahl, titel, node_id}` — gelesen hat sie nur das Routing.

Neu: `skill_precedence.anleitungs_hinweis(fakten, entities)` rendert daraus den
Block „## Freigegebene Anleitungen (Skills)" mit Zahl, Titel, Sammlungs-ID und
beiden Stufen. Wortlaut bewusst wie im Seitenblock — eine Sache, eine Stimme.

* **Auf der Seite schweigt er** (`quelle == QUELLE_SEITE`): dort steht der volle
  Katalog schon im Seitenblock; zwei Hinweise wären zwei Stimmen im selben Prompt.
* **Ohne `node_id` schweigt er ganz**: ein Weg, dessen erster Schritt kein
  Argument hat, ist schlechter als kein Weg.
* Der fremde Titel wird einzeilig gemacht und auf `MAX_TITEL_ZEICHEN` gekappt —
  gerahmt wird er nicht (Hausregel `domain/untrusted_text`: nur Langform-Prosa),
  aber er darf keine eigene Überschrift in den Block schreiben.

Verdrahtet in **beiden** Engines (Nutzer-Vorgabe 2026-08-14 „pattern und agent
loop"): `response_prompt_builder` P3c und `respond_agent` nach dem Seitenblock.
In P3c wird `get_cached` nicht ein zweites Mal gerufen — der Wert von P3 wird
wiederverwendet, sonst liefe der Aufruf ausserhalb der Absicherung und
`test_page_context_block_failure_is_swallowed` fiele (ist beim Bauen passiert).

Live, Sucheinstieg ohne jeden Seitenkontext, Reranker aus wie in Produktion:

```
Zug 1  „Suche mir Sammlungen zum Thema Optik"      M06
       Karten: 9e7ae956 Optik (0) · bf729405 Wellenoptik (0)
               f35c17d1 Geometrische Optik (28)  ← reichste, wird gemerkt
       Die ID steht NICHT im Antworttext (geprüft) — der Verlauf trägt sie nicht.

Zug 2  „Erstelle mir bitte einen Stundenentwurf zu Optik"
       Skill-Vorrang (gespraech): 28 → Schnellwege treten zurück
       get_skill_registry  collectionId=f35c17d1-…   ← nur aus dem neuen Block
       get_skill           nodeId=5b29f470-…         ← „Stunde planen"
       → die Anleitung stellt ihre Rückfrage (45/90 min, Phase)

Zug 3  „Optik, Klasse 8, 45 Minuten, Einführung"
       Skill-Vorrang (gespraech) · get_skill 5b29f470 DIREKT (ohne Registry)
       Lead 172 Zeichen · Kachel kind=lernpfad titel='Optik' 3266 Zeichen
```

Zug 3 belegt nebenbei die Notiz `_skill_lauf` vom selben Tag: die knappe
Stichwort-Antwort führt dieselbe Anleitung fort, statt neu zu wählen.

Tore: `pytest -q` 3680 passed / 1 failed (`test_auth::test_http_matrix_on_studio_route`,
vorbestehend) / 4 skipped · `ruff check .` All checks passed · `export_openapi.py
--check` unchanged.

**Nebenher, nicht Teil der Änderung:** `uv` zog ruff 0.15.21, in der `UP038`
nicht mehr Preview ist. Drei Bestandszeilen (`skill_precedence:139`,
`card_reranker:99`, `rag/retrieval:100`) wurden dadurch rot und auf `X | Y`
gestellt — dieselbe Quelle war heute Vormittag mit demselben Befehl grün.

### Offen: die Rückfrage der Anleitung landet in der Material-Kachel

In Zug 2 oben war `content` **leer** (0 Zeichen) und die Rückfrage der Anleitung
(„45 oder 90 Minuten? … Einführung, Durcharbeitung, Übung oder Anwendung?")
stand als `inline_documents[0] kind=lernpfad titel='Optik'` mit 222 Zeichen in
der Kachel. Der Skill verhält sich richtig — er fragt, bevor er baut. Falsch ist
die Aufteilung: eine Rückfrage ist kein Lernpfad, und eine leere Sprechblase ist
in keinem Fall die Absicht. Erwartet wäre die Frage in der Blase und gar keine
Kachel.

Vermuteter Ort: die Lead/Body-Trennung von M09 (`domain/inline_rendering` +
`services/turn_assembly`) nimmt alles ab dem ersten Absatz als Body, auch wenn
gar kein H1 und kein Verlaufsplan da ist. **Nicht angefasst** — eigener Schnitt,
eigener Befund, wartet auf Zuruf.

### Behoben: die Rückfrage der Anleitung landet in der Sprechblase

Ursache, und sie stand als Kommentar da: [`_split_lead_and_body`] teilt am ersten
ATX-Kopf, und **ohne Kopf gibt es alles als Body zurück** — „damit die Box
gefüllt ist und die Bubble leer". Diese Zusage stammt aus einer Zeit, in der
M09/M10/M11 immer ein Dokument lieferten. Seit eine freigegebene Anleitung ihr
eigenes Format vorgeben darf, antwortet sie auch mal mit einer *Rückfrage* — und
die stand dann als `lernpfad`-Kachel „Optik" da, während die Blase leer blieb.

**Kriterium ist die Struktur, nicht die Länge.** `turn_persist:477` deckelt
bereits bei 200 Zeichen und griff nicht (die Rückfrage hatte 222). Ein langer
Hinweistext ohne Dokument wäre weiter durchgerutscht. Alle drei Kachel-Muster
schreiben dagegen ausdrücklich eine Überschrift vor:

* M09 „Zuerst 1-Satz-Bubble-Lead **VOR dem H1** … Dann ab H1 das Markdown"
* M10 dieselbe Formel, und jeder Materialtyp beginnt mit H1
* M11 „der KOMPLETTE editierte Markdown **ab H1** bis zum letzten Abschnitt"

Fehlt sie ganz, hat das Modell kein Dokument geliefert, sondern Prosa.

Umgesetzt in `domain/inline_rendering`:

* `_ATX_UEBERSCHRIFT` als Konstante — zwei Stellen brauchen den Ausdruck, und
  jede wertet ihn anders aus (Position vs. Ob). Zwei Kopien driften.
* `_hat_ueberschrift()` — das Ob.
* `_build_inline_document` steigt ohne Überschrift vor dem Split aus und gibt
  `([], markdown)` zurück. **Nicht** in `_split_lead_and_body`: dort ist „keine
  Überschrift" von „Überschrift in Zeile 1" nicht zu unterscheiden (beide geben
  `("", md)`), und ihre Zusage ist ALT-verbatim gepinnt.

Beide Aufrufer (`turn_persist:506`, `direct_actions:580`) prüfen `if _docs:` und
lassen den Text sonst stehen — die leere Liste führt also von selbst dorthin,
wo der Text hingehört.

Live, Seitenkontext `9e7ae956`, Reranker aus:

```
Zug 1  „Erstelle mir einen Stundenentwurf"      M09 · get_skill_registry, get_skill
       Blase 243 Zeichen:
         ▸ stunde-planen aktiv — Verlaufsplan für 45 oder 90 Minuten
         Für welchen Zeitrahmen … **45 oder 90 Minuten** …
       Kacheln: 0                                   ← vorher: Blase 0, Kachel 222
Zug 2  „45 Minuten, Einführung in die Optik, Klasse 8"
       Blase 224 Zeichen (Lead) · Kachel kind=lernpfad titel='Optik' 3956 Zeichen
```

Tore: `pytest -q` 3685 passed / 1 failed (`test_auth`, vorbestehend) / 4 skipped
(+5 neue Tests) · `ruff check .` All checks passed.

**Nicht angefasst, beim Nachstellen aufgefallen:** ein Sucheinstieg mit dem Wort
„Sammlungen" liefert manchmal gar keine Sammlungskarte. Der Klassifikator liest
`medientyp='Sammlung'`, und `response_tool_selection` nimmt daraufhin
`search_wlo_all`, `search_wlo_collections` und `search_wlo_topic_pages` aus der
Werkzeugliste, „um eine Inhaltssuche zu erzwingen" — gemessen 21:48:25. Ohne
Sammlungskarte gibt es keine Notiz und damit keinen Skill-Vorrang. Derselbe Satz
lief eine halbe Stunde vorher über `search_wlo_all` durch; die Ableitung
schwankt also. Eigener Befund, eigener Schnitt.

**Ebenfalls offen:** `inline_rendering.py` ist mit 585 Zeilen deutlich über der
300er-Marke (vorher 544). Ein Split bräuchte einen eigenen Durchgang — das Modul
ist ein ausgewiesener ALT-Wortlaut-Port, und seine Herkunft ist Teil seiner
Zusage.

---

### „Sammlung" ist kein Medientyp — an ZWEI Stellen (behoben)

Der Befund vom Vortag: „Suche mir Sammlungen zum Thema Optik" ergab
`medientyp='Sammlung'`, und danach kam keine Sammlungskarte mehr an. Beim Fixen
zeigte sich, dass dieselbe falsche Annahme zweimal steckt — die erste Korrektur
schob den Ausfall nur eine Stufe weiter:

```
22:18:15  (nach Korrektur 1) search_wlo_all lief wieder
22:18:23  select_top_cards: 2 IDs picked — Die beiden gefundenen Sammlungen …
22:18:25  universal type-filter: 3 → 0 cards (medientyp=['sammlung'])   ← Stufe 2
```

1. **Werkzeugwahl** (`response_tool_selection:236`): bei gesetztem Medientyp
   fliegen `search_wlo_all`, `search_wlo_collections` und
   `search_wlo_topic_pages` raus, „weil sich Sammlungen nicht nach
   `resourceType` filtern lassen". Die Begründung trägt nur für INHALTS-Typen.
2. **Kartenfilter** (`content_types._resolve_wanted_content_types:157`): der
   Rohwort-Rückfall macht aus jedem unbekannten Medientyp ein Filterwort, gegen
   das `_card_matches_wanted_types` die `learning_resource_types` hält — und
   dort steht „sammlung" nie.

Eine Regel für beide: `content_types.medientyp_meint_sammlungen()` über
`_SAMMLUNGS_MEDIENTYPEN` (`sammlung|sammlungen|themenseite|themenseiten`). Ein
Test hält fest, dass sich die beiden Kataloge nicht überschneiden — stünde
„sammlung" in `_CONTENT_TYPE_KEYWORDS`, wäre die neue Regel ein Widerspruch
statt einer Ergänzung.

**Live nachgestellt, aber nicht ausgelöst:** im Wiederholungslauf leitete der
Klassifikator gar kein `medientyp` mehr ab (`medientyp = None`, 7 Karten,
darunter `f35c17d1 Geometrische Optik skill_count=28`). Die Ableitung schwankt;
der Auslöser liess sich nicht auf Kommando erzeugen. Belegt sind daher: der
Vorher-Zustand (gemessen, beide Stufen) und beide Korrekturen als Unit-Tests.

### Die harte Ladezeile im Chat (Nutzer-Vorgabe)

Bis hierher kam die Aktivierungs-Ansage aus dem `get_skill`-Ergebnis. Der
MCP-Server schreibt dort — nach eigener Auskunft im Text — einen Abschnitt:

```
## Aktivierung
Gib diese Zeile — vom Server erzeugt, nicht aus dem Dokument — wörtlich als
erste Zeile deiner nächsten Antwort aus:

[ edu-sharing Skill ] Stunde planen - aktiv
```

Gemessen hielt sich das Modell nicht daran: einmal
`▸ stunde-planen aktiv — Verlaufsplan für 45 oder 90 Minuten`, einmal
`[ edu-sharing Skill ] Stunde planen - aktiv`. Eine Ansage, die das Modell
umformuliert, ist eine Behauptung.

Neu, hartcodiert und damit ein Beleg:

* `skill_registry.skill_titel()` liest den Titel aus der H1 der ERSTEN Zeile
  (`get_skill` antwortet mit Markdown, nicht mit JSON — gemessen). Nur die erste
  Zeile: ein `#` weiter unten ist eine Abschnittsüberschrift, und ein geratener
  Titel wäre schlechter als keiner.
* `merke_laufende_anleitung(…, titel=…)` nimmt ihn in die bestehende Notiz.
* `skill_precedence.mit_ladehinweis()` stellt die Zeile voran — **nur im
  ladenden Zug**. Die Notiz gilt zwei Züge (damit die Rückfrage fortgeführt
  wird), die Ansage einen: geladen wurde einmal.
* Verdrahtet in beiden Engines (`respond.py:446`, `respond_agent.py:220`),
  jeweils direkt nach `append_answer_notes`.

Live, Sucheinstieg, Reranker aus:

```
Zug 3  M09 · get_skill_registry → get_skill (nodeId 5b29f470)
       Skill-Vorrang (gespraech): 28 freigegebene Anleitungen
       Erste Zeile der Antwort:
         [ edu-sharing Skill ] Stunde planen - wird geladen
```

Tore: `pytest -q` 3716 passed / 1 failed (`test_auth`, vorbestehend) / 4 skipped
(+31 Tests) · `ruff check .` All checks passed · openapi contract unchanged.

### Offen: die „aktiviert"-Gegenzeile über den MCP

Die Nutzer-Vorgabe verlangt zusätzlich, die Aktivierungsinfos aus den Skills zu
nehmen und eine gleichlautende `- aktiviert` als Info über den MCP abzusetzen,
damit die Ladekette nachvollziehbar wird: `wird geladen` bei uns, `aktiviert`
auf der Gegenseite.

**Nutzer-Entscheid 2026-08-16:** „die aktiviert zeile macht nicht der chatbot
direkt — die kommt als anweisung vom mcp tool." Also bleibt sie, wo sie ist: der
MCP-Server sendet sie weiter als Anweisung, und wir erzeugen sie NICHT.

Damit ist die Kette arbeitsteilig, und genau das war der Zweck:

* `- wird geladen` — von UNS, hartcodiert im Moment des Aufrufs. Sie existiert
  nur, wenn `get_skill` wirklich lief, und ihr Wortlaut steht fest.
* `- aktiviert` — von der GEGENSEITE, über die Anweisung im Werkzeug-Ergebnis.
  Sie existiert nur, wenn das Modell die Anleitung auch gelesen hat.

Zwei Quellen, zwei Belege. Eine selbstgebaute zweite Zeile wäre nur eine zweite
Behauptung derselben Seite gewesen.

**Offen und ausserhalb dieses Repos:** die Umstellung des Wortlauts von `- aktiv`
auf `- aktiviert` im MCP-Server. Bis dahin steht dort die alte Fassung.

---

### Korrektur: zwei Registries, nicht eine vererbte

Ich hatte gemessen, dass ``get_skill_registry`` für „Optik" (9e7ae956) und
„Geometrische Optik" (f35c17d1) je 28 Einträge liefert, und daraus auf
**Vererbung** geschlossen. Das war falsch — ich hatte nur die ersten vier
Einträge verglichen und das falsche Feld gelesen (``title`` statt
``registryTitle``). Der MCP-Entwickler wies darauf hin; nachgemessen:

| | Optik (9e7ae956) | Geometrische Optik (f35c17d1) |
|---|---|---|
| ``registryTitle`` | „Skillkatalog Physik Optik" | „Skill Registry" |
| ``registryNodeId`` | d84d54c4-… | 247da7a9-… |
| Einträge | 28 | 28 — dieselben Titel |

**Zwei eigene Registry-Dokumente**, deren Inhalte sich heute vollständig decken.
Das ist Überschneidung, nicht Vererbung: derselbe Skill darf in beiden stehen,
und morgen führt einer einen, den der andere nicht hat.

**Nutzer-Entscheid:** „dann wäre es richtig das beides kommt". Umgesetzt:

* ``merke_skill_sammlung`` merkt jetzt **alle** Sammlungen eines Zuges mit
  Skills, nach Anzahl sortiert, gedeckelt bei :data:`MAX_BESTAND_SAMMLUNGEN`
  (3, die Hausgrösse). Vorher gewann die reichste — bei Gleichstand entschied
  die Fundreihenfolge, und der zweite Katalog war unerreichbar.
* Die Notiz ist damit eine **Liste**. ``_bestand_liste`` liest auch die alte
  Einzelform: die Notiz reist als ``jsonb`` durch die Sitzung, und ein Zug von
  vorher soll seinen Vorrang nicht verlieren.
* ``skill_vorrang`` nimmt die grösste Zahl, ``anleitungs_hinweis`` nennt **jede**
  Sammlung mit Titel, ID und Anzahl.

### „Skill" statt „Anleitung" (Nutzer-Vorgabe)

Alle 16 ausgegebenen Stellen umgestellt — Chat-Text (``i18n/bot_text``),
Prompt-Blöcke (Seitenblock, P3b, P3c, Systemprompt beider Engines),
Werkzeug-Notizen (``skill_registry``, ``tool_result_redaction``) und die
Protokollzeile in ``route``. Mit Grammatik: aus „die Anleitung … arbeite nach
ihr" wird „der Skill … arbeite nach ihm".

**Nicht umgestellt:** Funktions- und Testnamen (``anleitungs_hinweis``,
``laufende_anleitung``, ``merke_laufende_anleitung``) sowie die Docstrings.
Das ist ein mechanischer Umbenenn-Durchgang über ~40 Stellen und gehört nicht in
diese Änderung; die Namen sind intern und stehen nirgends vor einem Nutzer.

Tore: ``pytest -q`` 3723 passed / 1 failed (``test_auth``, vorbestehend) /
4 skipped · ``ruff check .`` All checks passed · openapi contract unchanged.
