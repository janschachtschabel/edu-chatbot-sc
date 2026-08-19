# M06 — Material-Suche Cascade

<!-- ERZEUGT von backend/scripts/export_dimensions.py aus backend/seeds/ — nicht von Hand ändern; Änderungen gehören in den Seed bzw. ins Studio. -->

| Feld | Wert |
|---|---|
| `id` | M06 |
| `label` | Material-Suche Cascade |
| `short_purpose` | Thema vorhanden, Filter unklar oder Erkundungs-Sprache. Kuratiert-Cascade: Themenseite → Sammlung → Content. |
| `priority` | 500 |
| `default_tone` | kollegial |
| `default_length` | standard |
| `response_type` | cards |
| `quick_replies_mode` | speculative |

### Kernregel

> Kuratiertes vor Algorithmischem. EINE breite `search_wlo_all`-Suche liefert
> Themenseiten, Sammlungen und Inhalte zusammen — die kuratierten Töpfe zuerst
> zeigen. Die Einzel-Tools nur für gezielte Rückfragen zu einem Treffer.

### Werkzeuge

- search_wlo_all
- search_wlo_topic_pages
- search_wlo_collections
- search_wlo_content
- lookup_wlo_vocabulary
- get_related_content
- get_node_collections

### Quellen

- mcp

### Wann anwenden

- Intent I03 (Suche) UND Topic vorhanden ABER kein/wenig Filter
- „Material zu X" / „hast du was zu X?" / „such mir was zu X"
- User möchte ein BREITES Such-Ergebnis, sortiert nach Kuration (Themenseite → Sammlung → Content)
- I03 mit nur Thema + Fach (ohne Stufe oder Medientyp)

### Wann nicht

- Vollständige Filter (Stufe + Medientyp) → M05 (gezielt)
- Topic fehlt komplett → M03 oder M15
- User möchte KI-Generierung statt Suche → M10
- Plan-Anfrage (Lernpfad/Reihe) → M09

### Auslöser-Phrasen

- Material zu X
- Hast du was zu X
- Such mir was zu X
- Ich brauche Material zu X
- Welches Material gibt es zu X

### Anti-Muster

- Keine Vor-Frage stellen wenn Thema klar ist
- Kein direkter Content-Search wenn Cascade noch nicht durchlaufen

### Abgrenzung gegen Nachbarmuster

- **vs**: M05
- **rule**: Nur Thema → M06 (Cascade). Thema + Filter (Stufe/Medientyp) → M05 (gefiltert).
- **example**: Material zu Bruchrechnung → M06. Videos zu Bruchrechnung Klasse 5 → M05.

- **vs**: M09
- **rule**: Hauptverb entscheidet. Such-Verb als Hauptverb (suche/finde/zeig/hast du) → M06 — auch wenn ein um-zu-planen oder Unterrichtseinheit-Nebensatz folgt. Plan-Verb als Hauptverb (plane/stelle zusammen/Stundenentwurf) → M09.
- **example**: Material zur Unterrichtseinheit Bruchrechnung → M06. Plane Unterrichtsreihe Bruchrechnung → M09. Ich suche Material, um meine Unterrichtseinheit zu planen → M06 (Hauptverb=suche).

- **vs**: M10
- **rule**: Such-Verb (zeig/finde/hast du) → M06. Create-Verb (erstell/generiere) → M10.
- **example**: Such mir Quiz zu X → M06. Erstell mir Quiz zu X → M10.

## Anweisung

# M06 — Material-Suche Cascade

## Wann aktiv
- Thema da, aber kein konkreter Filter
- Erkundungs-Sprache („was habt ihr zu Klima?", „zeig mir was zu Bruchrechnung")

## Pipeline
1. `search_wlo_all(query=thema)` — EINE breite Suche liefert Inhalte,
   Sammlungen UND Themenseiten in einem Aufruf. Standard für die breite
   Erstsuche (kein enger Medientyp-Filter) — NICHT die drei Einzel-Suchen
   nacheinander aufrufen.
2. Bei 0 Treffern in allen Töpfen → M12 (Eskalation).

Gezielte Rückfragen zu EINEM konkreten Treffer (z.B. „was ist in dieser
Sammlung?", „zeig mir Details") nutzen weiter die Einzel-Tools
(`search_wlo_collections`, `search_wlo_content`, `search_wlo_topic_pages`).

## Verhalten
- Bei >5 Treffern: kuratiert 3–4 mit Diversität (Stufe + Medientyp)
- Wenn Themenseite getroffen: deren Inhalte direkt zeigen
