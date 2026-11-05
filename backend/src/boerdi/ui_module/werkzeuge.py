"""Werkzeugbeschreibung eines UI-Moduls aus seinem Manifest (Paket U1-b).

Die KI sieht ein Modul wie jedes andere Werkzeug: Name = Modulname, Beschreibung =
``beschreibung`` samt ``wann``/``nicht_wann``, Parameter = ``eingabe``. Zwei Dinge gehen nicht an
die KI: Werte, die nur das System setzt (``x-nur-system`` an einem Feld), und eigene
``x-``-Schlüssel überhaupt — sie sind Vermerke für Backend und Frontend, kein JSON Schema für
das Modell.

Seit U1-d1 auch der allgemeine Weg „Modul-Werkzeug → Block“: :func:`modul_werkzeuge` bietet jedes
Katalog-Modul mit ``agent: true`` an (ohne den Inhaltsrahmen mit seinem Dokument-Werkzeug und ohne
die abgeleiteten Module), :func:`modul_aufruf_annehmen` prüft einen Aufruf gegen ``eingabe`` und
macht daraus einen Block samt Textfassung. Ein Fehler ist ein Werkzeug-Ergebnis für die KI.

Seit U1-e Module mit Datenquelle (``ui_module/datenquelle``): Ihre Parameter sind nur die
``argumente`` der Datenquelle, nicht die ``eingabe`` (die beschreibt die Block-Daten, die das
Backend selbst holt), und angeboten werden sie nur, wenn ihr Werkzeug im Lauf verfügbar ist.
Seit U2 Module mit Dienst (``ui_module/dienst``): ihre Parameter sind der Auftrag
(``dienst.parameter``). Beide laufen asynchron (:func:`ist_asynchron`, ``ui_module/aufruf``).
"""

from __future__ import annotations

from collections.abc import Collection
from typing import Any, Literal

from boerdi.api.schemas_ui import UiBlock
from boerdi.domain.ui_bloecke import neuer_block
from boerdi.ui_module import datenquelle, dienst, katalog, schalter
from boerdi.ui_module.katalog import Manifest
from boerdi.ui_module.namen import OHNE_WIRKUNG_IN_TOOLS

_NUR_SYSTEM = "x-nur-system"

#: Schlüssel, deren Wert eine Liste von FELDNAMEN ist — dort sind ``x-…`` Namen, keine Vermerke.
_FELDLISTEN = frozenset({"properties", "patternProperties", "$defs"})


def _fuer_die_ki(schema: Any, feldliste: bool = False, *, pruefen: bool = False) -> Any:
    """Neue Kopie ohne Systemwerte und ohne ``x-``-Schlüssel, rekursiv.

    ``pruefen``: die Fassung, gegen die ein Aufruf der KI geprüft wird (Review U1 gesamt,
    Befund 4) — dort bleibt eine Aufzählung auch leer stehen, sonst ginge jeder Wert durch."""
    if isinstance(schema, list):
        return [_fuer_die_ki(s, pruefen=pruefen) for s in schema]
    if not isinstance(schema, dict):
        return schema
    if feldliste:
        return {feld: _fuer_die_ki(wert, pruefen=pruefen) for feld, wert in schema.items()}
    nur_system = set(schema.get(_NUR_SYSTEM) or ())
    aus: dict[str, Any] = {}
    for schluessel, wert in schema.items():
        if schluessel.startswith("x-"):
            continue
        if schluessel == "enum" and nur_system:
            # Für die KI: eine leere Aufzählung ließe kein Argument zu — dann lieber keine.
            if (rest := [w for w in wert if w not in nur_system]) or pruefen:
                aus[schluessel] = rest
            continue
        aus[schluessel] = _fuer_die_ki(wert, feldliste=schluessel in _FELDLISTEN,
                                       pruefen=pruefen)
    return aus


def _beschreibung(manifest: Manifest) -> str:
    teile = [manifest["beschreibung"]]
    if manifest.get("wann"):
        teile.append("WANN:\n" + "\n".join(f"- {w}" for w in manifest["wann"]))
    if manifest.get("nicht_wann"):
        teile.append("NICHT:\n" + "\n".join(f"- {w}" for w in manifest["nicht_wann"]))
    return "\n\n".join(teile)


