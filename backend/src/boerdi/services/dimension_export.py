"""Die Dimensionen des Chatbots als lesbares Markdown nach ``docs/dimensionen/``.

**Wozu.** Muster, Intents, Personas, Phasen, Entities und Signale sind die
Anweisungen, nach denen der Bot handelt — sie liegen aber in einer Form, die
fürs Laden gemacht ist: YAML-Frontmatter, verschachtelte Listen, ein Seed-Baum.
Wer sie weiterverwenden will (Redaktion, Konzept, ein anderes Modell), braucht
sie als Text, nicht als Datenstruktur.

**Quelle ist der Seed-Baum**, nicht die laufende Datenbank — bewusst: der Seed
ist versioniert, diffbar und braucht keine Verbindung. Wer im Studio geändert
hat, holt den Stand zuerst herunter::

    uv run boerdi export-config --to seeds      # live -> Seeds
    uv run python scripts/export_dimensions.py  # Seeds -> docs/dimensionen

**Was NICHT mitkommt:** die Kommentare der YAML-Dateien. Sie tragen die
Begründungen für die Redaktion („warum steht das hier"), nicht die Anweisung an
das Modell — und ``yaml.safe_load`` sieht sie ohnehin nicht. Wer sie braucht,
liest den Seed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

#: Die YAML-Dimensionen: Zieldatei, Überschrift, Pfad im Seed-Baum.
_YAML_DIMENSIONEN: tuple[tuple[str, str, str], ...] = (
    ("intents.md", "Intents", "04-intents/intents.yaml"),
    ("states.md", "Gesprächsphasen (States)", "04-states/states.yaml"),
    ("entities.md", "Entities (Slots)", "04-entities/entities.yaml"),
    ("signale.md", "Signal-Modulationen", "04-signals/signal-modulations.yaml"),
)

#: Kopfdaten eines Musters, in dieser Reihenfolge. Alles andere landet generisch
#: darunter — ein neues Feld im Seed soll nicht still aus dem Export fallen.
_MUSTER_KOPF = (
    "id", "label", "short_purpose", "priority", "default_tone", "default_length",
    "response_type", "quick_replies_mode",
)
_MUSTER_ABSCHNITTE = (
    ("core_rule", "Kernregel"),
    ("tools", "Werkzeuge"),
    ("sources", "Quellen"),
    ("when_to_use", "Wann anwenden"),
    ("when_not_to_use", "Wann nicht"),
    ("trigger_phrases", "Auslöser-Phrasen"),
    ("anti_patterns", "Anti-Muster"),
    ("discriminators", "Abgrenzung gegen Nachbarmuster"),
)
_HINWEIS = (
    "<!-- ERZEUGT von backend/scripts/export_dimensions.py aus backend/seeds/ — "
    "nicht von Hand ändern; Änderungen gehören in den Seed bzw. ins Studio. -->"
)


# ── Bausteine ────────────────────────────────────────────────────────────
def _frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """``(Kopfdaten, Rumpf)`` einer Seed-Markdown-Datei."""
    if not text.startswith("---"):
        return {}, text.strip()
    _, kopf, rumpf = text.split("---", 2)
    return yaml.safe_load(kopf) or {}, rumpf.strip()


def _mehrzeilig(text: str, einzug: str) -> list[str]:
    """Mehrzeiliger Text als Zitat — so bleibt eine Anweisung lesbar."""
    return [f"{einzug}> {zeile}".rstrip() for zeile in text.strip().splitlines()]


def _wert(wert: Any, ebene: int = 0) -> list[str]:
    """Ein YAML-Wert als Markdown-Zeilen — rekursiv, Reihenfolge wie im Seed."""
    einzug = "  " * ebene
    zeilen: list[str] = []
    if isinstance(wert, dict):
        for schluessel, inhalt in wert.items():
            if isinstance(inhalt, str) and "\n" in inhalt.strip():
                zeilen.append(f"{einzug}- **{schluessel}**:")
                zeilen += _mehrzeilig(inhalt, einzug + "  ")
            elif isinstance(inhalt, dict | list):
                zeilen.append(f"{einzug}- **{schluessel}**:")
                zeilen += _wert(inhalt, ebene + 1)
            else:
                zeilen.append(f"{einzug}- **{schluessel}**: {inhalt}")
    elif isinstance(wert, list):
        for eintrag in wert:
            if isinstance(eintrag, dict | list):
                zeilen += _wert(eintrag, ebene)
                zeilen.append("")
            else:
                zeilen.append(f"{einzug}- {eintrag}")
    elif isinstance(wert, str) and "\n" in wert.strip():
        zeilen += _mehrzeilig(wert, einzug)
    else:
        zeilen.append(f"{einzug}{wert}")
    return zeilen


def _abschnitt(titel: str, wert: Any) -> str:
    """Überschrift + Inhalt — oder nichts, wenn es nichts zu zeigen gibt."""
    if wert is None or wert == "" or wert == [] or wert == {}:
        return ""
    return f"### {titel}\n\n" + "\n".join(_wert(wert)).rstrip() + "\n\n"


# ── Muster ───────────────────────────────────────────────────────────────
def _muster_seite(kopf: dict[str, Any], rumpf: str) -> str:
    zeilen = [
        f"# {kopf.get('id', '?')} — {kopf.get('label', '')}".rstrip(), "",
        _HINWEIS, "", "| Feld | Wert |", "|---|---|",
    ]
    zeilen += [f"| `{feld}` | {kopf[feld]} |" for feld in _MUSTER_KOPF if feld in kopf]
    text = "\n".join(zeilen) + "\n\n"

    for feld, titel in _MUSTER_ABSCHNITTE:
        text += _abschnitt(titel, kopf.get(feld))

    bekannt = set(_MUSTER_KOPF) | {feld for feld, _ in _MUSTER_ABSCHNITTE}
    text += _abschnitt("Weitere Kopfdaten",
                       {k: v for k, v in kopf.items() if k not in bekannt})
    return text + f"## Anweisung\n\n{rumpf}\n"


def _muster_index(muster: list[tuple[str, dict[str, Any]]]) -> str:
    zeilen = [
        "# Muster", "", _HINWEIS, "",
        "Ein Muster bündelt Ton, Länge, Werkzeugliste und Anweisung für eine Art",
        "von Zug. Im Muster-Modus wählt der Klassifikator es, im Hybrid das Modell",
        "selbst (`waehle_vorgehen`), im Agent-Modus gibt es keins.", "",
        "| ID | Label | Zweck | Werkzeuge | Datei |", "|---|---|---|---|---|",
    ]
    for datei, kopf in muster:
        werkzeuge = ", ".join(f"`{t}`" for t in (kopf.get("tools") or [])) or "—"
        zweck = str(kopf.get("short_purpose", "")).replace("|", "\\|").replace("\n", " ").strip()
        zeilen.append(
            f"| {kopf.get('id', '?')} | {kopf.get('label', '')} | {zweck} "
            f"| {werkzeuge} | [{datei}](muster/{datei}) |"
        )
    return "\n".join(zeilen) + "\n"


# ── Personas + generische YAML-Dimensionen ───────────────────────────────
def _ueberschrift(name: Any, label: Any) -> str:
    """``## ID — Label`` — ohne den Strich, wenn kein Label gepflegt ist."""
    return f"## {name} — {label}\n\n" if label else f"## {name}\n\n"


