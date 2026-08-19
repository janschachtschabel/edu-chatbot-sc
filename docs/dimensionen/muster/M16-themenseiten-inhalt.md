# M16 — Themenseiten-Inhalt

<!-- ERZEUGT von backend/scripts/export_dimensions.py aus backend/seeds/ — nicht von Hand ändern; Änderungen gehören in den Seed bzw. ins Studio. -->

| Feld | Wert |
|---|---|
| `id` | M16 |
| `label` | Themenseiten-Inhalt |
| `short_purpose` | Inhalte EINER konkreten Themenseite nach Schwimmlinien zeigen (Auszug) + Absprung. |
| `priority` | 486 |
| `default_tone` | kollegial |
| `default_length` | kurz |
| `response_type` | cards |

### Kernregel

Inhalte EINER bestimmten Themenseite, nach Schwimmlinien gruppiert (max. 3 je Box, „(Auszug)") + Absprung-Button auf die Themenseite. KEINE normalen Sammlungs-/Inhalts-Boxen.

### Werkzeuge

- get_topic_page_content

### Quellen

- mcp

### Wann anwenden

- User will sehen, was AUF einer KONKRETEN Themenseite ist / deren Inhalte
- Öffnen/Anzeigen-Verb + Themenseite: „zeig mir die Inhalte der Themenseite X", „was ist auf der Themenseite X", „öffne die Themenseite X"
- User klickt „Inhalte dieser Themenseite zeigen" an einem Themenseiten-Treffer

### Wann nicht

- User sucht Themenseiten ZU einem Thema (Liste/Auswahl) → M06
- Konkreter Material-/Treffer-Wunsch zu einem Thema → M05/M06
- Sub-Themen/Aufbau einer normalen Sammlung navigieren → M08

### Auslöser-Phrasen

- Inhalte der Themenseite X
- Was ist auf der Themenseite X
- Zeig mir die Themenseite X
- Öffne die Themenseite X
- Was steht auf der Themenseite X

### Anti-Muster

- Liste von Themenseiten zu einem Thema → M06
- Allgemeine Materialsuche zu einem Thema → M05/M06
- Wissensfrage über das Thema → M04

### Abgrenzung gegen Nachbarmuster

- **vs**: M06
- **rule**: Inhalte EINER bestimmten Themenseite anzeigen → M16. Themenseiten zu einem Thema SUCHEN (Liste) → M06.
- **example**: Was ist auf der Themenseite Nachhaltigkeit? → M16. Gibt es Themenseiten zu Nachhaltigkeit? → M06.

- **vs**: M08
- **rule**: Schwimmlinien-Inhalte einer Themenseite → M16. Sub-Sammlungen/Aufbau einer normalen Sammlung → M08.
- **example**: Inhalte der Themenseite Klimawandel → M16. Wie ist die Mathematik-Sammlung gegliedert? → M08.

## Anweisung

# M16 — Themenseiten-Inhalt

## Wann aktiv
- „Zeig mir die Inhalte der Themenseite X", „Was ist auf der Themenseite X?", „Öffne Themenseite X"
- Folge-Klick „Inhalte dieser Themenseite zeigen" an einem Themenseiten-Treffer (M06)

## Pipeline (deterministisch im Backend)
1. `get_topic_page_content(query=thema)` → **ein** Aufruf: der Server sucht die passende Themenseite selbst und liefert direkt ihre Schwimmlinien mit echten Inhalts-Karten. Steht der Nutzer schon auf einer Themenseite, geht deren `collectionId` statt `query` hinein — die ist genauer als jede Auflösung über den Themen-Text.
2. Findet der Server keine Seite, nennt er den Grund (`reason`); daraus wird ein freundlicher Hinweis + Such-Angebot.
3. Anzeige: je Schwimmlinie eine Box „<Überschrift> (Auszug)" (max. 3 Karten) + Absprung-Button auf die Themenseite

## Verhalten
- **Antwort-Text kurz** (1–2 Sätze): nennt die Themenseite + dass es ein Auszug ist; die Boxen tragen den Inhalt.
- **KEINE** normalen Sammlungs-/Inhalts-/Themenseiten-Boxen — nur die Schwimmlinien-Boxen + Absprung.
- Wahrheitspflicht: nur über die tatsächlich gezeigten Schwimmlinien/Karten sprechen.
