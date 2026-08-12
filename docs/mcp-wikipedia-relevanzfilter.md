# Relevanz-Prüfung für `get_wikipedia_summary` — Übergabe an den MCP-Server

**Stand:** 2026-08-01 · **Quelle im Chatbot:** `backend/src/boerdi/services/wikipedia_service.py`
(`_normalize` / `_word_match` / `_is_relevant`)

Dieses Dokument beschreibt die Technik, mit der der Chatbot falsche
Wikipedia-Treffer verwirft, damit sie im MCP-Server nachgebaut werden kann.
Es beschreibt **auch die zwei bekannten Schwächen** — wer es nachbaut, sollte
sie nicht mitnehmen.

---

## 1. Warum es das gibt

`get_wikipedia_summary` löst Weiterleitungen sauber auf, prüft aber nicht, ob
der gefundene Artikel **zum gefragten Thema gehört**. Live gemessen am
2026-08-01 gegen `https://wlo-mcp.87.106.195.152.nip.io/mcp`:

| Anfrage | Antwort des Werkzeugs | Bewertung |
|---|---|---|
| `Photosynthese` | Photosynthese | richtig |
| `Bruchrechnen` | **Bruchrechnung** | richtig (Weiterleitung sauber aufgelöst) |
| `Feinoptik` | Feinoptiker | vertretbar (Berufsbezeichnung zum Fach) |
| `Stadt Berlin` | **Bern** | falsch |
| `Dreiecke` | **Dreiecker** (ein Berg im Allgäu) | falsch |
| `Qwertzuiop Blubb` | `found: false` | richtig |

Für einen Chat-Assistenten wäre das unschön. Für **erzeugtes
Unterrichtsmaterial ist es ein Sachfehler mit Rechtsfolge**: der Text bekommt am
Ende automatisch eine Quellenangabe „*Quelle: Wikipedia-Artikel „Bern"
(URL). Inhalte unter CC BY-SA 4.0 verarbeitet.*". Ein Arbeitsblatt über Berlin
würde also die Schweizer Bundesstadt zitieren.

---

## 2. Das Verfahren

Drei Eingaben: `topic` (die Anfrage), `title` (der Artikeltitel, den der Server
zurückgibt), `extract` (der Lead-Absatz). Ergebnis: `true` = passt.

### 2.1 Normalisierung

```
normalize(s):
  1. Unicode-NFKD-Zerlegung
  2. alle kombinierenden Zeichen entfernen   → "ü" wird "u", "é" wird "e"
  3. Kleinschreibung
  4. alles außer [a-z0-9ß ] durch Leerzeichen ersetzen
  5. Mehrfach-Leerzeichen zusammenziehen, trimmen
```

> **Wart im Original:** unsere Zeichenklasse lautet `[^a-z0-9äöüß ]`. Die
> Umlaute darin sind wirkungslos, weil Schritt 2 sie vorher schon zu `a/o/u`
> gemacht hat. Nur `ß` überlebt (es zerlegt nicht). Beim Nachbau: `äöü` in der
> Klasse weglassen, das spart die Verwirrung.

### 2.2 Ganzwort-Vergleich

```
wordMatch(word, text):  " word " ist Teilstring von " text "
```

Absichtlich **nicht** der nackte Teilstring-Test: `"berlin"` steckt in
`"ueberlingen"` (ü-b-**erlin**-gen), ist dort aber kein Wort.

### 2.3 Die Regelkette

Der Reihe nach; die erste zutreffende Regel entscheidet.

```
t  = normalize(topic)
nt = normalize(title)
ne = normalize(extract[0..300])

R0  t leer                                        → false

R1  t == nt  ODER  t enthalten in nt  ODER  nt enthalten in t   → TRUE
    (direkte Enthaltenheit, TEILSTRING — siehe Schwäche A)

    tokens        = t aufgeteilt an Leerzeichen
    contentWords  = tokens mit Länge >= 4, die nicht in STOP stehen

R2  contentWords leer                             → false

R3  tokens.length >= 2 (Mehrwort-Anfrage):
      das LÄNGSTE contentWord muss als GANZES WORT im Titel stehen
      → dessen Ergebnis, Ende

    (ab hier: Einwort-Anfrage, word = contentWords[0])

R4  wordMatch(word, nt) ODER wordMatch(word, ne)  → TRUE

R5  für jedes Titelwort tw mit Länge >= 5:
      a) word länger als tw UND word beginnt mit tw          → TRUE
         ("bruchrechnung" beginnt mit "bruch" → Kompositum)
      b) tw länger als word UND tw beginnt mit word
         UND der Rest ist ein anerkanntes Suffix (Länge >= 2) → TRUE
         ("feinoptik" + "er" → "feinoptiker")

R6  sonst                                          → false
```

**STOP** (Wörter, die allein nichts belegen):
`und, oder, der, die, das, den, dem, des, ein, eine, einer, einem, eines, für,
fuer, klasse, schule, stufe, sek, kl, stadt, land, ort`

Die drei letzten sind wichtig: ohne sie würde „**Stadt** Berlin" schon über das
Wort „Stadt" an jede beliebige Ortschaft andocken.

