# Themenbaum aus einem Dokument: Zahl der Unterpunkte (2026-11-16)

Anlass: Rückmeldung vom 16.11. Beim Themenbaum aus einem Lehrplan hatte die zweite Ebene immer
genau drei Unterpunkte.

## Ursache

- Die obere Ebene schätzt für jeden Punkt die Zahl seiner Unterpunkte (`unterthemen`). Sie sieht
  dabei nur die Gliederung des Dokuments, also nur die Überschriften.
- Der Systemteil gab als Richtwert „möglichst 3 oder mehr“ vor. Das Modell setzte deshalb fast
  überall 3.
- Die zweite Ebene musste dann „genau“ diese Zahl liefern, obwohl sie den Text des Abschnitts
  kennt.

## Was sich ändert

- **Mit Auszug** (Themenbaum aus einem Dokument): Die Schätzung der oberen Ebene ist nur noch ein
  Hinweis.
  - Die zweite Ebene liefert so viele Punkte, wie der Abschnitt Themen trägt: mindestens 2,
    höchstens `UNTERTHEMEN_OBEN` (8).
  - Nennen die Wünsche der Person eine Zahl, gilt diese.
- **Ohne Auszug** (Themenbaum aus einem Thema, Vertiefen, dritte Ebene): Die Schätzung bleibt
  verbindlich („genau“).
- **Systemteil:** „so viele, wie der Stoff des Punkts trägt; umfangreiche Punkte bekommen mehr,
  nicht alle gleich viele“ statt „möglichst 3 oder mehr“.
- **Dritte Ebene (Review, MAJOR):** Die höchstens 24 Aufrufe der dritten Ebene (`EBENE3_HOECHSTENS`)
  verteilen sich jetzt reihum über die oberen Punkte: erst das erste Kind jedes oberen Punkts, dann
  das zweite usw.
  - Vorher galt die Baumreihenfolge. Bei 5 bis 8 Unterpunkten je Punkt hätten nur die ersten drei
    oberen Punkte eine dritte Ebene bekommen.
  - Die Reihenfolge gilt für jeden Entwurf, auch ohne Dokument.
  - Was über den Deckel geht, bleibt `ausstehend` wie bisher.

## Bekannte Grenzen (Review, hingenommen)

- **Knoten-Deckel:** Aus einem Dokument sind bis zu 30 obere Punkte möglich. Mit je 8
  Unterpunkten wären das 270 Knoten, mehr als `HOECHSTENS_KNOTEN` (250). Die letzten oberen Punkte
  bleiben dann ohne oder mit weniger Unterpunkten; sie sind `ausstehend` markiert und lassen sich
  vertiefen. Das ist selten.
- **Schätzung 0:** Schätzt die obere Ebene für einen Punkt 0 Unterpunkte, bekommt er weiter keine
  zweite Ebene, auch wenn sein Abschnitt Stoff hätte. Bewusst so gelassen: Sonst bekäme jeder
  Punkt mindestens zwei Unterpunkte, auch ein echtes Blatt.
- **Antwortlänge:** Acht Unterpunkte mit Beschreibung und Schlagworten brauchen rund 1 000 bis
  1 100 Ausgabe-Token (Grenze 1 600). Das reicht, wird aber öfter ausgeschöpft; ein Aufruf dauert
  etwas länger.
- **Prompt-Cache:** Der Systemteil ist neu. Nach dem Deploy trifft der Cache einmal nicht.

## Geprüft

- Neue Tests:
  - mit Auszug: Obergrenze, Wünsche der Person;
  - ohne Auszug: „genau“;
  - Systemteil;
  - dritte Ebene reihum (vor der Behebung rot).
- `pytest -k "strukturentwurf or themenbaum"`: 336 grün, ruff sauber.
- Ein unabhängiges Review (1 MAJOR, 4 MINOR, 3 NIT): MAJOR und ein MINOR (Zahl in den Wünschen)
  behoben, die genaueren Prüfungen in den Tests nachgezogen, der Rest steht oben.
- **Mit einem echten Lehrplan nicht live geprüft.**

## Deploy

Image neu bauen. Keine Migration, kein `import-config`.
