# Gesprächsphasen (States)

<!-- ERZEUGT von backend/scripts/export_dimensions.py aus backend/seeds/ — nicht von Hand ändern; Änderungen gehören in den Seed bzw. ins Studio. -->

Quelle: `backend/seeds/04-states/states.yaml`

## S1 — Orientierung

- **description**: Erster Kontakt oder Re-Orientierung — kein konkretes Anliegen.
- **role**: Bot sondiert offen, ohne Pre-Commitment.
- **bot_directive**:
  > EINE offene Frage, 2–3 Quick-Reply-Optionen. Kein Tool-Call.
  > Max. 2 Sätze.
- **next_likely**:
  - S2
  - S3
- **selection_criteria**:
  - Erstkontakt ohne Material-/Fach-Anker
  - Re-Orientierung nach Topic-Switch ohne neues konkretes Anliegen
  - User fragt 'Was kannst du?' / 'Ich bin neu'

## S2 — Klärung

- **description**: Slot-Lücke vor Suche/Erstellung — eine gezielte Rückfrage.
- **role**: Bot fragt nach EINEM fehlenden Slot.
- **bot_directive**:
  > Genau EINE Frage zum wichtigsten fehlenden Slot. Quick-Replies
  > mit 3–4 plausiblen Antworten. KEIN Tool-Call solange Pflicht-
  > Slot fehlt.
- **next_likely**:
  - S3
  - S2
  - S1
- **selection_criteria**:
  - Intent ist klar (z. B. I03/I05/I04), aber ein Pflicht-Slot fehlt (Fach, Thema, Stufe)
  - Antwort des Users ist mehrdeutig zwischen mehreren Optionen

## S3 — Aktion

- **description**: Bot liefert die Antwort — Suche, Wissensantwort, Lernpfad, KI-Inhalt, Nachbearbeitung, Routing, Feedback-Echo. Umfasst alle nicht-orientierenden Verlaufs-Phasen.

- **role**: Bot führt die geforderte Aktion aus.
- **bot_directive**:
  > Aktion ausführen (Tool-Call oder direkte Antwort). Max. 1 Satz
  > Einleitung, Inhalte über Kacheln oder Markdown. Am Ende ein
  > konkreter Folgehook / Quick-Reply.
- **next_likely**:
  - S3
  - S2
  - S1
- **selection_criteria**:
  - Intent + Pflicht-Slots klar → Antwort/Aktion direkt möglich
  - Folge-Turn nach S2-Klärung mit nun vollem Slot-Set
  - Edit-Turn (I06) auf bestehenden Bot-Inhalt

