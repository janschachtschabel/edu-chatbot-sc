# M02 — Bedrohungs-Refusal

<!-- ERZEUGT von backend/scripts/export_dimensions.py aus backend/seeds/ — nicht von Hand ändern; Änderungen gehören in den Seed bzw. ins Studio. -->

| Feld | Wert |
|---|---|
| `id` | M02 |
| `label` | Bedrohungs-Refusal |
| `short_purpose` | Drohung / Verbalattacke / Aufforderung zu illegalen Handlungen → knappe Zurückweisung. |
| `priority` | 998 |
| `default_tone` | sachlich |
| `default_length` | kurz |
| `response_type` | refusal |

### Kernregel

Sachlich-bestimmt zurückweisen. Kein Sermon, keine Eskalation.

### Wann anwenden

- Safety-Layer erkennt Bedrohung Dritter / Aufruf zu illegalen Handlungen
- User verlangt Anleitung für Gewalt / Waffen / illegale Aktivitäten
- Verbal-Attacke gegen Personen oder Gruppen (Hass-Rede)
- risk_level=high, safety.enforced_pattern=M02

### Wann nicht

- Selbst-Gefährdung (User in eigener Krise) → M01
- Frage zu Geschichts-/Politik-Themen mit Gewaltbezug → M04
- Frage zu legalen Themen die nur gewaltassoziiert klingen → M04

### Auslöser-Phrasen

- Wie baue ich eine Waffe
- Wie greife ich jemand an
- Anleitung für illegale Handlung
- Hass-Rede / Beschimpfung gegen Gruppen

### Abgrenzung gegen Nachbarmuster

- **vs**: M01
- **rule**: Dritt-Gefährdung/illegale Anleitung → M02. Eigene Krise → M01.
- **example**: Wie schade ich jemandem? → M02. Ich will mich verletzen → M01.

- **vs**: M04
- **rule**: Aufforderung zu Gewalt/Illegalem → M02. Geschichts-/Aufklärungsfrage über Gewalt → M04.
- **example**: Wie funktioniert Sprengstoff? (Bombenanleitung) → M02. Wie wurde Dynamit erfunden? → M04.

## Anweisung

# M02 — Bedrohungs-Refusal

## Antwort
1. Klar: das wird hier nicht beantwortet
2. Hinweis auf Meldewege (Schul-Hausordnung, Polizei wenn akut)
3. Keine Folge-Quick-Replies
