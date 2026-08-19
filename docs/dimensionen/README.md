# Dimensionen des Chatbots

<!-- ERZEUGT von backend/scripts/export_dimensions.py aus backend/seeds/ — nicht von Hand ändern; Änderungen gehören in den Seed bzw. ins Studio. -->

Die Anweisungen, nach denen der Bot handelt — als Text zum Weiterverwenden.

| Datei | Inhalt |
|---|---|
| [muster.md](muster.md) | Übersicht aller 20 Muster |
| [muster/](muster/) | je Muster eine Datei: Kopfdaten, Werkzeuge, Abgrenzungen, Anweisung |
| [intents.md](intents.md) | Intents mit Beispielen, Auslöse-Verben, Abgrenzungen |
| [personas.md](personas.md) | Personas mit Ton, Förmlichkeit, Markern, Anweisung |
| [states.md](states.md) | Gesprächsphasen samt `bot_directive` |
| [entities.md](entities.md) | Entities (Slots) der Klassifikation |
| [signale.md](signale.md) | Signal-Modulationen |

## Herkunft und Auffrischen

Quelle ist `backend/seeds/` — versioniert und ohne Datenbank lesbar. Der
laufende Betrieb liest jedoch den Config-Store; wer im Studio geändert hat,
holt den Stand zuerst herunter:

```bash
cd backend
uv run boerdi export-config --to seeds        # live -> Seeds
uv run python scripts/export_dimensions.py    # Seeds -> docs/dimensionen
```

Die Kommentare der YAML-Dateien kommen **nicht** mit: sie begründen für die
Redaktion, was dort steht, und sind keine Anweisung an das Modell.