**SAFE_SUFFIXES** (R5b):
`ung, heit, keit, schaft, tum, lich, bar, isch, iker, iger, haft, lein, chen,
en, es, em, ern, ens, eln, er`

Ein-Zeichen-Anhänge sind **verboten**: aus „Dreiecke" + „r" wird „Dreiecker",
und das ist ein Berg, keine Flexion.

---

## 3. Die zwei Schwächen — bitte nicht mitnehmen

### Schwäche A: R1 ist ein Teilstring-Test und hebelt R5b aus

`normalize("Dreiecke") = "dreiecke"` ist ein **Teilstring** von
`"dreiecker"`. R1 greift und liefert `true` — die sorgfältige Suffix-Prüfung in
R5b, die genau diesen Fall abfangen soll, kommt nie zum Zug.

**Behebung:** R1 nur bei Gleichheit oder bei **Wortgrenzen**-Enthaltenheit
zünden lassen (`wordMatch`), nicht bei nacktem Teilstring. Dann fällt
„Dreiecke"/„Dreiecker" durch bis R5b und wird korrekt verworfen.

### Schwäche B: Verb/Substantiv-Paare fallen durch

`"Bruchrechnen"` vs. `"bruchrechnung"`: R1 nein (keiner enthält den anderen),
R4 nein, R5a nein (`"bruchrechnen"` beginnt nicht mit `"bruchrechnung"`),
R5b nein (`"bruchrechnung"` beginnt nicht mit `"bruchrechnen"` — es scheitert am
`e` vs. `u`). Ergebnis: **verworfen, obwohl der Artikel genau passt.**

**Behebung:** vor R5 einen gemeinsamen Wortstamm vergleichen. Für Deutsch reicht
ein leichtgewichtiger Stemmer (z.B. `snowball`/`german`), der `rechnen` und
`rechnung` auf denselben Stamm bringt. Alternativ eine Liste von
Nominalisierungs-Paaren (`-en` ↔ `-ung`), das deckt den Löwenanteil ab.

---

## 4. Empfehlung für die Server-Schnittstelle

**Den Treffer nicht still wegwerfen, sondern kennzeichnen.** Verschiedene
Aufrufer brauchen Verschiedenes: ein Chat-Assistent kann einen unsicheren
Treffer zeigen und einordnen; eine Material-Erzeugung darf ihn nicht zitieren.

Vorschlag für den JSON-Envelope:

```json
{
  "query": "Stadt Berlin",
  "found": true,
  "relevance": { "verdict": "mismatch", "rule": "R3", "checked": "berlin" },
  "summary": { "title": "Bern", "extract": "…", "url": "…", "lang": "de" }
}
```

`verdict`: `"match"` | `"mismatch"` | `"uncertain"`. Ein zusätzlicher
Eingabeparameter `relevanceCheck` (`"off"` | `"annotate"` | `"enforce"`,
Standard `"annotate"`) lässt jeden Aufrufer selbst entscheiden — `"enforce"`
liefert bei `mismatch` dann `found: false` mit `reason: "irrelevant"`.

Das ist auch für uns der bessere Vertrag: wir könnten den eigenen Filter
abschalten, sobald `enforce` da ist, und hätten die Prüfung an genau einer
Stelle statt in jedem Client.

---

## 5. Testfälle

Erwartungswerte für eine **korrigierte** Fassung (Schwäche A und B behoben):

| topic | title | erwartet | greift bei |
|---|---|---|---|
| `Photosynthese` | `Photosynthese` | match | R1 (Gleichheit) |
| `Bruch` | `Bruch (Mathematik)` | match | R1 (Wortgrenze) |
| `Bruchrechnen` | `Bruchrechnung` | match | Stemming (Schwäche B) |
| `Feinoptik` | `Feinoptiker` | match | R5b (`er`) |
| `Bruchrechnung` | `Bruch Grundlagen` | match | R5a (Kompositum) |
| `Osmose` | `Diffusion` (Extract nennt Osmose) | match | R4 (Extract) |
| `Stadt Berlin` | `Berlin Hauptstadt` | match | R3 |
| **`Stadt Berlin`** | **`Bern`** | **mismatch** | R3 |
| **`Stadt Berlin`** | **`Stadtbergen`** | **mismatch** | R3 (Wortgrenze) |
| **`Dreiecke`** | **`Dreiecker`** | **mismatch** | R5b (1-Zeichen-Suffix) |
| `Photosynthese` | `Astronomie` | mismatch | R6 |
| `die der und` | `xyz` | mismatch | R2 (nur Stoppwörter) |

Die drei fett gesetzten Zeilen sind die, an denen sich die Umsetzung entscheidet.
Unsere aktuelle Fassung besteht die `Dreiecker`-Zeile **nicht** (Schwäche A) und
die `Bruchrechnen`-Zeile **nicht** (Schwäche B).

---

## 6. Referenz

Unsere Fassung steht vollständig in
`backend/src/boerdi/services/wikipedia_service.py` (Funktionen `_normalize`,
`_word_match`, `_is_relevant`), die Testfälle in
`backend/tests/test_wikipedia_service.py`. Sie ist unverändert aus dem
Altsystem übernommen; die Sprint-7-Notiz im Code beschreibt, warum
Ein-Zeichen-Suffixe verboten wurden.
