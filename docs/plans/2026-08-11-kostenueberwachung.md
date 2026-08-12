# Kostenüberwachung — Token je Sitzung und Zeitraum, als Grundlage für die Abrechnung

**Stand 2026-08-11 — Messung fertig, Entwurf beschlossen, Bau NICHT begonnen.**
Dieses Dokument ist so geschrieben, dass eine frische Sitzung ohne Vorwissen
damit bauen kann. Alles, was gemessen wurde, steht hier; nichts muss geraten
werden.

---

## 0. Wiedereinstieg — was eine frische Sitzung wissen muss

**Arbeitsverzeichnis:** `C:\Users\jan\staging\Windsurf\wlo-suche\boerdi-chat`

**Rahmen, der immer gilt (nicht verhandelbar):**

* `../badboerdi/`, `../wlo-mcp-server/` und `Windsurf/wlo-mcp-server-sc/` sind
  **nur Referenz — niemals ändern.**
* Secrets liegen in `backend/.env` (gitignored) und in den OS-Variablen
  `B_API_KEY_STAGING` / `B_API_KEY_PROD` — **nie ausgeben, nie loggen.**
* **Commits und Deploys macht der Nutzer selbst.** Eval-, Golden- und
  Lasttest-Läufe startet der Nutzer. Kleine Chat-Smokes sind erlaubt.
* Seed-Änderungen wirken **erst nach einem Seed-Import** (die Config lebt in
  der Datenbank, nicht in der Datei).
* Eiserne Regeln: kein veränderlicher Modul-Zustand, ≤300 Zeilen je Datei,
  deutsch = Inhalt / englisch = Bezeichner, DSGVO: keine externen Fonts/Dienste.
* Lizenz-Gate: nur MIT / Apache-2.0 / BSD / PSF / PostgreSQL.
* **`boerdi-chat` ist KEIN git-Repository** — `git diff` funktioniert nicht.

**Vorgehen:** Jedes Paket beginnt mit `/better-coding-workflow`; K5 zusätzlich
mit `/better-coding-frontend`. Test zuerst, rot sehen, dann bauen.

**Gates (aus `backend/`):**

```bash
OTEL_TRACES_EXPORTER=none uv run pytest -q
```
```bash
uv run ruff check src/boerdi tests/
```
```bash
uv run python scripts/export_openapi.py --check
```

Ausgangsstand vor diesem Plan: **pytest 2905 passed / 4 skipped**, ruff sauber,
OpenAPI unverändert, `ng test ui` 701, `playwright` 46.

---

## 1. Ziel

Wer die Anlage betreibt, soll beantworten können: *Was hat diese Sitzung
gekostet, was der letzte Monat, und wie verteilt es sich auf Eingabe, Cache,
Ausgabe und Reasoning?* Grundlage für eine Abrechnung, nicht nur ein Gefühl.

## 2. Messung (2026-08-11, am Code und gegen das installierte LiteLLM)

### 2.1 Was schon trägt — und was nur so aussah

> ⚠ **Korrektur vom 2026-08-11, gefunden beim Bau von K1a.** Die Überschrift
> hieß hier „mehr als vermutet". Das war falsch, und zwar auf eine Art, die
> diesen Plan im Kern betraf: **der Merkposten wurde nie angelegt.** Siehe M0
> in 2.2. Ich hatte die *Mechanik* gelesen (fünf Nodes reichen `ctx.usage`
> durch, `turn_persist` schreibt es ins JSONB) und daraus geschlossen, dass sie
> auch *läuft*. Gelesene Mechanik ist kein Beleg für einen Ablauf — dieselbe
> Lehre wie „eine Zählung ist kein Befund", nur eine Ebene höher.

`obs/usage.py` sammelt je Zug einen Merkposten mit **prompt / completion /
cached / calls**, aufgeschlüsselt **je Modell** und **je Phase** (classify,
tool_loop, response, …). Er wird durch die LLM-Aufrufe gefädelt, landet in
`DebugInfo.token_usage` (`services/turn_persist.py:177`) und wird
**bedingungslos** in `messages.debug` (JSONB) gespeichert — für jede
Bot-Nachricht. Das Widget-Debug-Panel zeigt ihn je Zug an
(`frontend/projects/ui/src/debug/debug-panel.component.ts:254`), zeigte aber
bis zum Fix nichts an: seine Bedingung ist `token_usage['calls']`, und die
stand immer auf 0.

Zwei Dinge sind gegen die **Wirklichkeit** geprüft, nicht gegen die Attrappe:

* **`extract_usage` greift.** LiteLLMs `Usage` ist ein Objekt, `getattr`
  funktioniert. Gemessen mit den echten Typen aus dem installierten Paket:
  `{'prompt': 100, 'completion': 20, 'cached': 64}`. Das ist **kein** dritter
  Fall der dict-statt-Objekt-Falle aus dem P11-Probelauf.
* **Der Streaming-Pfad bucht mit.** `_stream_completion` fordert
  `stream_options.include_usage` an und hängt die Schluss-Usage an die
  rekonstruierte Antwort; `tool_loop.py:588-596` bucht **nach beiden** Zweigen.
  Eine erste Grep-Zählung sah hier eine Lücke — sie war keine.
  **Merke: eine Zählung ist kein Befund.**

### 2.2 Was fehlt

| # | Befund | Folge |
|---|---|---|
| **M0** | **Der Merkposten wurde nie angelegt.** `TurnContext.usage` stand auf `{}` (`graph/state.py:94`), und **kein einziger Erzeuger** rief `new_accumulator()` — ALT tut es in `chat_turn_setup.py:175`, der Port hat die Zeile verloren. `add_usage` kehrt bei falsy `acc` still zurück (`obs/usage.py:54`), also war **jede** der fünf Durchreichungen (assess/route/respond/assemble/persist) ein No-Op. | `debug.token_usage` war in **jeder** Bot-Nachricht `{}`. Nicht „zu niedrig" — **null**. Die Grundlage, auf der M1–M4 aufsetzen, existierte nicht. ✅ **Behoben** (K1-0). |
| **M1** | **Fünf Produktivmodule buchen nicht** (Details in 2.3). | Arbeitsblätter und Lernpfade sind **große** Aufrufe. Jede Kostenzahl aus heutigen Daten ist systematisch zu niedrig — und sieht korrekt aus. |
| **M2** | **Reasoning-Token werden nicht gelesen.** LiteLLM liefert `completion_tokens_details.reasoning_tokens` (gemessen: 8), `extract_usage` nimmt nur `cached_tokens`. | Bei Reasoning-Modellen der teuerste Posten, komplett unsichtbar. |
| **M3** | **Keine Aggregation.** Kein Endpunkt, keine Ansicht für „je Sitzung" oder „je Zeitraum". | Die Zahlen liegen je Nachricht im JSONB; auswertbar nur von Hand. |
| **M4** | **Keine Preise.** Nichts im Backend. Das Studio-„Kosten-Band" der Eval (`eval-generative-start.component.ts:141`) zählt **Aufrufe**, kein Geld. | Ohne Preis keine Abrechnung. |
| **M5** | **Embeddings buchen nicht** (`services/llm.py:201`, gibt nur den Vektor zurück). | Bewusst außerhalb dieses Plans (Nutzer-Entscheid), hier nur festgehalten. |

### 2.3 Die fünf ungebuchten Stellen — je mit ihrer Kette

Das ist die Kernmessung für K1. **Sie sind nicht gleich schwer.**

| Modul | Aufruf | Wo ist der Merkposten? | Aufwand |
|---|---|---|---|
| `services/llm_learning_path.py:136` | `generate_learning_path_text` | **Schon da:** `lp_fast_path.run_lp_fast_path` hat `usage_acc: dict` (Z. 95) und ruft den Generator in Z. 374 **ohne** ihn. | trivial — Parameter anfügen, durchreichen |
| `services/llm_curation.py:68` | `generate_curation_text` | `direct_actions.py` ruft ihn; `direct_actions` führt **kein** `usage_acc`. Kette: preflight-Knoten (`ctx.usage` vorhanden) → `direct_actions` → Generator. | klein — ein Hop |
| `services/canvas_service.py:318` | `generate_canvas_content` | `canvas_fast_path.run_canvas_create_fast_path` (Z. 104) hat **kein** `usage_acc`; Aufrufer ist `graph/nodes/route.py`, wo `ctx.usage` vorliegt (Z. 215 reicht es bereits an `run_lp_fast_path`). | klein — ein Hop |
| `services/safety/legal.py:53` | `classify_legal` | `safety/service.py:230` ruft ihn im `gather`; der Dienst führt kein `usage_acc`. Aufrufer ist der assess-Knoten, dort liegt `ctx.usage` (vgl. `assess.py:88`). | klein — zwei Hops |
| `services/mcp/arg_resolvers.py:476` | `_llm_vocab_match` (Z. 417) | **Der schwierige Fall.** Modul-Helfer mit Prozess-Cache (`_cache_vocab`), erreicht über `TOOL_PREPROCESSORS` → `mcp/client.py`. Dort gibt es **keinen Zug-Kontext**, und ein Treffer im Cache macht gar keinen Aufruf. | siehe K1e — eigene Entscheidung |

