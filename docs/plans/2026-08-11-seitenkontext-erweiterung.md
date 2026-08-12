# Seitenkontext-Erweiterung — Suche, fremde Seite, eigene Startseite

Stand 2026-08-11 · Entwurf zur Abnahme · Nutzer-Auftrag vom selben Tag

## Ziel

Der Chatbot soll **jede** Seite erkennen, auf der er sitzt — nicht nur Sammlung,
Inhalt und Themenseite —, das kurz im Chat sagen und bei einer fremden Seite die
Erschliessung anbieten, nachdem er geprüft hat, ob es sie in WLO schon gibt.

## Ausgangslage (gemessen, nicht angenommen)

Der grösste Teil steht bereits — aus dem Seitenkontext-Paket R6. **Was hier
gebaut wird, ist eine Erweiterung, kein Neubau.**

| Baustein | Datei | Stand |
|---|---|---|
| Erkennung aus URL/DOM | `frontend/projects/ui/src/page-context/page-context-detector.ts` | erkennt `content` · `collection` · `topic` · `subject` · `search` · `other` |
| Metadaten je Objekt | `backend/src/boerdi/services/page_context.py` | über MCP, TTL-Cache je Seiten-Signatur |
| Meldung im Chat | `backend/src/boerdi/graph/nodes/context_greeting.py` | LLM-frei, Text + Chips aus dem Seed |
| Texte/Chips, zweisprachig | `backend/seeds/01-base/context-actions.yaml` | Studio-pflegbar |
| **Abschalter** | ebenda, `enabled: true` | **existiert schon** (`context_greeting.py:160`) |

### Am echten Beispiel belegt (2026-08-11)

Der Nutzer lieferte die Staging-Adresse der Sammlung „Geometrische Optik". Sie
ist der harte Fall, weil sie **drei** Signale gleichzeitig trägt — `q=Optik`
(sieht aus wie Suche), `id=<uuid>` (die Sammlung), `sort=<JSON>`:

```
…/edu-sharing/components/collections?sort=%7B…%7D&q=Optik&id=f35c17d1-…&scope=TYPE_EDITORIAL
```

Beide Hälften der Kette gemessen, nicht angenommen:

* **URL ⇒ Seitenart:** `page_kind='collection'`, `collection_id='f35c17d1-…'`,
  `search_query='Optik'` als *Filter*. Der Sammlungs-Zweig steht bewusst **vor**
  dem generischen `?q`-Zweig; stünde er dahinter, verlöre der Bot hier die
  Sammlung. Gepinnt in `page-context-detector.spec.ts` mit genau dieser Adresse.
* **ID ⇒ Metadaten:** Live-Aufruf `get_node_details` liefert „Geometrische
  Optik", Physik, Sekundarstufe I, `nodeType: collection`.

Der verbundene MCP-Server zeigt auf **Staging** — die zurückgegebenen URLs
tragen `repository.staging.openeduhub.net`.

**Was heute schon passiert:** wer auf dieser Seite eine Unterhaltung fortsetzt,
bekommt „Du bist gerade in der Sammlung „Geometrische Optik" …" samt Chips. Was
NICHT passiert: dieselbe Meldung beim ersten Laden — siehe Lücke 3.

### Die drei Lücken

1. **`search` wird erkannt, meldet sich aber nicht.** Zwei Sperren nennen
   dieselben drei Arten — und **beide** müssen fallen, sonst passiert nichts:
   * Widget: `shell/lifecycle.ts::_maybeSendContextPing` → `addressable`
   * Backend: `context_greeting.py:48` → `_GREETABLE_KINDS`
2. **Der Erkenner sieht nie den Hostnamen an.** Nur Pfad, Query, DOM. Eigene
   Startseite und fremde Webseite landen beide auf `other` — die Unterscheidung,
   die eine Erschliessung auslösen müsste, gibt es nicht.
3. **Beim ersten Laden schweigt die Meldung.** `context_greeting.py:135`
   (`if not history: return None`) und der Auslöser im Widget hängt an
   `_afterResume()` / `onSpaContextChange()` — nie am Erstaufruf.

## Entscheidungen des Nutzers (2026-08-11)

