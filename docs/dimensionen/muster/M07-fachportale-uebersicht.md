# M07 — Fachportale-Übersicht

<!-- ERZEUGT von backend/scripts/export_dimensions.py aus backend/seeds/ — nicht von Hand ändern; Änderungen gehören in den Seed bzw. ins Studio. -->

| Feld | Wert |
|---|---|
| `id` | M07 |
| `label` | Fachportale-Übersicht |
| `short_purpose` | Plural-Frage nach allen Fachportalen / Top-Level-Sammlungen → Liste der Fächer. |
| `priority` | 490 |
| `default_tone` | kollegial |
| `default_length` | standard |
| `response_type` | cards |
| `quick_replies_mode` | speculative |

### Kernregel

Top-Level-Fachportale als Cards rendern (max. 12). Kein Drilldown.

### Werkzeuge

- get_subject_portals

### Quellen

- mcp

### Wann anwenden

- User fragt nach ALLEN Fächern (Plural) — „Welche Fächer gibt es?"
- „Was bietet WLO insgesamt?" / „Liste aller Fachportale"
- Übersichts-Frage ohne konkretes Fach

### Wann nicht

- Konkretes Singular-Fach + Drilldown-Verb („Welche Bereiche unter Mathematik?") → M08
- Material-Suche zu konkretem Thema → M05/M06
- Reine Wissensfrage über WLO → M04

### Auslöser-Phrasen

- Welche Fächer gibt es
- Liste der Fachportale
- Was bietet WLO
- Alle Fächer zeigen
- Übersicht Fächer

### Anti-Muster

- Keine Material-Treffer rendern (das ist M05/M06)
- Bei Singular-Fach mit Drilldown-Verb → M08

### Abgrenzung gegen Nachbarmuster

- **vs**: M08
- **rule**: PLURAL/Übersicht aller Fächer → M07. Singular-Fach mit Drilldown → M08.
- **example**: Welche Fächer gibt es? → M07. Welche Bereiche hat Mathematik? → M08.

- **vs**: M04
- **rule**: Liste der Fachportale (kuratierter MCP-Output) → M07. Wissensfrage „Was sind Fachportale?" → M04.
- **example**: Liste Fachportale → M07. Was bedeutet Fachportal? → M04.

## Anweisung

# M07 — Fachportale-Übersicht

## Wann aktiv
- „Welche Fächer gibt es?", „Was bietet WLO insgesamt?", „Liste der Fachportale"
- **Plural** / Übersichts-Frage ohne ein konkretes Fach

## Verhalten
- `get_subject_portals` aufrufen
- Cards alphabetisch
- Quick-Reply am Ende: „In ein Fach reinschauen?" → führt zu M08