> ⚠ **Korrektur beim Bau (2026-08-11): diese Tabelle zählt Aufruf*stellen* zu
> niedrig.** Zwei der fünf Funktionen haben **je zwei** Aufrufer:
> `generate_learning_path_text` (LP-Fast-Path **und** Direkt-Aktion) und
> `assess_safety` → `classify_legal` (assess-Knoten **und** preflight). Wer
> nach dieser Tabelle verdrahtet, lässt jeweils den zweiten Weg stumm.
> Vor jeder weiteren Verdrahtung: `grep` auf den Funktionsnamen, nicht auf die
> Tabelle.

## 3. Entscheidungen (Nutzer, 2026-08-11)

1. **Eigene Tabelle** `usage_events` statt JSONB-Auswertung — abrechnungsfest,
   indizierbar, eigene Aufbewahrungsfrist, unabhängig vom Debug-Format.
   **Ohne Rückfüllung:** die Vergangenheit trägt die Lücken aus M1/M2, die sich
   rückwirkend nicht schließen lassen; sie zu importieren hieße, falsche Zahlen
   abrechnungsfest zu machen.
2. **Erfassungsumfang: Chat vollständig.** M1 und M2 werden geschlossen.
   Embeddings, Evals und Lasttests bleiben draußen.
3. **Preise als Studio-Config** — YAML im Seed-Baum, editierbar wie die
   übrigen Bereiche. Preisänderung ohne Deploy.

## 4. Nicht im Umfang

