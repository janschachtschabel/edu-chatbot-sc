"""Werte hinzufügen statt ersetzen, mehrere Werte je Feld (Plan 2026-11-14, N2).

Bis zum MCP-Stand vom 14.11. nahm ``wlo_update_content`` für Fach, Bildungsstufe, Inhaltstyp und
Zielgruppe genau eine Bezeichnung und ERSETZTE damit alle bisherigen Werte. „Füge das Fach
Mathematik hinzu“ ging nicht: Die KI sollte das Werkzeug dafür nicht aufrufen und einen Vorschlag
anbieten. Der neue Stand kennt

- ``addDiscipline`` / ``addEducationalContext`` / ``addUserRole`` an ``wlo_update_content`` und je
  Eintrag von ``wlo_update_contents``: fügt hinzu, die bisherigen Werte bleiben;
- eine Liste statt einer Bezeichnung an den vier ersetzenden Feldern (auch beim Anlegen);
- ``lookup_wlo_vocabulary("contentType")``: die Inhaltstypen, wie das Schreiben sie annimmt.

Dieses Modul sagt, was das Modell davon angeboten bekommt — nur, wenn der bereitgestellte Server
es kennt (:mod:`faehigkeiten`). Die Argument-Modelle (``api/schemas_mcp_curation``) nehmen Listen
und die drei Felder immer an.

**Woran das Angebot hängt:** an ``addDiscipline`` in der Werkzeugliste von ``wlo_update_content``.
Listen und die Einträge von ``wlo_update_contents`` zeigt die Werkzeugliste nur verschachtelt; sie
kamen mit demselben Stand (B1) und hängen deshalb an derselben Marke.
"""

from __future__ import annotations

import copy
from typing import Any, Final

from boerdi.api.schemas_mcp_curation import HINZUFUEGEN, MEHRWERTIG
from boerdi.services.mcp import faehigkeiten

_MARKE: Final = ("wlo_update_content", "addDiscipline")
_NACHSCHLAGEN: Final = ("lookup_wlo_vocabulary", "vocabulary", "contentType")

#: Der Satz in der Beschreibung von ``wlo_update_content``, solange der Server nur ersetzen kann
#: (``tool_defs_curation`` setzt ihn ein) — und der, der ihn ablöst.
NUR_ERSETZEN: Final = (
    "Schlagworte werden ergaenzt; Fach, Bildungsstufe, Inhaltstyp und "
    "Zielgruppe werden ERSETZT: alle bisherigen Werte fallen weg. Soll ein Wert "
    "HINZUKOMMEN, dieses Werkzeug dafuer nicht aufrufen: sag, dass es nur ersetzen "
    "kann, und biete einen Vorschlag an (wlo_suggest_metadata; Annehmen ergaenzt). ")
MIT_HINZUFUEGEN: Final = (
    "Schlagworte werden ergaenzt. Fach, Bildungsstufe, Inhaltstyp und Zielgruppe werden "
    "ERSETZT: alle bisherigen Werte fallen weg (mehrere Werte als Liste). Soll ein Wert "
    "HINZUKOMMEN, nimm addDiscipline, addEducationalContext oder addUserRole: die bisherigen "
    "Werte bleiben. Nie dasselbe Feld zugleich ersetzen und ergaenzen. Der Inhaltstyp laesst "
    "sich nur ersetzen: soll einer dazukommen, die bisherigen mitnennen (get_node_details) "
    "oder einen Vorschlag anbieten (wlo_suggest_metadata). ")

#: Hinzufügen-Parameter → (was er ergänzt, das ersetzende Geschwisterfeld).
_HINZU: Final[dict[str, tuple[str, str]]] = {
    "addDiscipline": ("Fach", "discipline"),
    "addEducationalContext": ("Bildungsstufe", "educationalContext"),
    "addUserRole": ("Zielgruppe", "userRole"),
}
assert set(_HINZU) == set(HINZUFUEGEN), "die Hinzufügen-Felder des Modells und des Angebots"
_LISTE: Final = " Eine Bezeichnung oder mehrere als Liste."
_ERSETZT: Final = " ERSETZT die bisherigen Werte (die bleibenden mitnennen)."
_VORSCHLAG_IM_STAPEL: Final = (" In wlo_update_contents wird die Zielgruppe nicht geschrieben, "
                               "sondern als Vorschlag hinterlegt.")