| Frage | Entscheid |
|---|---|
| Auch beim ersten Laden melden? | **Ja** — mit der Auflage, dass Begrüssung und Kontextmeldung zu EINER Nachricht verschmelzen |
| Fremde Seite | **Erkennen und Erschliessung anbieten**, „erfordert aber Dublettencheck im Repo auf URL- und Titel-Basis" |
| Vorgehen | Erst Plan, dann bauen |

Der Dublettencheck ist **keine neue Mechanik**: M20 schreibt ihn bereits vor
(„Vor JEDER Neuanlage … mit Titel und Adresse in `search_wlo_content` bzw.
`search_wlo_all` suchen"). Dieser Plan baut nur die Auslöse-Naht dorthin.

## Abgrenzung

**Drin:** Seitenarten `search`, `home`, `external`; Meldung beim ersten Laden;
Hostname-Unterscheidung; Dublettenprüfung vor dem Erschliessungs-Angebot; Texte
und Chips im Seed, zweisprachig; Abschalter greift auch für die neuen Arten.

**Draussen, bewusst:**
* `subject` (Fachportal) — wird erkannt, bleibt vorerst stumm. Eigene
  Produktfrage, kein Teil des Auftrags.
* Die Erschliessung selbst. Der Chip löst M20 aus; M20 ist gebaut.
* Automatisches Anlegen ohne Klick. Kuration bleibt zweistufig.

## Ansatz

Drei Alternativen für die Verschmelzung beim ersten Laden wurden erwogen:

| | Wie | Warum nicht / doch |
|---|---|---|
| A | Widget unterdrückt die Begrüssung, wenn die Seite erkannt ist | Fällt der Ping aus, bekommt die Person **gar keine** Begrüssung |
| B | Erst Begrüssung zeigen, Kontextmeldung ersetzt sie danach | Sichtbares Flackern, und der Verlauf trägt kurz eine falsche Zeile |
| **C** | **Begrüssung zurückstellen, bis der Ping antwortet — Inhalt ⇒ zeigen, sonst die normale Begrüssung** | **Gewählt.** Genau eine Nachricht, kein Flackern, und der Ausfall ist abgedeckt |

Für die Hostname-Frage: die Entscheidung „eigen oder fremd" gehört **ins
Backend gegen eine Studio-pflegbare Liste**, nicht in den Widget-Code — sonst
steckt eine Betriebs-Tatsache in einem Bundle, das nur bei einem Neubau
aktualisiert wird (der häufigste Deploy-Fehler dieses Projekts).

**Datenschutz-Schnitt — ZURÜCKGENOMMEN (gemessen 2026-08-11).** Der Entwurf sah
vor, nur den **Hostnamen** zu schicken, nicht die volle Adresse: Query-Parameter
fremder Seiten können personenbezogene Daten tragen.

Die Messung widerlegt die Prämisse. `detectPageContext` schickt **heute schon**
`page_text` — bis zu 1500 Zeichen des sichtbaren Seitentextes — für jede Seite
ausser der Suche, also auch für fremde (`page-context-detector.ts:300-305`). Die
Adresse zurückzuhalten, während der Text der Seite reist, wäre Theater: die
Adresse ist strikt **weniger** Preisgabe als das, was ohnehin geht. Und ohne sie
ist die Erschliessung unmöglich — M20 braucht eine URL, ein Hostname allein
führt auf die falsche Seite.

Also: das Widget schickt `page_url` (Aufgabe 7), die Dublettenprüfung läuft im
Zug. Die Sperre im Knoten ist trotzdem gebaut — ohne `page_url` unterbleibt der
Aufruf ganz, statt auf den blossen Hostnamen zu prüfen.

> **Getrennt zu entscheiden, hier bewusst NICHT angefasst:** ob `page_text` von
> beliebigen fremden Seiten überhaupt unaufgefordert reisen soll. Das ist
> Bestandsverhalten seit R6 und eine eigene Produktfrage, kein Teil dieses Plans.

## Architektur

### Datenfluss

```
Widget                              Backend
──────                              ───────
page-context-detector
  page_kind: search|home|external
  page_host: "example.org"      ──▶  page_context_enrich
  (KEINE volle URL)                    └─ resolve_page_context (Metadaten, TTL)
                                            │
lifecycle._maybeSendContextPing             ▼
  addressable += search|home|external  context_greeting
  page_event: context_open_initial       ├─ Sperren: Art ∈ GREETABLE, Text da
    (beim ersten Laden)                  ├─ external ⇒ Dublettenprüfung (MCP)
                                         └─ Text + Chips aus context-actions.yaml
                                              │
  eine Nachricht rendern            ◀─────────┘
```

### Dateien

| Datei | Zuständigkeit | Änderung |
|---|---|---|
| `ui/src/page-context/page-context-detector.ts` | Erkennung | `page_host` ergänzen; `page_kind` um `home`/`external` — **entschieden vom Backend**, das Widget liefert nur den Hostnamen und `other` |
| `ui/src/shell/lifecycle.ts` | Auslöser | `addressable` erweitern; Erstaufruf-Pfad mit zurückgestellter Begrüssung |
| `ui/src/controllers/context-greeting.controller.ts` | Ping | Rückfall-Begrüssung, wenn die Antwort leer ist |
| `backend/domain/page_host.py` | **neu** | Reine Einordnung: Hostname + Liste ⇒ `home`/`external`/`''`. Kein I/O, nutzt `guide_mode.host_matches_pattern`. Nicht in `page_context.py` — die trägt auf 597 Zeilen schon Auflösen **und** Rendern |
| `backend/graph/nodes/page_context_enrich.py` | Aufbereitung | Ruft die Einordnung mit der gepflegten Liste, **vor** dem Auflösen — so sehen Resolver, Meldung und Prompt denselben Wert |
| `backend/graph/nodes/context_greeting.py` | Meldung | `_GREETABLE_KINDS` erweitern; History-Sperre nur noch für `context_open`, nicht für `context_open_initial`; Dublettenzweig |
| `backend/services/page_duplicate.py` | **neu** | Reine Naht: Adresse+Titel ⇒ `search_wlo_content`/`search_wlo_all` ⇒ Treffer ja/nein. Eigene Datei, weil es eine zweite Zuständigkeit ist (`context_greeting.py` hat 216 Zeilen und trägt schon eine) |
| `backend/seeds/01-base/context-actions.yaml` | Texte/Chips | `own_hosts`, Texte + Chips für `search`/`home`/`external`, je DE+EN |

### Schnittstellen

```python
# backend/services/page_duplicate.py
async def find_existing_by_url(url: str, title: str) -> dict | None:
    """Erster WLO-Treffer zu dieser Adresse oder diesem Titel, sonst None.

    Rückgabe: {"node_id": str, "title": str, "matched_on": "url"|"title"}
    """
```

```yaml
# context-actions.yaml — neue Schlüssel
context_actions:
  # ACHTUNG, am Nutzer-Beispiel 2026-08-11 gefunden: die Repository-Hosts
  # gehören ZWINGEND dazu, nicht nur die WordPress-Seiten. Auf
  # repository.staging.openeduhub.net gibt es Seiten, die auf KEIN Muster
  # passen (z.B. /edu-sharing/components/workspace) — die fielen sonst auf
  # `external`, und der Bot böte an, eine WLO-eigene Seite „in WLO
  # aufzunehmen". Gepinnt von einem Test mit genau dieser Adresse.
  own_hosts:
    - wirlernenonline.de
    - wissenlebt.online
    - repository.staging.openeduhub.net
    - redaktion.openeduhub.net
  greetings:
    search:   "Du suchst gerade nach „{query}“. Ich kann die Suche verfeinern …"
    home:     "Du bist auf der Startseite von {host}. Womit fangen wir an?"
    external: "Du bist auf einer Seite ausserhalb von WLO ({host})."
  greetings_en: { … dieselben Schlüssel }
  pills:
    external:
      - { label: "Diese Seite in WLO aufnehmen", label_en: "Add this page to WLO", kind: action, action: erschliessen }
```

### Abhängigkeitsrichtung

`page_duplicate.py` liegt unter `services/` und ruft den vorhandenen
MCP-Client — kein neuer Weg nach aussen, keine Zyklen. `context_greeting`
(Knoten) hängt von `services/`, nie umgekehrt.

## Nicht-funktionale Festlegungen

* **Kosten.** Die Dublettenprüfung kostet **einen** MCP-Aufruf, wenn die Adresse
  im Bestand liegt, und **zwei**, wenn nicht (dann folgt die Titel-Suche).
  ~~ein Aufruf~~ — korrigiert beim Bau von Aufgabe 2: der Nutzer verlangt „auf
  URL- **und** Titel-Basis", und der Titel lässt sich nicht in dieselbe Abfrage
  packen, ohne beide zu verwässern. Sie läuft nur bei `external`, nur wenn die
  Meldungen eingeschaltet sind, und nur einmal je Seiten-Signatur (der
  TTL-Cache aus `page_context.py` deckt das ab). Ohne diese Deckelung feuerte
  sie bei jedem Blättern.
* **Datenschutz.** Nur der Hostname reist unaufgefordert (siehe oben). Keine
  volle Fremd-Adresse in Logs.
* **i18n.** Jeder neue Text steht in `greetings` **und** `greetings_en`;
  `label_en` ist bei `kind: text` kein Schmuck, sondern die gesendete Nachricht.
* **Barrierefreiheit.** Die Meldung ist eine normale Bot-Nachricht im
  bestehenden Verlauf — sie erbt dessen Live-Region und Fokusverhalten. Kein
  neues Bedienelement.
* **Abschalter.** `enabled: false` schaltet **alle** Arten ab, auch die neuen.
  Das wird geprüft, nicht angenommen.

## Risiken

| Risiko | Gegenmittel |
|---|---|
| **Eigene Seite als „fremd" eingestuft** ⇒ der Bot bietet an, WLO in WLO aufzunehmen | `own_hosts` enthält die Repository-Hosts (siehe Kommentar dort); Test mit `…/components/workspace` auf dem Staging-Host |
| **Host-Einordnung überschreibt eine erkannte Seitenart** ⇒ die Sammlung „Geometrische Optik" läge auf einem eigenen Host und würde zu `home` — Metadaten und Kontext-Chips wären weg (beim Bau von Aufgabe 3 gefunden) | Die Einordnung greift **nur** bei `''`/`other`; rot-grün belegt (ohne die Sperre fällt genau dieser eine Test, mit `home` statt `collection`) |
| **Falsche Dublette** ⇒ der Bot sagt „kennen wir schon" und verschweigt das Angebot | Ein Suchtreffer zählt nur, wenn er die Adresse bzw. exakt den Titel trägt; „ähnlicher Titel" und „anderer Pfad" sind eigene Tests |
| ~~Zwei~~ **DREI** Sperren, eine geändert ⇒ stille Wirkungslosigkeit. Die dritte ist `_CONTEXT_ACTIONS_PAGE_KINDS` im Loader — sie wirft unbekannte Arten aus der Config, bevor der Knoten sie sieht (beim Bau von Aufgabe 4 gefunden) | Backend-Seite gepinnt: ein Test prüft Loader-Liste und `_GREETABLE_KINDS` gegeneinander. Die Widget-Liste kommt in Aufgabe 8 dazu |
| **Alle neuen Arten teilen einen Entdopplungs-Schlüssel** ⇒ nach der ersten Meldung schweigt jede weitere Suche/fremde Seite (beim Bau von Aufgabe 4 gefunden) | Eigener `_greeting_signature` aus Art + Gegenstand statt `_current_context_signature`; drei Tests fahren zwei verschiedene Suchen, zwei fremde Seiten und die Mischung |
| **Toter Chip**: eine Beschriftung, die kein Muster auslöst | Die `external`-Chips sind wörtlich M20s `trigger_phrases` |
| Erstaufruf bringt zwei Nachrichten | Aufgabe 6 pinnt „genau eine" — nicht „mindestens eine" |
| Fremde Seite auf jedem Blättern ⇒ MCP-Last | Cache je Signatur; Test misst die Aufrufzahl |
| `page_event` ist im eingefrorenen Vertrag getypt | **Aufgabe 1 prüft das zuerst.** Ist es ein Enum, wird der Erstaufruf über ein vorhandenes Feld unterschieden statt über einen neuen Wert |

## Aufgaben

### Phase 1 — Fundament (Backend, ohne sichtbare Wirkung) — ✅ fertig 2026-08-11

**Schritt 0: `/better-coding-workflow` aufrufen.**

1. ✅ **Vertrag geprüft — beide neuen Signale sind gratis.** `page_event` ist
   `str | None` (`api/schemas.py:168`), im eingefrorenen Vertrag
   `anyOf: [string, null]` — **kein Enum**. `page_context` ist
   `dict[str, Any]` mit `additionalProperties: true`. Also kosten weder der
   neue Wert `context_open_initial` noch der neue Schlüssel `page_host` eine
   Vertragsänderung; **der Ausweichweg aus dem Risiko-Abschnitt entfällt** und
   Aufgabe 5 darf den geraden Weg gehen. `export_openapi.py --check` meldet
   nach Phase 1 `openapi contract unchanged`.
2. ✅ **`services/page_duplicate.py`** mit `find_existing_by_url` (12 Tests).
   **Vor dem Bau am echten Staging-MCP gemessen** statt angenommen: eine
   Volltext-Suche mit der kompletten URL findet den Knoten exakt (`total: 1`),
   eine unbekannte URL liefert sauber `total: 0` ohne Rauschen. Deshalb ist die
   Adresse das starke Signal und der Titel nur der Rückfall — und deshalb wird
   die Adresse zuerst gefragt (siehe Kosten-Korrektur oben).
   Gegen die gefährliche Richtung gepinnt: ein Treffer zählt nur, wenn der
   gefundene Knoten die Adresse (bzw. exakt den Titel) wirklich trägt — die
   Rangfolge der Suche allein gilt nicht als Beweis, sonst verschwiege der Bot
   das Erschliessungs-Angebot für eine Seite, die es gar nicht gibt.
3. ✅ **Host-Einordnung** — **abweichend vom Entwurf nicht in `page_context.py`**:
   die Datei hat 597 Zeilen und trägt schon zwei Zuständigkeiten (Auflösen +
   Rendern). Die Einordnung ist rein (kein I/O) und liegt darum in
   `domain/page_host.py` (`classify_page_host`, 11 Tests); sie nutzt den
   vorhandenen `guide_mode.host_matches_pattern` statt eines zweiten
   Host-Abgleichs. Gerufen wird sie im Knoten `page_context_enrich` — dort, wo
   der Seitenkontext ohnehin aufbereitet wird, **vor** dem Auflösen und vor
   `context_greeting`, sodass Resolver, Meldung und Prompt denselben Wert sehen.
   **Dabei gefunden und gepinnt:** die Einordnung darf eine bereits erkannte
   Seitenart NIE überschreiben (neue Zeile in der Risiko-Tabelle).

### Phase 2 — Meldung erweitern — ✅ fertig 2026-08-11

**Schritt 0: `/better-coding-workflow` aufrufen.**

4. ✅ **Drei neue Arten begrüßbar** + Seed-Texte und Chips, DE+EN.
   **Es gab eine DRITTE Sperre, nicht zwei:** `_CONTEXT_ACTIONS_PAGE_KINDS` im
   Loader (`config_loader/widget.py`). Was dort fehlt, wirft der Loader aus der
   Config, **bevor** der Knoten es sieht — ein gepflegter Seed-Text wäre
   wirkungslos angekommen. Ein Test prüft Loader-Liste und `_GREETABLE_KINDS`
   jetzt gegeneinander.
   Zweiter Befund: die alte Sperre 3 („aufgelöste Metadaten") passt nur auf
   Seiten, die ein WLO-Objekt SIND. Die neuen drei haben keinen Knoten, also
   wurde sie zu `_greeting_fields` verallgemeinert — Gegenstand ist der
   Suchbegriff (`{query}`) bzw. der Hostname (`{host}`).
   **Defekt in der eigenen Arbeit gefunden und behoben:** die Entdopplung nutzte
   `_current_context_signature`, die nur Knoten-IDs und Slugs liest. Für alle
   drei neuen Arten sind die leer ⇒ sie teilten sich EINEN Schlüssel und
   blockierten einander nach der ersten Meldung (eine zweite Suche wäre stumm
   geblieben). Eigener `_greeting_signature` mit Art + Gegenstand; 3 Tests.
5. ✅ **Erstaufruf-Sperre.** Eigenes Ereignis `context_open_initial`; die
   History-Prüfung gilt nur noch für `context_open`. Die übrigen Sperren gelten
   weiter — sonst wäre der Erstaufruf eine Hintertür.
6. ✅ **Dublettenzweig für `external`** — mit **zwei Korrekturen am Entwurf**:
   * `kind: action, action: erschliessen` gibt es nicht. Registriert sind nur
     `browse_collection`, `curate_collection`, `generate_learning_path`; der
     Chip wäre eine tote Schaltfläche gewesen. Richtig ist `kind: text` mit
     M20s **wörtlicher** Auslösephrase „Nimm diese Seite in WLO auf" — bei
     `text` IST die Beschriftung die gesendete Nachricht.
   * **Drei Zweige fallen auf zwei zusammen.** Der Negativ-Text behauptet nichts
     über Dubletten („Ich kann mir die Seite ansehen und sie vorschlagen"), also
     ist „nichts gefunden" dieselbe ehrliche Aussage wie „konnte nicht fragen".
     Ein eigener Fehlertext wäre eine Unterscheidung ohne Unterschied.
   Die Dubletten-Fassung ist bewusst **keine** Seitenart (eigene Config-Felder
   `duplicate_greeting`/`duplicate_pill_label`, je DE+EN) — als Seitenart könnte
   ein Widget sie als `page_kind` senden und würde begrüßt.

### Phase 3 — Widget — ✅ fertig 2026-08-11

**Schritt 0: `/better-coding-workflow` + `/better-coding-frontend` aufrufen.**

7. ✅ **`page_host` UND `page_url` im Erkenner.** ~~nur Hostname~~ — siehe die
   zurückgenommene Datenschutz-Festlegung oben. Angehängt an EINER Stelle
   (`_detectFromUrl` umschliesst jetzt `_classifyUrl`) statt in acht
   Rückgabepfaden: einer, an dem man es richtig machen kann, keiner zum
   Vergessen. Der Host-Agnostik-Test schlug an und wurde **geschärft**, nicht
   entschärft: verglichen wird die *Einordnung*; dass Host und Adresse dem
   Ursprung folgen, ist jetzt ein eigener Test.
8. ✅ **Ping-Gate erweitert** — **abweichend vom Entwurf keine Spiegelung von
   `_GREETABLE_KINDS`.** `home`/`external` setzt der Erkenner NIE; beim Widget
   heissen sie `other`. Ein Gate, das die Backend-Liste spiegelte, pingte auf
   einer fremden Seite also nie und liesse das Backend gar nicht zu Wort kommen.
   Die Bedingung lautet „**könnte** begrüssbar sein": IDs/Objekt-Arten wie
   bisher, `search` nur mit Begriff, `other` nur mit Hostnamen, `subject`
   bewusst stumm (`shouldSendContextPing`, 5 Tests).
   Der Kreuz-Test liest die benannte Liste `PING_COVERS_BACKEND_KINDS` aus der
   TS-Datei und vergleicht sie mit `_GREETABLE_KINDS` (Muster aus
   `test_widget_router.py`). **Rot-grün belegt:** ein entfernter Eintrag lässt
   ihn fallen.
9. ✅ **Zurückgestellte Begrüssung** (Ansatz C). `sendContextPing` nimmt jetzt
   den Ereignisnamen und meldet zurück, **ob** es gerendert hat — daran hängt
   der Erstaufruf seine Standard-Begrüssung auf. Vier Fälle gepinnt: Ping mit
   Inhalt ⇒ genau eine Nachricht (die Kontextmeldung) · leere Antwort ⇒ normale
   Begrüssung · Ping-Fehler ⇒ normale Begrüssung (nie gar keine) · laufende
   Tour ⇒ normale Begrüssung ohne Ping (sonst Kollision über `isLoading`).

**Wartezeit, geprüft statt angenommen:** während der Ping läuft, ist der Verlauf
leer. Das Eingabefeld steht derweil auf `chat.input.thinking` und ist gesperrt —
die Wartezeit ist sichtbar und nicht als Fehler lesbar. Deshalb kein Zeitlimit
und keine Verwerf-Mechanik; ein hängender Rundlauf bleibt Sache der HTTP-Schicht
(unter „Bekannte Grenzen").

### Phase 4 — Abnahme

10. Gesamt-Tore: `ruff` · `pytest -q` · `export_openapi.py --check` ·
    `npx ng test ui` · `npx ng test studio` · `npm run build:widget` ·
    **`npx playwright test`**.

    ⚠️ **Die E2E-Suite fehlte in dieser Liste — und genau sie hat den Bruch
    gefunden.** Nachgetragen 2026-08-11, nachdem sie beim Abnahme-Lauf eines
    ANDEREN Plans (`2026-08-11-mcp-anmeldung-knopf`) zum ersten Mal wieder
    lief: **10 von 43 rot**. Die Unit-Tests waren grün, weil sie mit dem Umbau
    mitgezogen wurden; die E2E-Suite prüft von aussen und war deshalb die
    ehrlichere. Lehre: ein Gate, das eine Verhaltensänderung erwischen könnte,
    gehört in die Liste — sonst wird es genau dann nicht gefahren, wenn es
    zählt.

10a. ✅ **E2E an die neue Absicht angeglichen** (2026-08-11, 44/44 grün).

    Ursache aller 10: seit `_greetOnFirstLoad` pingt **jede frische Sitzung**
    beim Öffnen (`shouldSendContextPing` genügt der Hostname). Damit lag der
    Ping auf `chatRequests()[0]`, wo die Tests ihren eigenen Zug erwarteten,
    und die Ping-Antwort ersetzte die Config-Begrüssung.

    Drei Änderungen, keine davon am Produktivcode:
    * **Harness wirklichkeitsnah**: ein Ping (`environment.page_event`)
      bekommt eine **leere** Antwort statt der Standard-Antwort — im Betrieb
      sagt das Backend zu einer beliebigen Seite meist nichts — und **nimmt
      der Warteschlange nichts weg**, sonst schnappte er die für den nächsten
      Zug hinterlegte Antwort weg. Wer die Kontextmeldung sprechen lassen
      will, setzt `pingReply`.
    * **`turnRequests()` / `waitForTurns()`**: dieselbe Sicht ohne Pings, für
      alle Tests, die „mein Zug" meinen. `chatRequests()` bleibt vollständig.
    * **Zwei Tests pinnten die ALTE Absicht** („eine FRISCHE Session pingt
      nie", „eine Seite ohne Kontext pingt nicht") — sie halten jetzt die
      neue: Erstaufruf pingt mit `context_open_initial`, eine Seite ohne IDs
      pingt wegen des Hostnamens, und die Auflage „genau EINE Nachricht" ist
      in beiden Richtungen gepinnt (Ping spricht ⇒ er IST die Begrüssung;
      Ping schweigt ⇒ normale Begrüssung).
11. **Seed-Import** — ohne ihn wirkt keine der Textänderungen.
12. Kleiner Live-Smoke je neuer Seitenart. Golden-Lauf: Nutzer.

## Abnahmekriterien

| Anforderung | Nachweis |
|---|---|
| Suche meldet sich | Test Aufgabe 4 + Live-Smoke |
| Fremde Seite wird erkannt | Test Aufgabe 3 |
| Erschliessung wird angeboten | Test Aufgabe 6, Zweig „kein Treffer" |
| Dublette wird vorher geprüft | Test Aufgabe 6, Zweig „Treffer" |
| Eigene Startseite sagt „Du befindest Dich auf …" | Test Aufgabe 4 |
| Auch beim ersten Laden | Test Aufgabe 5 + 9 |
| Genau EINE Nachricht | Test Aufgabe 9 |
| Abschaltbar | Test Aufgabe 4, `enabled: false` |
| Volle Fremd-Adresse reist nicht unaufgefordert | Test Aufgabe 7 |

## Offene Punkte

Keine. Die Vertragsfrage aus Aufgabe 1 ist als **erste** Aufgabe eingeplant und
hat einen benannten Ausweichweg, falls `page_event` getypt ist.