* Embeddings, Evals, Lasttests, Sprachein-/ausgabe (eigene Preismodelle).
* Rückfüllung historischer Züge.
* Budget-Warnungen, Kontingente, Abschaltung bei Überschreitung.
* Rückwirkende Preishistorie („alter Zug zu altem Preis") — siehe Risiken.

## 5. Architektur

### 5.1 Dateien

| Datei | Verantwortung |
|---|---|
| `backend/src/boerdi/obs/usage.py` *(ändern)* | `extract_usage` liest zusätzlich `reasoning_tokens`; der Merkposten führt sie mit. Bleibt rein. |
| die fünf Module aus 2.3 *(ändern)* | `usage_acc` durchreichen, mit Phasen-Etikett. |
| `backend/src/boerdi/db/models.py` *(ändern)* | Neue Tabelle `UsageEvent`. |
| `backend/alembic/versions/0002_usage_events.py` *(neu)* | Migration (bisher gibt es nur `0001_schema.py`). |
| `backend/src/boerdi/domain/pricing.py` *(neu)* | **Rein:** Token + Preistafel → Betrag. Kennt weder DB noch Config-Laden. |
| `backend/src/boerdi/domain/config_models/pricing.py` *(neu)* | Bereichs-Modell, eingetragen in `AREA_MODELS` (`config_models/__init__.py:53`). |
| `backend/seeds/01-base/pricing.yaml` *(neu)* | Preise je Modell, je Million Token. |
| `backend/src/boerdi/services/usage_store.py` *(neu)* | Schreiben eines `UsageEvent`; Abfragen „je Sitzung" / „je Zeitraum". Einzige Stelle mit SQL. |
| `backend/src/boerdi/services/turn_persist.py` *(ändern)* | Ruft den Schreibvorgang mit dem fertigen Merkposten auf. |
| `backend/src/boerdi/api/usage.py` *(neu)* | Zwei Studio-Endpunkte (Auth). **Vertragsänderung — siehe 5.5.** |

**Abhängigkeitsrichtung:** `domain/pricing.py` ist rein und kennt nichts;
`services/usage_store.py` kennt DB und Domäne; `api/usage.py` kennt Services.
Nach innen, keine Zyklen.

### 5.2 Datenmodell

```python
class UsageEvent(Base):
    __tablename__ = "usage_events"
    id: BigInteger, PK
    session_id: Text, FK sessions.session_id ON DELETE CASCADE, indiziert
    model: Text                       # aufgelöster Modellname der Antwort
    prompt_tokens: Integer            # Eingabe GESAMT (Cache eingeschlossen)
    cached_tokens: Integer            # davon aus dem Prompt-Cache
    completion_tokens: Integer        # Ausgabe GESAMT (Reasoning eingeschlossen)
    reasoning_tokens: Integer         # davon Reasoning
    calls: Integer                    # LLM-Aufrufe in diesem Zug
    created_at: TIMESTAMPTZ, server_default now(), indiziert
```

**Die zwei „davon"-Felder sind der Kern und die häufigste Falle.** OpenAI zählt
`cached_tokens` **innerhalb** von `prompt_tokens` und `reasoning_tokens`
**innerhalb** von `completion_tokens`. Wer sie addiert, zahlt doppelt.

Eine Zeile **je Zug**, nicht je LLM-Aufruf: der Merkposten aggregiert bereits
über den Zug, und die Abrechnungseinheit ist die Sitzung. Je Aufruf wäre 5–10×
mehr Zeilen für eine Auflösung, die niemand abrechnet. Die Phasen-Aufteilung
bleibt im Debug-JSONB, wo sie der Diagnose dient.

**Mehrere Modelle in einem Zug:** der Merkposten führt `models` als Dict. Der
Zug schreibt deshalb **eine Zeile je Modell** — sonst wäre `model` gelogen,
sobald Klassifikation und Antwort verschiedene Modelle nutzen. Bei einem
Modell ist das genau eine Zeile.

### 5.3 Preisrechnung (`domain/pricing.py`)

```
Betrag = (prompt − cached) · P_eingabe
       +  cached           · P_cache
       +  completion       · P_ausgabe      # Reasoning ist darin enthalten
```

Reasoning wird **nicht** separat bepreist — die Anbieter berechnen es zum
Ausgabepreis. Es wird getrennt **gespeichert**, damit sichtbar ist, wofür die
Ausgabe draufging. Eine Anzeige-, keine Rechenfrage.

Signaturen:

```python
def cost_for(tokens: TokenCounts, table: PriceTable) -> Decimal | None: ...
def resolve_model_price(model: str, table: PriceTable) -> ModelPrice | None: ...
```

`Decimal`, nicht `float` — Geld. `None` heißt „Preis nicht gepflegt" und ist
ausdrücklich **nicht** `0`.

### 5.4 Preistafel (`seeds/01-base/pricing.yaml`)

```yaml
# Preise je 1 Mio. Token. Modellname wie ihn der Anbieter in der Antwort
# meldet (``resp.model``), nicht wie er konfiguriert ist — sonst trifft die
# Tafel bei Aliassen daneben.
currency: EUR
models:
  gpt-5.4-mini:
    input: 0.0
    cached_input: 0.0
    output: 0.0
```

**Alle Preise stehen im Seed auf 0,0.** Ein erfundener Preis wäre schlimmer als
keiner: er sähe aus wie eine Abrechnung. Für ein Modell ohne gepflegten Preis
meldet die Auswertung ausdrücklich „Preis nicht gepflegt" statt 0 € — sonst
liest sich eine ungepflegte Tafel als „hat nichts gekostet". Dieselbe Lehre wie
bei C2 (`/quality/tight-races`), wo ein stummes `0` als Messergebnis
missverstanden wurde.

**Modellname als Schlüssel:** `resp.model` kann eine Version tragen
(`gpt-5.4-mini-2026-03-01`), die Tafel aber den Kurznamen. `resolve_model_price`
probiert exakt, dann den längsten passenden Präfix, sonst `None`.

### 5.5 Vertragsfrage (vor K4 zu entscheiden)

Der OpenAPI-Vertrag ist eingefroren: `docs/api/openapi-v1.json`, gemessen
2026-08-11 **86 Pfade / 114 Operationen** (die im Repo-Plan genannten „107
Routen" sind eine ältere Zahl). Die Prüfung ist ein **Byte-Vergleich des ganzen
Dokuments** (`export_openapi.py:29`) — jede Abweichung ist rot, auch eine neue
Beschreibung oder ein neuer Query-Parameter.

**Gemessene Alternative:** alle Quality-Endpunkte geben `-> dict` zurück
(untypisiert), und mit `/api/health` + `reranker` ist belegt, dass zusätzliche
Schlüssel in einer untypisierten Antwort den Vertrag **byte-gleich** lassen.
Der Sitzungswert könnte also kostenlos an `GET /api/sessions/{session_id}`
hängen. **Die Zeitraum-Abfrage kann das nicht**: sie braucht `from`/`to`, und
ein neuer Parameter steht im Vertrag. `/api/quality/stats` führt nur `scope`
(freier `str`) — den Zeitraum dort hineinzucodieren wäre kostenlos, aber die
Beschreibung des Parameters wäre dann gelogen.

Da die Zeitraum-Abfrage die Änderung ohnehin erzwingt, ist der saubere Weg
besser als der formal billigere: **zwei eigene Routen unter `/api/usage/`,
einmal neu erzeugt, als benannter Eintrag dokumentiert.** Präzedenzfall
existiert (C1-g, zwei Routen bewusst additiv erweitert).

**Entschieden (Nutzer, 2026-08-11): so bauen, keine Rückfrage nötig.**
Begründung, und sie räumt den Einwand aus, den ich zuerst zu schwer gewichtet
hatte: Die Prüfung schützt **zwei** Dinge, und nur eines steht hier zur
Debatte.

* Die **ALT-Treue** („NEU bietet genau das, was ALT bot") ist an den Umbau
  gebunden und läuft mit der Stilllegung von ALT ohnehin ab — P11-Schritt 6
  ist genau das. NEU **ersetzt** ALT; die Aussage jetzt zu schonen, um sie
  planmäßig fallen zu lassen, wäre Formalie.
* Die **Drift-Erkennung** — dass eine *versehentliche* Änderung auffällt —
  ist von ALT unabhängig und bleibt nach dem Neu-Erzeugen **vollständig
  erhalten**. Sie ist der bleibende Wert des Gates.

Kompatibilität steht nicht auf dem Spiel: Aufrufer sind Widget und Studio,
beide im selben Repo; einen externen Verbraucher gibt es nicht.

Einziges Restrisiko: wird „Gate rot → neu erzeugen" zum Reflex, fängt es
irgendwann keine Versehen mehr. Gegenmittel ist der benannte Eintrag mit
Grund je bewusstem Zusatz (Vorbild: der `BEWUSST_EINSPRACHIG`-Wächter). K4
legt diese Liste an — als Abschnitt „Bewusste Vertragszusätze" in
`docs/api/`, mit `/api/usage/session/{session_id}` und `/api/usage/period`
als ersten beiden Einträgen.

---

## 6. Aufgaben

### Paket K1 — Erfassung wahr machen

*Ohne K1 ist jede spätere Zahl falsch. Kein Schema, keine API — sofort im
Debug-Panel sichtbar.*

**Schritt 0: `/better-coding-workflow` aufrufen.**

#### K1-0 — Den Merkposten überhaupt anlegen ✅ **fertig 2026-08-11**

*Nicht geplant gewesen — beim Bau von K1a gefunden (M0). Ohne diesen Schritt
wäre K1a Zierrat an einem toten Pfad geblieben.*

* **Geändert:** `backend/src/boerdi/graph/state.py` (ein Feld-Default)
* **Test:** `backend/tests/test_turn_context.py` (+2, einer korrigiert)

`TurnContext.usage` bekommt `default_factory=new_accumulator` statt `dict`.
**Warum am Feld und nicht im setup-Node** (wo ALT es tut): NEU hat ein
erstklassiges Zug-Zustandsobjekt; ALTs *lokale Variable* entspricht diesem
**Feld**, nicht einem Seiteneffekt eines Knotens. So bringt jeder Zug den
Merkposten mit — auch der, den ein Node-Test direkt konstruiert. Genau die
Optionalität war die Ursache: der Merkposten war überall *durchgereicht*,
aber nirgends *erzeugt*.

**Die zwei neuen Pins prüfen die VERBINDUNG, nicht die Seiten.** Beide Seiten
waren für sich korrekt und getestet — `obs/usage.py` mit 7 Tests, die
Durchreichungen mit je eigenen. Alle bauten den Merkposten **von Hand**. Das
ist zum vierten Mal dieselbe Klasse (P11 LiteLLM ×2, `_pending_write`,
`prewarm_vocabularies`): *die Attrappe teilt die Annahme des Codes, statt die
Wirklichkeit abzubilden.* Gegenmittel bleibt: **die Naht pinnen, nicht die
Seiten.**

`test_turn_context.py:56` hatte `assert ctx.usage == {}` — ein Test, der den
Irrtum festschrieb. Korrigiert mit Begründung im Text.

**Rot gesehen:** `KeyError: 'calls'` — die Buchung lief ins Leere.
**Verifikation:** `pytest tests/test_turn_context.py -q` → 7 passed; voller
Lauf danach **2907 passed / 4 skipped** (vorher 2905) — kein Bestandstest hing
an der Leere.

#### K1a — Reasoning-Token lesen ✅ **fertig 2026-08-11**

* **Ändern:** `backend/src/boerdi/obs/usage.py`
* **Test:** `backend/tests/test_usage.py`

`extract_usage` gibt zusätzlich `"reasoning"` zurück, gelesen aus
`completion_tokens_details.reasoning_tokens` (0 bei jedem Fehlschlag, wie bei
`cached`). `new_accumulator` führt `reasoning_tokens: 0`; `add_usage` summiert
es in die Gesamtsumme, den Modell- und den Phasen-Topf.

Test zuerst, gegen die **echten** LiteLLM-Typen (nicht gegen ein Dict-Attrappe):

```python
from litellm.types.utils import (ModelResponse, Usage,
                                 CompletionTokensDetailsWrapper)
def test_reasoning_wird_gelesen():
    u = Usage(prompt_tokens=10, completion_tokens=20,
              completion_tokens_details=CompletionTokensDetailsWrapper(
                  reasoning_tokens=8))
    assert extract_usage(ModelResponse(model="m", usage=u))["reasoning"] == 8
```

Erwarteter Fehlschlag vorher: `KeyError: 'reasoning'`.

**Verifikation:** `uv run pytest tests/test_usage.py -q` grün; das Debug-Panel
zeigt die Zahl unverändert weiter (kein Frontend-Zwang — `token_usage` ist ein
freies Dict, der OpenAPI-Vertrag ändert sich **nicht**).

**So gebaut, mit zwei Ergänzungen gegenüber dem Entwurf:**

1. Der Merkposten führt `reasoning_tokens` in **allen drei** Töpfen (gesamt,
   je Modell als `reasoning`, je Phase als `reasoning`) — der Entwurf nannte
   nur die Gesamtsumme, aber ein Posten, der je Modell fehlt, macht die
   spätere Zeile je Modell (5.2) unvollständig.
2. Zwei Doku-Stellen mitgezogen, damit sie nicht lügen:
   `api/schemas_debug.py` (Format-Kommentar, jetzt inkl. `per_phase` und dem
   „davon"-Hinweis) und `frontend/…/grouping/message-types.ts` (Typ des
   Debug-Nutzlast). **Keine** Anzeigeänderung — die gehört zu K5.

**Rot gesehen:** 6 Fehlschläge, u.a. `Right contains 1 more item:
{'reasoning_tokens': 0}` und der Pin gegen die echten LiteLLM-Typen.
**Gemessen, nicht angenommen:** `CompletionTokensDetailsWrapper(reasoning_tokens=8)`
existiert im installierten Paket und kommt als Objekt (nicht dict) an.

**Verifikation (frisch gelaufen):**
`OTEL_TRACES_EXPORTER=none uv run pytest -q` → **2909 passed / 4 skipped** ·
`uv run ruff check src/boerdi tests/` → *All checks passed!* ·
`uv run python scripts/export_openapi.py --check` → *openapi contract unchanged* ·
`npx ng test ui` → **701 passed** (69 Dateien).

#### K1b — Lernpfad-Generator bucht ✅ **fertig 2026-08-11**

* **Ändern:** `services/llm_learning_path.py` (Parameter `usage_acc` an
  `generate_learning_path_text`, Weitergabe an `chat_completion` mit
  `phase="learning_path"`), `services/lp_fast_path.py:374` (durchreichen —
  der Merkposten liegt dort bereits als Parameter, Z. 95).
* **Test:** `backend/tests/test_lp_fast_path.py` — Lauf mit frischem
  Merkposten, danach `acc["calls"] >= 1` und `acc["per_phase"]["learning_path"]`.

**Zwei Funde, die den Schnitt geändert haben:**

1. **Der Generator hat ZWEI Aufrufer.** Die Messung in 2.3 nannte nur
   `lp_fast_path`; `direct_actions._handle_generate_learning_path:376` ruft ihn
   ebenso. **7. Mal, dass meine Aufzählung eine untere Schranke war.** Deshalb
   umfasst K1b jetzt die ganze Lernpfad-Geschichte (beide Wege), und K1c nur
   noch Kuration + Canvas.
2. **Die Direkt-Aktion braucht ein eigenes ZIEL.** Sie beendet den Zug im
   preflight-Knoten (`early_response`), also läuft `turn_persist` — die einzige
   Stelle, die sonst `token_usage` füllt — dort **nie**. Ohne Zuweisung an das
   `DebugInfo` des Handlers wäre die Buchung wieder berechnet und
   weggeworfen; genau der Fehler aus M0, eine Ebene tiefer. **Folge für K2b:**
   der `usage_events`-Schreiber kann NICHT allein in `turn_persist` sitzen.

Nebenbei: derselbe Handler ruft `generate_quick_replies`, das `usage_acc`
**seit je unterstützt** und einfach keines bekam — jetzt auch verdrahtet.

**Dritter Fund, beim Nachsehen statt beim Abarbeiten:** auch
`_handle_browse_collection` ruft den QR-Generator. Das reine *Blättern* kostet
also Token, und es stand in **keiner** Liste — die Messung zählte Module mit
eigenem Generator und übersah den **geteilten**. Ebenfalls verdrahtet.
`show_content_text` dagegen ist gemessen frei von LLM-Aufrufen (nur MCP) und
bleibt bewusst ohne Merkposten.

**Verifikation:** rot gesehen (4×, u.a. `TypeError: ... unexpected keyword
argument 'usage_acc'`), danach 57 Tests in den vier berührten Modulen grün.

#### K1c — Kuration und Canvas buchen ✅ **fertig 2026-08-11**

* **Ändern:** `services/llm_curation.py` + `services/direct_actions.py`
  (Parameter durchreichen) + `graph/nodes/preflight.py` (`ctx.usage` hinein),
  Phase `"curation"`.
* **Ändern:** `services/canvas_service.py` + `services/canvas_fast_path.py`
  (Parameter an `run_canvas_create_fast_path`) + `graph/nodes/route.py`
  (`usage_acc=ctx.usage`, wie schon Z. 215 für den LP-Pfad), Phase `"canvas"`.
* **Test:** je ein Naht-Test wie K1b.

**So gebaut.** Die Kuration setzt `token_usage` ebenfalls in ihr eigenes
`DebugInfo` (gleicher Grund wie K1b). Der Canvas-Fast-Path bekam den
Merkposten **neu als Parameter** — er führte, anders als der LP-Fast-Path,
gar keinen. Ein Bestandstest pinnte die Aufruf-kwargs des Generators exakt
und fiel deshalb zu Recht; er trägt den neuen Schlüssel jetzt mit.

**Verifikation:** rot gesehen, danach 45 (Kuration) bzw. 74 (Canvas) Tests
grün in den berührten Modulen.

#### K1d — Rechtsprüfung bucht ✅ **fertig 2026-08-11**

* **Ändern:** `services/safety/legal.py`, `services/safety/service.py:230`,
  `graph/nodes/assess.py` (zwei Hops), Phase `"legal"`.
* **Achtung:** der Aufruf steckt in einem `gather`; der Merkposten wird von
  mehreren Nebenläufigen beschrieben. `add_usage` ist eine reine
  Dict-Mutation ohne await — unter asyncio damit atomar genug. **Im Test
  ausdrücklich zwei gleichzeitige Aufrufe fahren** und prüfen, dass beide
  gezählt sind.

**Dritter Fund derselben Art: `assess_safety` hat ebenfalls ZWEI Aufrufer** —
den assess-Knoten *und* den preflight-Knoten (`preflight.py:112`, vor der
Direkt-Aktion). Der Plan nannte nur den ersten. Beide reichen jetzt
`ctx.usage` durch.

Der Nebenläufigkeitstest fährt **echt gleichzeitig** (`asyncio.gather` mit
einem `await asyncio.sleep(0)` im Transport, das einen Aufgabenwechsel
erzwingt) und benutzt eine Attrappe **mit** Buchung — eine ohne hätte den
Test wertlos gemacht, weil dann gar nichts zu zählen gewesen wäre. Ergebnis:
beide Aufrufe gezählt, `per_phase["legal"]["prompt"] == 20`.

**Verifikation:** rot gesehen, danach 46 Tests in den vier Modulen grün.

**Gesamtstand nach K1b–K1d (2026-08-11):** `OTEL_TRACES_EXPORTER=none uv run
pytest -q` → **2925 passed / 4 skipped** (vorher 2909) · `ruff` sauber ·
`export_openapi.py --check` → *openapi contract unchanged*. Vier der fünf
Stellen aus 2.3 buchen jetzt; offen bleibt allein K1e.

#### K1e — Vokabular-Abgleich bucht ✅ **fertig 2026-08-11**

**Zuerst gemessen, wie der Plan es verlangt.** Nicht im Live-Smoke, sondern
schärfer: der echte Produktivpfad (`_llm_vocab_match`) lief gegen die **echten
WLO-Vokabulare**, nur der Netz-Aufruf abgefangen — so steht da der Prompt, den
die Produktion wirklich sendet, statt einer Schätzung.

| Vokabular | Einträge | Prompt **eines** Aufrufs |
|---|---|---|
| `lrt` | 113 Schlüssel / 48 URIs | **2727 Token** |
| `discipline` | 190 Schlüssel / 70 URIs | **2422 Token** |
| `educationalContext` | 49 / 12 | 612 Token |
| `userRole` | 31 / 7 | 389 Token |

Der Prompt trägt das **ganze** Vokabular; vier Filter an einem Werkzeug-Aufruf
kosten im schlimmsten Fall ~6150 Token. Das ist kein Rundungsfehler.

**Und der Pfad zieht öfter als gedacht.** Über 61 realistische Filterwerte
greift die Fuzzy-Heuristik in 78,7 % — **21,3 % gehen an den LLM**. Die Ausfälle
sind kein Rauschen, sondern ein Muster: `Gymnasium`, `Oberstufe`, `Klasse 11`
(die Bildungsstufe kennt nur `sekundarstufe_2`) und vor allem **`teacher` und
`learner`** — die englischen Wörter stehen in der Zielgruppe nicht als Alias,
obwohl sie die URI benennen. Seit C1 sind englische Züge ein zugesagtes
Produktmerkmal, dieser Weg trifft künftig also **häufiger**, nicht seltener.
Weg 3 („nicht buchen") ist damit vom Tisch.

**Gewählt: ein vierter Weg, den dieser Plan nicht kannte — `ContextVar`.**
Weg 1 ist teurer als hier geschätzt: er ändert nicht „drei Schichten", sondern
den Vertrag der `TOOL_PREPROCESSORS`-Registry (alle 5 Vorverarbeiter, 3 davon
ohne jedes Interesse) **plus 25 `call_mcp_tool`-Aufrufstellen in 11 Dateien**,
von denen keine einzige mit Kosten zu tun hat.

Den Ausschlag gab: **dieselbe Abwägung ist in genau diesem Pfad schon getroffen
und schriftlich begründet.** `mcp/auth.py` (Z. 22) trägt den Zugangsblock per
ContextVar, „weil es 23 Aufrufstellen von `call_mcp_tool` in 9 Dateien gibt; der
Block interessiert unterwegs niemanden" — und nennt `_query_metas` und
`_request_hints` als dieselbe Lösung. Ein ContextVar ist **kein** Modul-Zustand
im Sinn der eisernen Regel: der Wert hängt an der asyncio-Task, ist also je Zug
getrennt und bei N Repliken richtig. Weg 2 (Prozess-Summe) bleibt zu Recht
ausgeschlossen — genau diese Eigenschaft hätte er nicht.

* **Neu** in `obs/usage.py`: `bind_turn_usage()` / `current_turn_usage()`.
  Standard ist `None` und **ausdrücklich kein `{}`** — ein leeres Dict wäre die
  Wiederauferstehung von M0 (`add_usage` kehrt bei falschem `acc` still zurück).
* **Gebunden** im setup-Knoten, direkt neben `reset_query_metas()`: `START →
  setup` ist der Eingang des Graphen, also erbt **jeder** spätere Knoten und
  jede von ihm erzeugte Task die Bindung. Dieselbe Grundhygiene, dieselbe
  Begründung — ein Zug darf nie am Merkposten des vorigen hängen.
* **Gelesen** an der Aufrufstelle: `usage_acc=current_turn_usage()`,
  `phase="vocab_match"`. Damit steht dort ein sichtbares `usage_acc` — der
  K1f-Wächter braucht für diese Stelle **keine** Ausnahme.

**Der Test, der zählt, ist der über die Naht.** Zwei getrennt grüne Tests
(„setup bindet" + „das Blatt bucht") sind genau die Konstellation, die M0
durchgelassen hat. `test_setup_bindet_den_merkposten_des_zuges_und_ein_blatt_bucht_hinein`
fährt beides in EINER Task-Kette und stand vor dem Fix auf `ctx.usage["calls"]
== 0` — die Produktion buchte nachweislich nichts. Falle dabei: `asyncio.run`
kopiert den Kontext, eine Bindung **im** Lauf ist draußen unsichtbar; die
Prüfung muss innerhalb stehen.

Ein Cache-Treffer bucht bewusst nichts (kein Aufruf, keine Kosten), und ohne Zug
(Start-Vorwärmung) bucht niemand, ohne dass etwas bricht — beides gepinnt.

**Verifikation:** rot gesehen (`AttributeError: bind_turn_usage`, dann
`assert 0 == 1` in der Nahttest-Zeile), danach 53 Tests in den drei berührten
Modulen grün.

**Gesamtstand nach K1e (2026-08-11):** `OTEL_TRACES_EXPORTER=none uv run
pytest -q` → **2932 passed / 4 skipped** · `ruff` sauber ·
`export_openapi.py --check` → *openapi contract unchanged*. **Alle fünf Stellen
aus 2.3 buchen jetzt** — K1 ist bis auf den Wächter K1f zu.

#### K1f — Der Wächter ✅ **fertig 2026-08-11**

* **Neu:** `backend/tests/test_usage_coverage.py`

Zählt über den AST **alle** `chat_completion`-Aufrufstellen unter
`src/boerdi/` auf und verlangt, dass jede entweder `usage_acc` führt oder in
`OHNE_BUCHUNG` mit Begründung steht (Vorbild: `BEWUSST_EINSPRACHIG` in
`tests/test_i18n_messages.py`).

**Er hat sich beim ERSTEN Lauf bezahlt gemacht.** 12 Aufrufstellen, 6 ohne
`usage_acc` — und eine davon war ein echtes Loch, das in **keiner** der bisher
fünf gezählten Stellen stand: `_max_iterations_fallback`
(`services/tool_loop.py`). Der Abschluss-Aufruf, wenn der Tool-Loop die
Iterationsgrenze reißt, hängt die **ganze** bisherige Nachrichtenkette an — also
gerade kein kleiner Aufruf — und lief ungebucht. Warum ihn jede frühere Zählung
übersah: die Messung suchte Module mit *eigenem* Generator, und `tool_loop`
galt als „bucht schon". Es bucht auch — nur an einer anderen Stelle derselben
Datei. **Das ist die fünfte Wiederholung derselben Klasse und die erste, bei
der nicht ich sie gefunden habe, sondern die Maschine.** Gebucht wird jetzt
unter eigener Phase `fallback_summary`: ihr Auftauchen meldet zugleich, dass
der Zug die Iterationsgrenze gerissen hat — ein Qualitätssignal, das in
`response` untergegangen wäre.

Die verbleibenden fünf Ausnahmen sind echte Ausnahmen, je mit Grund:

| Stelle | Grund |
|---|---|
| `eval/judge.py::judge_turn` · `eval/runner.py::simulate_conversation` (2 Aufrufe) · `eval/scenario_gen.py::generate_scenarios` | Evals sind laut §4 nicht im Umfang. |
| `tool_loop.py::_run_tool_loop` | **Bucht selbst** direkt hinter dem Aufruf — und muss das: das Phasen-Etikett (`tool_loop` vs. `response`) folgt erst aus `finish_reason`/`tool_calls` der Antwort. Derselbe Block bucht den Streaming-Zweig mit. |

Drei Eigenschaften, die den Wächter vor dem üblichen Verrotten schützen:

1. **Beide Richtungen.** Ein Eintrag, der nicht mehr gebraucht wird, lässt den
   Test fallen. Eine Ausnahmeliste, die stillschweigend veraltet, macht die
   übrigen Einträge unglaubwürdig.
2. **Der Aufzähler ist selbst geprüft** — drei Tests fahren ihn gegen erfundene
   Quelltexte (mit / ohne `usage_acc`, verschachtelte Funktionen,
   Namensdoppelgänger). Ein Wächter, der nie anschlagen kann, ist keiner.
3. **Schutz gegen den stillen Totalausfall:** ein kaputter Pfad würde eine leere
   Menge liefern und alles grün färben — deshalb die Untergrenze „mindestens 10
   Aufrufstellen gefunden".

Bewusst nicht erfasst: `llm.embedding` (M5, Nutzer-Entscheid) und der rohe
Transport `llm._acompletion`. Letzterer hat außerhalb von `llm.py` **genau
einen** Aufrufer (`_stream_completion`), dessen einziger Nutzer der Tool-Loop
ist — der beide Zweige mit derselben Hand bucht. Gemessen, nicht vermutet.

**Verifikation:** rot gesehen in beiden Richtungen (erst „neue Stelle ohne
`usage_acc`", dann „Ausnahme wird nicht mehr gebraucht" — der zweite Fehler
korrigierte meinen geratenen Funktionsnamen), danach 7 grün.

**Gesamtstand nach K1 (2026-08-11): K1 ist ZU.** `OTEL_TRACES_EXPORTER=none uv
run pytest -q` → **2940 passed / 4 skipped** · `ruff` sauber ·
`export_openapi.py --check` → *openapi contract unchanged*.

---

### Paket K2 — Tabelle und Schreiben

**Schritt 0: `/better-coding-workflow` aufrufen.**

#### K2a — Modell und Migration ✅ **fertig 2026-08-11**

* **Geändert:** `db/models.py` — Klasse `UsageEvent`, Felder wie 5.2.
* **Neu:** `alembic/versions/0002_usage_events.py`, zwei Indizes
  (`idx_usage_session`, `idx_usage_created`).

**Beide Richtungen gegen die echte Compose-PG gefahren**, wie hier verlangt:

```
nach upgrade head : version=0002 usage_events=True
nach downgrade    : version=0001 usage_events=False
nach re-upgrade   : version=0002 usage_events=True
```

Bewusst **keine** CHECK-Bedingung auf die „davon"-Felder
(`cached ≤ prompt`, `reasoning ≤ completion`): eine Zeile zu verlieren, weil
ein Anbieter einmal seltsam zählt, wäre schlechter als eine seltsame Zeile zu
haben — und der Schreibpfad darf einen Zug nie scheitern lassen. Die Semantik
steht stattdessen im Docstring der Klasse und in der Migration.

Drei Tests in `test_db_migration.py`: Tabelle + Indizes, ORM-Rundlauf gegen die
migrierte DDL, und die **DSGVO-Zusage aus §8 nachgewiesen statt behauptet** —
beim Löschen der Sitzung verschwinden ihre Verbrauchszeilen (`ON DELETE
CASCADE`).

#### K2b — Schreibpfad ✅ **fertig 2026-08-11**

* **Neu:** `services/usage_store.py` — `record_turn_usage(session, session_id,
  acc) -> int`, eine Zeile je Modell des Zuges.
* **Geändert:** `api/chat.py` — `_record_usage(...)` direkt hinter `ainvoke`,
  in **beiden** Endpunkten.

> **Abweichung vom Plan, mit Grund.** Der Plan sah `turn_persist` plus eine
> zweite Stelle für Direkt-Aktionen vor und warnte selbst, die Wege
> aufzuzählen statt zu raten. Die Aufzählung wurde gemacht — und ergab, dass
> **nur zwei** Ausstiege überhaupt Token kosten: der Hauptweg und preflight
> (Direkt-Aktion *und* Sicherheits-Block). Tour und Kontext-Begrüßung rufen
> nachweislich kein LLM, die Drosselung greift davor.
>
> Trotzdem ist die Aufzählung nicht der beste Ort. Genau die Fehlerklasse, an
> der dieser Plan fünfmal hängengeblieben ist, heißt „ein neuer Weg wird
> gebaut und fällt still heraus" — dagegen hilft kein sorgfältiges Aufzählen,
> sondern ein **Trichter**. Hinter `ainvoke` liegt der einzige Punkt, den
> jeder Zug passiert, ganz gleich welcher Knoten ihn beendet hat. Zwei
> Aufrufstellen (POST und Stream), beide sichtbar, keine Aufzählung, die
> veralten kann. Der Merkposten steht dort als `state["usage"]` bereit, weil
> er seit K1-0 ein Feld des `TurnContext` ist.
>
> Preis der Abweichung: die Buchhaltung sitzt in der API-Schicht statt im
> Dienst. Das ist die übliche Richtung (api → services) und kostet vier Zeilen.

**Fehler halten den Zug nicht an** — zweifach abgesichert: `usage_store`
schluckt und protokolliert seine eigenen Fehler (mit `rollback`, sonst wäre die
Sitzung für den nächsten Schreibversuch verdorben), und `_record_usage` fängt
zusätzlich alles davor. Beides ist getestet, inklusive „die Antwort geht
trotzdem raus".

**Tests:** zwei Modelle → zwei Zeilen (gegen die echte PG, mit dem echten
Modell — eine Attrappe hätte gerade das nicht geprüft); ein Zug ohne LLM-Aufruf
→ keine Zeile (auch für `None` und `{}`); Schreibfehler → 0 statt Ausnahme;
Trichter in beiden Endpunkten, je mit Identitätsprüfung auf den Merkposten;
Früh-Antwort (Direkt-Aktion) bucht ebenfalls — der Fall, den ein Schreiben im
persist-Knoten verloren hätte.

---

### Paket K3 — Preise ✅ **fertig 2026-08-11**

* **Neu:** `domain/pricing.py` (123 Z.), `domain/config_models/pricing.py`
  (46 Z.), `seeds/01-base/pricing.yaml` (32 Z.).
* **Geändert:** `domain/config_models/__init__.py` (`AREA_MODELS`),
  `frontend/…/schema-form/json-schema.ts` (+`minimum`),
  `area-schemas.fixture.ts` (neu erzeugt).

**Der 36. Bereich, sichtbar statt still.** `test_config_models` sagte zu:
„die Registry deckt **genau** die 35 Bereiche der Spezifikation". Diese Zusage
einfach auf 36 hochzuzählen hätte die ALT-Treue stumm aufgegeben. Stattdessen
eine zweite, getrennte Liste `NEUE_BEREICHE` — je Eintrag mit Grund, nach dem
Vorbild von `BEWUSST_EINSPRACHIG` (i18n) und `OHNE_BUCHUNG` (K1f). Der Wächter
prüft `SPEC_AREAS | NEUE_BEREICHE`, hält `len(SPEC_AREAS) == 35` fest und
läuft in beiden Richtungen (ein Eintrag ohne Registry-Gegenstück fällt auf).

> **Abweichung 1: `float` im Bereichsmodell, `Decimal` erst in der Rechnung.**
> §5.3 sagt „`Decimal`, nicht `float` — Geld", und das gilt: nur gehört der
> Geld-Typ in `domain/pricing.py`, nicht ins Config-Modell. Der Beleg kam beim
> Bauen: ein `Decimal`-Feld verschemat pydantic als
> `anyOf: [number, string]` **mit `pattern`** — Formen, die der Studio-Typ
> `JsonSchema` ausdrücklich NICHT führt (dokumentierte, gemessene Teilmenge),
> woraufhin der Editor laut eigener Politik auf ein JSON-Textfeld zurückfällt.
> Der Studio-Build brach mit `TS2353` ab. Eine Preistafel, die man nur noch als
> JSON tippen kann, verfehlt den Zweck dieses Bereichs. Mit `float` steht dort
> `type: number` + `minimum` — die Umwandlung passiert sichtbar in
> `_als_decimal` (über `str`, wie pydantic es intern täte). Der Studio-Typ
> bekommt `minimum` nachgetragen, weil der Endpunkt es wirklich liefert; der
> `raws`-Wächter des Studios blieb dabei **unverändert grün**, die Tafel
> rendert also mit echten Feldern.
>
> **Abweichung 2: Präfixe enden an der `-`-Grenze.** §5.4 sagt nur „längster
> passender Präfix". Ohne Grenze bepreiste ein Eintrag `gpt-5` stillschweigend
> auch `gpt-55-turbo` — falsches Geld ohne jede Meldung.

**Entscheidung, die §5.4 zu Ende denkt:** ein Eintrag aus **lauter Nullen gilt
als nicht gepflegt**, nicht als Nulltarif. Der ausgelieferte Seed steht ja
genau so da; läse man ihn als „0 €", meldete eine frische Installation „hat
nichts gekostet" — der Fehler, den §5.4 vermeiden will. Preis der Entscheidung:
ein tatsächlich kostenloses Modell ist nicht ausdrückbar. Für eine interne
Kostenschau kein Verlust. Ein **negativer** Wert zählt ebenfalls als
ungepflegt: das Studio weist ihn beim Speichern ab (`ge=0`), aber
`seed_io.import_tree` schreibt **ungeprüfte** Dicts — und eine Gutschrift wäre
der stillere Fehler von beiden.

**Tests (19 in `test_pricing.py`, 1 in `test_config_data_endpoint.py`):**
Rechenbeispiel von Hand (4,92 €); Cache wird abgezogen statt addiert;
`reasoning` ist **kein Feld** von `TokenCounts` (Wächter gegen
Doppelberechnung); `cached > prompt` verkleinert nichts; unbekanntes Modell →
`None` und ausdrücklich `!= Decimal(0)`; Präfix längster/mit Grenze; exakter
Treffer ohne Preis fällt **nicht** auf den kürzeren zurück; Seed behauptet
keinen Preis; Seed-Roundtrip über den ganzen Baum; und die ganze Kette aus §7
(„Preis einstellbar"): PUT über `/api/config/data/01-base/pricing` gegen die
echte PG → dieselbe Zeile rechnet danach 3 € statt „nicht gepflegt".

Die drei tragenden Vorkehrungen wurden **einzeln ausgehebelt**, um zu belegen,
dass ihr Test wirklich fällt (Bindestrich-Grenze, Nullen-Regel, Cache-Deckel —
je rot). Ein Beispiel im Test war zunächst falsch geraten: `3 Mio × 0,10 €`
driftet in `float` gar nicht. Ersetzt durch ein **gemessenes** Paar —
486.531 Token zu 27,29 € ergeben in `float` 13,277430990000001, in `Decimal`
glatt 13,27743099.

**Belege:** pytest 2972/4 · ruff sauber · OpenAPI unverändert (K3 fügt keine
Route hinzu — der Vertragszusatz gehört zu K4) · `npx ng test studio` 897 grün.

---

### Paket K4 — Auswertung ✅ **fertig 2026-08-11**

* **Neu:** `api/usage.py` (73 Z.), `services/usage_analytics.py` (137 Z.),
  `services/config_loader/pricing.py` (29 Z.),
  `docs/api/bewusste-vertragszusaetze.md`.
* **Geändert:** `main.py` (Router), `i18n/messages.py` (+1 Schlüssel je
  Sprache), `tests/test_openapi_contract.py` (Routen-Inventar),
  `docs/api/openapi-v1.json` **neu erzeugt** — 86/114 → **88 Pfade / 116
  Operationen**, genau +2/+2.

> **Abweichung vom Plan, mit Grund.** Der Plan nannte nur `api/usage.py`.
> Gebaut ist die Hausform: dünner Router über einem Dienst
> (`quality.py` → `quality_analytics.py`). SQL-Aggregation und HTTP-Vertrag
> sind zwei Gründe zu ändern; ausserdem hat der Schreibpfad `usage_store.py`
> damit sein natürliches Gegenstück auf der Lesehand.

**Der Betrag verlässt den Server als Zeichenkette.** Als JSON-Zahl würde aus
`13.27743099` beim Serialisieren wieder `13.277430990000001` — die ganze
`Decimal`-Rechnung aus K3 wäre auf dem letzten Meter verloren. Der Rot-Lauf hat
dabei eine Frage aufgeworfen, die keine Testkosmetik war: `str(Decimal)` hängt
am Exponenten der Eingabe, dieselben 2 € kämen je nach Preistafel als `2`, `2.0`
oder `2.00` an. Gemessen: `normalize()` allein hilft nicht (aus 100 wird
`1E+2`, wissenschaftliche Schreibweise im Studio). Gewählt ist
`format(betrag.normalize(), "f")` — exakt, stabil, ohne Exponent; **nicht** auf
zwei Nachkommastellen gerundet, weil ein einzelner Zug oft Bruchteile eines
Cents kostet und `0,00 €` sich wie „hat nichts gekostet" läse.

**Teilsumme statt Alles-oder-nichts.** Der Plan schrieb „Betrag **oder**
`price_unavailable`". Gebaut ist beides zugleich: `amount` deckt die bepreisten
Modelle, `price_unavailable` nennt die übrigen. Strikt gelesen bliebe `amount`
für immer `null`, sobald ein einziges seltenes Modell ungepflegt ist — ein Feld,
das nie etwas sagt, wird ignoriert. **Pflicht für K5:** die Liste muss neben dem
Betrag stehen, sonst liest sich die Teilsumme als Gesamtsumme.

**Zwei Wächter haben die Änderung gefangen — beide zu Recht.**

1. `test_i18n_messages` (C1-e): mein 422-Text war rohes Deutsch am Katalog
   vorbei. Richtig ist der Katalog-Schlüssel (`usage.periodReversed`), nicht ein
   Eintrag in `BEWUSST_EINSPRACHIG` — das Studio ist zweisprachig.
2. `test_openapi_contract::test_route_inventory_matches_spec_5_1`: ein **zweiter**
   Vertragswächter, der das Inventar der laufenden App gegen eine Liste im Test
   hält. Er hat für additive Routen schon ein Muster (V3, U1); dem folgt K4.

Die neue `Lang`-Abhängigkeit ändert den Vertrag **nicht** — `request_locale`
liest den Header von `Request` statt ihn zu deklarieren (C1-e-Trick), also
bleibt `--check` nach dem Neu-Erzeugen grün.

**Die benannte Liste** (`docs/api/bewusste-vertragszusaetze.md`) ist das
Gegenmittel gegen den „Gate rot → neu erzeugen"-Reflex aus §5.5.
`tests/test_openapi_additions.py` bewacht sie und wurde in **drei** Richtungen
rot gesehen: Eintrag gelöscht · undokumentierte Route im neu erzeugten Vertrag ·
Liste nennt etwas, das es nicht gibt. Der eingefrorene Stand (86/114) steht dort
als Konstante und darf nicht nachgezogen werden.

**Gemessen statt angenommen:** der Studio-BFF (`studio_proxy.py`) schreibt
`/studio/api/<rest>` generisch auf `/api/<rest>` um — **keine** Pfad-Liste. K5
erreicht die Routen ohne Backend-Änderung.

**Tests (22):** Summen je Sitzung über drei Zeilen/zwei Modelle; fremde Sitzung
zählt nicht mit; Sitzung ohne Zeilen meldet `empty` statt 404; Zeitraum trennt
zwei Züge (früh/spät/beide); leerer Zeitraum liefert Nullen **und** `empty`;
Betrag aus dem K3-Beispiel durch die ganze Kette (4,92 €); Betrag ist Text;
kein Exponent bei 100 €; ohne Preis `null` + Modellnamen; Teilsumme nennt die
Lücke; `from`/`to`-Alias; zonenlose Angabe wird UTC; vertauschte Grenzen 422
**ohne** den Dienst zu fragen; beide Routen 401 ohne Schlüssel; Absage
zweisprachig.

**Belege:** pytest 2995/4 · ruff sauber · `export_openapi.py --check` grün.

---

### Paket K5 — Studio-Ansicht „Kosten" ✅ **fertig 2026-08-12**

**Schritt 0: `/better-coding-workflow` **und** `/better-coding-frontend`.** ✔

**Der Plan verlangte etwas, das es noch nicht gab.** „Die teuersten Sitzungen"
war in K4 nicht gebaut — dort stehen nur „je Sitzung" und „je Zeitraum". K5
zerfällt deshalb in **K5a (Backend)** und **K5b (Oberfläche)**.

#### K5a — die teuersten Sitzungen

* **Geändert:** `services/usage_analytics.py` (137 → 262 Z.): `_SessionTally`,
  `_grouped_by_session`, `_tally_sessions`, `_by_cost`, `_top_sessions`;
  `period_usage` trägt jetzt zusätzlich `sessions` (Deckel `_TOP_SESSIONS = 10`).
* **Kein Vertragszusatz.** Gemessen statt vermutet: die 200er-Antwort beider
  Kosten-Routen ist im eingefrorenen Dokument
  `{"type":"object","additionalProperties":true}` — kein Feld ist gepinnt. Ein
  zusätzlicher Schlüssel ändert den Vertrag also **nicht**; `--check` bleibt
  grün und `docs/api/bewusste-vertragszusaetze.md` unberührt. Eine dritte Route
  hätte die §5.5-Ausnahme ein zweites Mal ausgegeben, für Zahlen, die dieselbe
  Ansicht im selben Fenster ohnehin zusammen liest.
* **Die Rangfolge entsteht in Python, nicht in SQL** — der Preis lebt in der
  Config, nicht in der Datenbank, also könnte `ORDER BY` nur nach Token sortieren
  und das ist eine andere Reihenfolge, sobald zwei Modelle verschieden kosten.
  Preis: eine Zeile je Sitzung **und** Modell im Speicher; als `simplify:` im
  Modul vermerkt, Ausweg wäre der eingefrorene Betrag aus den Risiken.
* **Ohne gepflegte Preise ordnet die Liste nach Token.** Der ausgelieferte Seed
  pflegt keine — nach Betrag zu sortieren hiesse dann, gar nicht zu sortieren,
  und zwar genau beim ersten Blick auf eine frische Anlage.

#### K5b — die Ansicht

* **Neu:** `views/costs.component.{ts,html,scss,spec.ts}` (146/181/234/265 Z.),
  `core/usage-api.service.ts` (63 Z.), `i18n/catalogue/costs.ts` (115 Z.).
* **Geändert:** `core/format.ts` (+`formatMoney`), `i18n/studio-format.service.ts`
  (+`money`), `studio-views.ts` (20. Ansicht, `paket: 'K5'`), `app.routes.ts`,
  `i18n/catalogue/{parts,views}.ts`, `studio-views.spec.ts`, `views-i18n.spec.ts`.
* **Betrag als Text bis zum Bildschirm.** `formatMoney` nimmt eine Zeichenkette
  und entscheidet die Nachkommastellen **an ihren Ziffern**, nicht an einem
  Gleitkommawert: zwei Stellen normal, mehr nur wenn zwei eine echte Zahl auf
  `0,00 €` rundeten. Ein einzelner Zug kostet oft Bruchteile eines Cents.
* **`currency` ist ein freies Config-Feld.** `Intl` wirft bei einem ungültigen
  Code einen `RangeError` — „Euro" statt „EUR" hätte die ganze Ansicht geleert.
  Ungültige Codes fallen auf eine schlichte Zahl mit angehängtem Code zurück.
* **Die Auflage aus K4 ist eingelöst:** `price_unavailable` steht **neben** dem
  Betrag (Teilsumme mit Modellnamen), und ohne jeden Preis steht dort ein Strich
  samt Grund — nie eine erfundene Null.
* **Kein Kostenwert im Widget.** `ng test ui` unverändert bei 701.

**Zwei Funde, die kein Test von selbst gefunden hätte.**

1. **Das Tagesende.** Der Server liest ein blosses Datum als Mitternacht. „Bis
   heute" hätte den ganzen heutigen Tag verloren — **stumm**, denn eine
   kleinere Summe sieht aus wie eine kleinere Summe. Die Ansicht schickt darum
   `T23:59:59.999Z`; für einen Menschen heisst „bis 11.08." einschliesslich des
   11.08., und diese Übersetzung gehört in die Oberfläche, nicht in die Rechnung.
2. **Ein Test, der in der Rot-Probe grün blieb.** Die Sitzungen hiessen
   `k5o-gross`/`k5o-klein` — alphabetisch dieselbe Reihenfolge wie nach Token,
   also bewies der Test nichts. Umbenannt in `k5o-b-viel`/`k5o-a-wenig`, so dass
   die Kennung der Erwartung zuwiderläuft.

**Wächter, die zu Recht ansprangen (4):** `studio-views.spec.ts` (Anzahl, Slugs,
Paketname) und `views-i18n.spec.ts` (Schlüsselzahl, deutsche Beschriftungen).
Die §5.6-Zusage ist dabei **nicht** durch eine höhere Zahl ersetzt worden,
sondern in zwei Listen geteilt — `PORTIERT` (16 aus ALT) und
`OHNE_ALT_VORBILD` (4, je mit Grund), samt Gegenrichtungs-Test. Dieselbe
Disziplin wie `SPEC_AREAS`/`NEUE_BEREICHE` bei K3.

**Rot-Probe, je einzeln abgeschaltet — alle ROT:** Tagesende · Teilsummen-Hinweis
· Strich statt Null · variable Nachkommastellen · Währungs-Prüfung (K5b);
Token-Rang ohne Preise · Deckelung · Beträge je Sitzung addiert ·
Bepreist-vor-unbepreist (K5a).

**Belege:** pytest **3003 passed / 4 skipped** (vorher 2995) · ruff sauber ·
`export_openapi.py --check` grün · `ng test studio` **922** (vorher 897) ·
`ng test ui` 701 unverändert · `npm run check:tokens`: „Jedes gelesene Token ist
definiert."

**Was hier bewusst NICHT gebaut ist:** `/api/usage/session/{id}` hat nach K5
keinen Verbraucher in der Oberfläche — die Sitzungsliste beantwortet „was hat
eine Sitzung gekostet" für die Sitzungen, auf die es ankommt. Eine Kostenspalte
in der Sessions-Ansicht stünde nicht im Plan; sie wäre ein eigener Schritt.

---

## 7. Verifikation je Anforderung

| Anforderung | Beleg |
|---|---|
| Token je Sitzung | K4-Test: Summe über eine Sitzung mit bekannten Zeilen |
| Token je Zeitraum | K4-Test: zwei Züge in verschiedenen Zeiträumen, Filter greift |
| Getrennt nach Eingabe/Cache/Ausgabe | K2-Test: die vier Zahlen stehen einzeln in der Zeile |
| Reasoning berücksichtigt | K1a-Test gegen echte LiteLLM-Typen |
| Preis einstellbar | K3-Test: Seed-Roundtrip + Studio-PUT ändert das Ergebnis |
| Vollständigkeit der Erfassung | K1f-Wächter (AST über alle Aufrufstellen) |
| Keine Regression | volle Suite + ruff + OpenAPI-Diff nach jedem Paket |

## 8. Risiken

* **Preis zum Auswertungszeitpunkt, nicht zum Zug-Zeitpunkt.** Ändert sich ein
  Preis, ändern sich rückwirkend alle Summen. Für eine interne Kostenschau
  richtig, für eine externe Rechnung nicht. Ausweg, falls je gebraucht: den
  Betrag beim Schreiben einfrieren. Bewusst **nicht** jetzt — es verdoppelt die
  Wahrheit (Token **und** Betrag), und niemand hat danach gefragt.
* **DSGVO.** Eine Sitzung ist ein Mensch. `usage_events` speichert keine
  Inhalte, aber ein Verbrauchsprofil je Sitzung. `ON DELETE CASCADE` sorgt
  dafür, dass die Zahlen mit der Sitzung verschwinden. Eine eigene, kürzere
  Frist ist möglich, sobald es eine gibt — heute gibt es keine.
* **Zeilenwachstum.** Etwa so viel wie `messages`. Unkritisch, aber der Index
  auf `created_at` ist Pflicht, sonst wird die Zeitraum-Abfrage mit den Monaten
  langsam.
* **K1 ändert Signaturen quer durch die Dienste.** Jede Änderung ist ein
  zusätzlicher Parameter mit Vorgabewert `None` — bestehende Aufrufer bleiben
  gültig. Trotzdem nach jedem Teilschritt die volle Suite.

## 9. Offene Fragen

**Keine mehr.** Die letzte (K1e) ist am 2026-08-11 gemessen und entschieden —
Begründung im K1e-Abschnitt.

Offen ist nur noch *Arbeit*, keine Frage: K1f (Wächter), K2–K5.

Zwei Dinge, die kein Test zeigen kann und die dem Nutzer gehören:

1. **Ein Live-Zug gegen DB + LLM.** Alle Nähte sind gepinnt, aber dass im
   Betrieb wirklich Zahlen in `debug.token_usage` ankommen, belegt erst ein
   echter Zug. Empfehlung: eine Suche mit einem Filter, den die Fuzzy-Heuristik
   *nicht* trifft (z.B. auf Englisch „worksheets for teachers"), dann
   `per_phase` ansehen — dort müssen `vocab_match` **und** `response` stehen.
2. **Ein Produktbefund aus der K1e-Messung, der nichts mit Kosten zu tun hat:**
   `teacher`/`learner` fehlen als Alias in der Zielgruppe, `Gymnasium`/
   `Oberstufe` in der Bildungsstufe. Heute kostet das je einen LLM-Aufruf mit
   ~400–600 Token, wo eine Alias-Zeile im Vokabular gereicht hätte. Das ist
   Sache des WLO-Vokabulars, nicht dieses Plans — hier nur festgehalten.

*(Die Vertragsfrage zu K4 ist am 2026-08-11 entschieden — Begründung in 5.5.)*

## 10. Review des Geldpfads (2026-08-12) und was daraus wurde

Nach K5 einmal `/better-coding-review` über Erfassung → Schreiben → Preis →
Auswertung → Route. Ergebnis: 0 kritisch, 0 schwer, 4 leicht, 1 Kleinigkeit.
Sauber befunden und hier nur als Beleg festgehalten: `Decimal` durchgehend,
die beiden „davon"-Felder nirgends addiert, beide Routen StudioKey-gesichert,
je ein Index für beide Abfragewege, `ON DELETE CASCADE`.

Vier Befunde behoben, einer **zurückgezogen**:

1. **Der `cached`-Pfad war nur gegen eine selbstgebaute Attrappe gepinnt** —
   der Echt-Typen-Test daneben prüfte allein `reasoning`. Da `cached`
   entscheidet, welcher der beiden Eingabepreise gilt, hätte eine Umbenennung
   bei LiteLLM jeden Cache-Token still zum vollen Preis abgerechnet, bei
   grüner Suite. Neu: `test_cached_wird_aus_echten_litellm_typen_gelesen`
   gegen `PromptTokensDetailsWrapper`. Rot-Probe: mit verstelltem Feldnamen
   `assert 0 == 64`.
2. **Die Buchung besaß die Transaktionsgrenze der ganzen Anfrage.** Sie läuft
   auf der anfragegebundenen Sitzung; ihr Fehlerpfad nahm mit `rollback()`
   alles zurück, was dort sonst noch offen war. Neu: SAVEPOINT
   (`session.begin_nested()`) um die eigenen Zeilen, Sitzungs-Rollback nur
   noch nach einem gescheiterten Commit — da ist die Transaktion ohnehin
   verloren. Belegt gegen die echte Postgres: eine fremde, noch nicht
   committete Zeile überlebt jetzt eine Fremdschlüssel-Verletzung der Buchung
   (vorher war sie weg — genau so fiel der Test ohne den Fix).
3. **`/api/usage/period` nahm jeden Zeitraum an.** Ein Vertipper („2000"
   statt „2026") zog die Gruppierung der ganzen Tabelle nach Python, je
   Sitzung UND Modell, ohne `LIMIT`. Neu: `MAX_PERIOD_DAYS = 366` (ein volles
   Jahr mit Schalttag), 422 mit übersetzter Absage, die die Grenze nennt.
   Kostet **eine** Vertragszeile — die Beschreibung der Route; Eintrag in
   `docs/api/bewusste-vertragszusaetze.md`.
4. **Eine kaputte Preistafel sah aus wie eine ungepflegte.** `load_pricing`
   verschluckte jede Ausnahme und gab die leere Tafel zurück; die Redaktion
   sah nach einem YAML-Tippfehler denselben Bildschirm wie bei einer frischen
   Installation, der Grund stand nur im Log. Neu: `load_pricing()` liefert
   `None` für „unlesbar", die Antwort trägt `price_config_broken`, und die
   Ansicht schreibt einen anderen Satz. Kein Vertragsbruch (die Antwort ist
   `additionalProperties: true`), keine Änderung am Bereichsmodell.
5. **Zurückgezogen: „`0002` fehlt `IF NOT EXISTS`".** Nachgemessen hat `0001`
   **zwölf** `CREATE TABLE`, davon **null** mit Wächter; der eine
   `IF NOT EXISTS` steht auf `CREATE EXTENSION vector` und meint etwas anderes
   (Erweiterungen sind datenbankweit und können echt vorbestehen). `0002` ist
   also konsistent, nicht abweichend — der Befund beruhte auf einem
   überinterpretierten Grep-Treffer.

### Zweite Sitzung (Studio-Ansicht), 2026-08-12

6. **Die Tagesgrenzen lagen in UTC statt in der Zeitzone der Bedienung.** Der
   schwerste Fund der beiden Sitzungen, weil er die Zahlen selbst verfälscht.
   `dayStart`/`dayEnd` hängten ein `Z` an den gewählten Tag, `isoDay` las
   `toISOString().slice(0, 10)`. Gemessen in Europe/Berlin: ein Zug am 12.08.
   um **00:30 Ortszeit** liegt **vor** `2026-08-12T00:00:00Z` und fällt damit
   aus dem Fenster „von 12.08. bis 12.08." heraus, während dasselbe Fenster bis
   **13.08. 01:59 Ortszeit** hineinreicht; die Vorbelegung „bis heute" zeigte
   zwischen Mitternacht und 02:00 Uhr **gestern**. Beides lautlos — eine
   kleinere Summe sieht aus wie eine kleinere Summe. Genau die Fehlerklasse,
   die der Docstring dieses Paars zu beheben behauptete, eine Ebene tiefer.
   Neu: die Grenze wird aus dem ÖRTLICHEN Kalendertag gebaut, `toISOString`
   rechnet um; Unlesbares kommt unverändert zurück statt als `RangeError`
   (der Server weist es dann sichtbar mit 422 ab).
   **Drei Bestandstests pinnten die falsche Form** und wurden korrigiert, nicht
   der Code — sie waren nach dem Code geschrieben. Einer davon prüft jetzt
   bewusst über den **Jahreswechsel**: dort steht Berlin auf +01:00, im August
   auf +02:00, ein festgeschriebenes `Z` wäre also nicht einmal um einen
   konstanten Betrag falsch. Geprüft wird gegen die ORTS-Getter
   (`getHours`/`getDate`), damit die Zusicherung in jeder Zeitzone gilt.
7. **Währungscode serverseitig ungeprüft** (der offene Chip). `formatMoney`
   fing einen `Intl`-`RangeError` ab, der die ganze Ansicht geleert hätte —
   aber die Ursache stand ungeprüft im Bereichsmodell, `currency` war ein
   freier String. Neu: `pattern=r"^[A-Za-z]{3}$"` auf `PricingArea.currency`,
   also derselbe Riegel wie `ge=0` bei den Preisen, an derselben Stelle. Vor
   dem Edit gemessen: `PricingArea` steht **nicht** in den 54 Schemata des
   eingefrorenen Vertrags (die Config-Routen führen untypisierte Dicts), das
   `pattern` kann dort also nichts verschieben — bestätigt durch
   „openapi contract unchanged". Der Rückfall im Frontend bleibt, weil
   `seed_io.import_tree` weiterhin ungeprüft schreibt; sein Kommentar sagt das
   jetzt, statt den Eindruck zu lassen, er sei die einzige Verteidigung.
   Ein am Studio vorbei gespeicherter Unsinn macht die Tafel unlesbar und sagt
   das über `price_config_broken` aus Befund 4 — die beiden greifen ineinander.

**Ausdrücklich geprüft und in Ordnung befunden** (zweite Sitzung): `formatMoney`
rechnet auf der Zeichenkette statt auf einer geparsten Zahl; `moneyDigits`
verträgt Beträge ohne Nachkommastellen und negative; der Betrag ist `aria-live`
mit `aria-atomic` und die Stellen sind beschriftet; das Formular ist ein echtes
`<form>` mit `type="date"`, gebundenen Labels und `required`. Und die neue
422-Meldung aus Befund 3 **erreicht** die Redaktion: `describeApiError` zeigt
`detail` bei jedem Status ≠ 0 roh an (nachgelesen, nicht angenommen).