_STAPEL_SATZ: Final = (" Je Eintrag fuegen addDiscipline und addEducationalContext hinzu, statt "
                       "zu ersetzen (die Zielgruppe wird im Stapel als Vorschlag hinterlegt).")
#: Der Zusatz in der Beschreibung des Felds ``contentType``, solange der Server die Inhaltstypen
#: nicht nachschlagen lässt — und der, der ihn ablöst (Review N2, M1).
TYP_FRAGEN: Final = ("(nicht nachschlagen); nennt sie zwei Bedeutungen oder keinen, die Person "
                     "fragen.")
TYP_NACHSCHLAGEN_ODER_FRAGEN: Final = (
    "(nicht unter lrt nachschlagen); nennt sie zwei Bedeutungen, die Person fragen; nennt sie "
    "keinen, mit lookup_wlo_vocabulary (vocabulary=contentType, query) nachschlagen.")
#: Review N2 (M4): die KI nennt ``add…``, der bereitgestellte Server kennt es nachweislich nicht.
_KANN_NICHT_HINZUFUEGEN: Final = (
    "Dieser Server kann Werte nicht hinzufuegen ({felder}): er liesse die Angabe still weg. "
    "Nichts wurde geaendert. Sag, dass das Werkzeug hier nur ersetzen kann, und biete einen "
    "Vorschlag an (wlo_suggest_metadata; Annehmen ergaenzt).")
#: Der Satz in der Beschreibung von ``lookup_wlo_vocabulary``, solange der Server die
#: Inhaltstypen des Schreibens nicht nachschlagen lässt — und der, der ihn ablöst.
TYP_NICHT_NACHSCHLAGEN: Final = (
    "Den Inhaltstyp fuers Schreiben NICHT hier nachschlagen: die Schreibwerkzeuge pruefen ihn "
    "gegen ein feineres Vokabular und nennen bei einer Ablehnung selbst Vorschlaege")
TYP_UNTER_CONTENTTYPE: Final = (
    "Den Inhaltstyp fuers Schreiben NICHT unter lrt nachschlagen (die Schreibwerkzeuge pruefen "
    "gegen ein feineres Vokabular): bei einer Ablehnung zuerst ihre Vorschlaege nehmen, erst "
    "sonst vocabulary=contentType mit query")
_TYP_NACHSCHLAGEN: Final = (
    " contentType = die Inhaltstypen, wie die Schreibwerkzeuge sie im Feld contentType annehmen "
    "(nicht dieselbe Liste wie lrt; gross, mit query eingrenzen).")


def angeboten() -> bool:
    """Bekommt das Modell Listen und die Hinzufügen-Parameter angeboten?"""
    return faehigkeiten.kennt(*_MARKE)


def _felder(eigenschaften: dict[str, Any], *, hinzu: bool, stapel: bool = False) -> None:
    """Die vier Felder als Liste; mit ``hinzu`` (ein vorhandener Datensatz) der Satz, dass sie
    ersetzen, und dazu die drei ergänzenden. Im Stapel wird die Zielgruppe nur vorgeschlagen."""
    for feld in MEHRWERTIG:
        if feld not in eigenschaften:
            continue
        text = eigenschaften[feld].get("description", "") + _LISTE
        if feld == "contentType" and faehigkeiten.kennt_wert(*_NACHSCHLAGEN):
            text = text.replace(TYP_FRAGEN, TYP_NACHSCHLAGEN_ODER_FRAGEN, 1)
        if stapel and feld == "userRole":
            text += _VORSCHLAG_IM_STAPEL
        elif hinzu:
            text += _ERSETZT
        eigenschaften[feld] = {"type": "array", "items": {"type": "string"}, "description": text}
    if not hinzu:
        return
    for name, (was, geschwister) in _HINZU.items():
        eigenschaften[name] = {
            "type": "array", "items": {"type": "string"},
            "description": (f"{was}: eine Bezeichnung oder mehrere — FUEGT hinzu, die bisherigen "
                            f"Werte bleiben. Nicht zusammen mit {geschwister}."
                            + (_VORSCHLAG_IM_STAPEL if name == "addUserRole" else ""))}