def werkzeug_aus_manifest(manifest: Manifest) -> dict[str, Any]:
    """Die Funktionsbeschreibung (OpenAI-Form) eines Moduls; das Manifest bleibt unverändert.
    Mit Datenquelle sind die Parameter deren Argumente (U1-e), mit Dienst der Auftrag (U2),
    sonst die ``eingabe``."""
    if dienst.name(manifest):
        parameter = dienst.parameter(manifest)
    elif datenquelle.werkzeug(manifest):
        parameter = datenquelle.parameter(manifest)
    else:
        parameter = _fuer_die_ki(manifest["eingabe"])
    return {
        "type": "function",
        "function": {
            "name": manifest["name"],
            "description": _beschreibung(manifest),
            "parameters": parameter,
        },
    }


#: Module mit eigenem Weg: der Inhaltsrahmen über das Dokument-Werkzeug, die abgeleiteten ohne
#: Aufruf aus der fertigen Antwort — dieselben, die in ``tools:`` eines Musters nichts bewirken.
_EIGENER_WEG = frozenset(OHNE_WIRKUNG_IN_TOOLS)

_AUFRUF_FEHLER = ("Fehler: Der Aufruf von {name} passt nicht zur Beschreibung des Werkzeugs. "
                  "Berichtige die Argumente und rufe es noch einmal, oder antworte in Prosa. "
                  "Abweichungen: {fehler}")


def _agent_module() -> dict[str, Manifest]:
    return {name: m for name, m in katalog.katalog().items()
            if m.get("agent") and name not in _EIGENER_WEG}


def ist_modul_werkzeug(name: object) -> bool:
    """Ist ``name`` ein allgemeines Modul-Werkzeug (``agent: true``, kein eigener Weg)?"""
    return isinstance(name, str) and name in _agent_module()


def ist_asynchron(name: object) -> bool:
    """Holt oder erzeugt das Backend die Daten selbst — Datenquelle (U1-e) oder Dienst (U2)? Dann
    läuft der Aufruf über :func:`ui_module.aufruf.asynchron` statt :func:`modul_aufruf_annehmen`."""
    manifest = _agent_module().get(name) if isinstance(name, str) else None
    return manifest is not None and bool(datenquelle.werkzeug(manifest) or dienst.name(manifest))


def ist_abfragendes_modul(name: object) -> bool:
    """Ist ``name`` ein abfragendes Modul-Werkzeug (``art: abfragen``)? Ein Aufruf beendet die
    Runde wie ``respond_to_user`` (Review U1-d2: Phase der Runde in der Muster-Schleife)."""
    return isinstance(name, str) and (_agent_module().get(name) or {}).get("art") == "abfragen"


def modul_werkzeug_titel() -> dict[str, str]:
    """Name → deutscher Titel jedes allgemeinen Modul-Werkzeugs, nach Namen sortiert — für das
    Studio (Werkzeug-Katalog der Muster, Werkzeug-Übersicht, Prompt-Vorschau; U1-d2)."""
    return {name: str((m.get("titel") or {}).get("de") or "")
            for name, m in sorted(_agent_module().items())}


def _anbietbar(manifest: Manifest, verfuegbar: Collection[str] | None) -> bool:
    """Ein Modul mit Datenquelle nur, wenn sein Werkzeug im Lauf verfügbar ist (Sperren der
    Sicherheit, Studio-Schalter, Modus der Einbettung — Plan §15, E-3) und das Backend es kennt;
    ein Modul mit Dienst, wenn das Backend den Dienst kennt (U2)."""
    if dienst.name(manifest):
        return dienst.parameter(manifest) is not None
    quelle = datenquelle.werkzeug(manifest)
    return quelle is None or (verfuegbar is not None and quelle in verfuegbar
                              and datenquelle.parameter(manifest) is not None)