def _personas_seite(dateien: list[Path]) -> str:
    text = f"# Personas\n\n{_HINWEIS}\n\n"
    for pfad in dateien:
        kopf, rumpf = _frontmatter(pfad.read_text(encoding="utf-8"))
        text += _ueberschrift(kopf.get("id", pfad.stem), kopf.get("label"))
        text += _abschnitt("Kopfdaten",
                           {k: v for k, v in kopf.items() if not isinstance(v, list)})
        text += _abschnitt("Marker und Listen",
                           {k: v for k, v in kopf.items() if isinstance(v, list)})
        if rumpf:
            text += f"### Anweisung\n\n{rumpf}\n\n"
    return text


def _eintraege(daten: Any) -> list[dict[str, Any]] | None:
    """Die Datensatz-Liste einer YAML-Datei — oder ``None`` bei anderer Form.

    Erkennt beide Bauarten im Seed-Baum: die Datei IST eine Liste, oder sie hat
    genau eine Liste unter einem Schlüssel (``intents:``, ``states:`` …).
    """
    if isinstance(daten, list) and all(isinstance(e, dict) for e in daten):
        return daten
    if isinstance(daten, dict):
        listen = [w for w in daten.values()
                  if isinstance(w, list) and w and all(isinstance(e, dict) for e in w)]
        if len(listen) == 1:
            return listen[0]
    return None


def _yaml_seite(titel: str, quelle: str, daten: Any) -> str:
    text = f"# {titel}\n\n{_HINWEIS}\n\nQuelle: `backend/seeds/{quelle}`\n\n"
    eintraege = _eintraege(daten)
    if eintraege is None:
        # Keine Datensatz-Liste (z.B. eine Zuordnung) — generisch, aber vollständig.
        return text + "\n".join(_wert(daten)).rstrip() + "\n"
    for eintrag in eintraege:
        name = eintrag.get("id") or eintrag.get("name") or "?"
        text += _ueberschrift(name, eintrag.get("label"))
        rest = {k: v for k, v in eintrag.items() if k not in {"id", "label"}}
        text += "\n".join(_wert(rest)).rstrip() + "\n\n"
    return text


def _readme(anzahl_muster: int) -> str:
    return f"""# Dimensionen des Chatbots

{_HINWEIS}

Die Anweisungen, nach denen der Bot handelt — als Text zum Weiterverwenden.

| Datei | Inhalt |
|---|---|
| [muster.md](muster.md) | Übersicht aller {anzahl_muster} Muster |
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
"""


# ── Einstieg ─────────────────────────────────────────────────────────────
def exportiere(seeds: Path, ziel: Path) -> list[Path]:
    """Schreibt den Export und gibt die geschriebenen Dateien zurück."""
    ziel.mkdir(parents=True, exist_ok=True)
    (ziel / "muster").mkdir(exist_ok=True)
    geschrieben: list[Path] = []

    def schreibe(pfad: Path, text: str) -> None:
        pfad.write_text(text, encoding="utf-8", newline="\n")
        geschrieben.append(pfad)

    muster: list[tuple[str, dict[str, Any]]] = []
    for quelle in sorted((seeds / "03-patterns").glob("*.md")):
        kopf, rumpf = _frontmatter(quelle.read_text(encoding="utf-8"))
        name = f"{kopf.get('id', quelle.stem)}-{quelle.stem.split('-', 1)[-1]}.md"
        schreibe(ziel / "muster" / name, _muster_seite(kopf, rumpf))
        muster.append((name, kopf))
    schreibe(ziel / "muster.md", _muster_index(muster))

    schreibe(ziel / "personas.md",
             _personas_seite(sorted((seeds / "04-personas").glob("*.md"))))
    for datei, titel, quelle_pfad in _YAML_DIMENSIONEN:
        daten = yaml.safe_load((seeds / quelle_pfad).read_text(encoding="utf-8"))
        schreibe(ziel / datei, _yaml_seite(titel, quelle_pfad, daten))

    schreibe(ziel / "README.md", _readme(len(muster)))
    return geschrieben