def nicht_moeglich(werkzeug: str, argumente: dict[str, Any]) -> str | None:
    """Ein Satz für die KI, wenn sie ``add…`` nennt und der bereitgestellte Server es nachweislich
    nicht kennt — sonst ``None``. Ohne Auskunft des Servers (Stand unbekannt) geht der Aufruf
    hinaus wie bisher: der Server entscheidet.

    Ein Server ohne ``add…`` verwirft das Feld still: mit einem zweiten Feld daneben schriebe er
    nur dieses, und das Fach fehlte wortlos (Review N2, M4)."""
    if werkzeug not in ("wlo_update_content", "wlo_update_contents") or angeboten():
        return None
    if not faehigkeiten.kennt(_MARKE[0], "nodeId"):
        return None
    eintraege = argumente.get("items") if werkzeug == "wlo_update_contents" else [argumente]
    genannt = sorted({f for e in eintraege if isinstance(e, dict) for f in HINZUFUEGEN if f in e}
                     ) if isinstance(eintraege, list) else []
    return _KANN_NICHT_HINZUFUEGEN.format(felder=", ".join(genannt)) if genannt else None


def erweitert(definition: dict[str, Any]) -> dict[str, Any]:
    """Die Werkzeug-Definition, wie der bereitgestellte Server sie versteht — eine Kopie; ohne
    Angebot (oder für ein anderes Werkzeug) die Definition selbst."""
    name = definition["function"]["name"]
    if name == _NACHSCHLAGEN[0]:
        return _mit_inhaltstyp(definition)
    if name not in ("wlo_update_content", "wlo_update_contents", "wlo_create_content") \
            or not angeboten():
        return definition
    neu = copy.deepcopy(definition)
    funktion = neu["function"]
    eigenschaften = funktion["parameters"]["properties"]
    if name == "wlo_update_contents":
        _felder(eigenschaften["items"]["items"]["properties"], hinzu=True, stapel=True)
        funktion["description"] = funktion["description"].replace(
            " Fortsetzen wie bei", _STAPEL_SATZ + " Fortsetzen wie bei", 1)
    else:
        _felder(eigenschaften, hinzu=name == "wlo_update_content")
        # Driftet der Katalog, fände der Tausch den Satz nicht — das hält ein Wächtertest fest
        # (``test_die_saetze_die_abgeloest_werden_stehen_in_den_vorlagen``).
        funktion["description"] = funktion["description"].replace(NUR_ERSETZEN, MIT_HINZUFUEGEN, 1)
    return neu


def _mit_inhaltstyp(definition: dict[str, Any]) -> dict[str, Any]:
    """``lookup_wlo_vocabulary`` mit dem Wert ``contentType`` — wenn der Server ihn nennt."""
    if not faehigkeiten.kennt_wert(*_NACHSCHLAGEN):
        return definition
    neu = copy.deepcopy(definition)
    vokabular = neu["function"]["parameters"]["properties"]["vocabulary"]
    if _NACHSCHLAGEN[2] not in vokabular.get("enum", []):
        vokabular["enum"] = [*vokabular.get("enum", []), _NACHSCHLAGEN[2]]
    vokabular["description"] = vokabular.get("description", "") + _TYP_NACHSCHLAGEN
    neu["function"]["description"] = neu["function"]["description"].replace(
        TYP_NICHT_NACHSCHLAGEN, TYP_UNTER_CONTENTTYPE, 1)
    if faehigkeiten.kennt(_NACHSCHLAGEN[0], "query"):
        neu["function"]["parameters"]["properties"].setdefault("query", {
            "type": "string",
            "description": "Grenzt contentType auf Eintraege nahe diesem Begriff ein, "
                           "z.B. 'Video'."})
    return neu