def modul_werkzeuge(erlaubt: Collection[str], verfuegbar: Collection[str] | None = None, *,
                    fuer: Literal["agent", "muster"]) -> list[dict[str, Any]]:
    """Die Funktionsbeschreibungen der allgemeinen Modul-Werkzeuge, die ``erlaubt`` nennt (die
    Module, die das Widget zeigen kann), nach Namen sortiert. ``verfuegbar`` sind die
    MCP-Werkzeuge des Laufs; ohne Angabe fallen Module mit Datenquelle weg.

    ``fuer`` (U1-f, Pflicht — keine stille Vorgabe): die Studio-Schalter. ``agent`` nimmt nur
    Module, die aktiv und für den Agenten an sind; ``muster`` nur aktive (``schalter``)."""
    zugelassen = schalter.fuer_agent if fuer == "agent" else schalter.aktiv
    return [werkzeug_aus_manifest(m) for name, m in sorted(_agent_module().items())
            if name in erlaubt and zugelassen(name) and _anbietbar(m, verfuegbar)]


def _doppelte_kennungen(daten: dict[str, Any]) -> list[str]:
    """Listen von Objekten mit ``id`` (z. B. ``optionen``): jede Kennung nur einmal — das kann
    JSON Schema nicht ausdrücken, und eine Antwort nennt nur Kennungen."""
    fehler = []
    for feld, wert in daten.items():
        if not isinstance(wert, list):
            continue
        gesehen: set[str] = set()
        for eintrag in wert:
            kennung = eintrag.get("id") if isinstance(eintrag, dict) else None
            if isinstance(kennung, str) and kennung in gesehen:
                fehler.append(f"{feld}: Kennung „{kennung}“ doppelt")
            elif isinstance(kennung, str):
                gesehen.add(kennung)
    return fehler


def _beschriftung(eintrag: Any) -> str:
    if not isinstance(eintrag, dict):
        return str(eintrag)
    text = str(eintrag.get("label") or eintrag.get("titel") or eintrag.get("id") or "")
    hinweis = eintrag.get("hinweis")
    return f"{text} — {hinweis}" if isinstance(hinweis, str) and hinweis.strip() else text


def textfassung(manifest: Manifest, daten: dict[str, Any]) -> str:
    """Die Textfassung eines Blocks nach der Vorlage des Manifests — für Widgets, die das Modul
    nicht kennen. ``nummerierte_liste`` setzt eine ``frage`` (falls vorhanden) davor, damit die
    Person mit der Nummer antworten kann."""
    vorlage = manifest["textfassung"]["vorlage"]
    wert = daten.get(manifest["textfassung"].get("feld") or "")
    if vorlage == "nummerierte_liste" and isinstance(wert, list):
        liste = "\n".join(f"{i}. {_beschriftung(e)}" for i, e in enumerate(wert, start=1))
        frage = daten.get("frage")
        return f"{frage}\n\n{liste}" if isinstance(frage, str) and frage.strip() else liste
    return wert if isinstance(wert, str) else ""


def modul_aufruf_annehmen(name: str, args: object) -> tuple[UiBlock | None, str | None]:
    """Ein Werkzeugaufruf → ``(Block, None)`` oder ``(None, Fehlertext für die KI)``.

    Geprüft gegen ``eingabe`` des Manifests, so wie die KI sie sieht (ohne Werte, die nur das
    System setzt — ``x-nur-system``), und auf eindeutige Kennungen. Ein abfragender Block ist
    ``offen``; die Regeln je Antwort (höchstens ein offener) wendet die Schleife an.
    """
    manifest = _agent_module().get(name)
    if manifest is None:
        return None, f"Fehler: {name} ist kein UI-Modul, das du aufrufen kannst."
    daten = args if isinstance(args, dict) else {}
    fuer_die_ki = {**manifest, "eingabe": _fuer_die_ki(manifest["eingabe"], pruefen=True)}
    if fehler := katalog.daten_fehler(fuer_die_ki, daten) or _doppelte_kennungen(daten):
        return None, _AUFRUF_FEHLER.format(name=name, fehler="; ".join(fehler))
    return neuer_block(name, manifest["version"], manifest["art"], daten,
                       textfassung(manifest, daten)), None
