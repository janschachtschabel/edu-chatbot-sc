"""Die Prüfung von ``agent.feste_argumente`` (Plan 2026-11-19, A2, E4) — aus ``pruefung`` gelöst,
weil die schon groß ist.

Feste Argumente setzt ``ui_module/dienst.aufruf`` in jeden Aufruf eines UI-Moduls mit Dienst. Ein
Befund, wenn das Werkzeug nicht im Schritt steht, kein UI-Modul mit Dienst ist (dort wirkten sie
nie), ein Argument nicht im Schema des Dienstes steht oder sein Wert nicht dazu passt. Review A,
NIT 11: auch, wenn sie sich widersprechen (``aus_dokument`` und ``aus_inhalten``) oder ein Argument
festlegen, das nur zu einem mitgeschickten Entwurf gehört (``vorlage`` …) — dort gelten feste
Argumente ohnehin nicht (``dienst.aufruf``).
"""

from __future__ import annotations

from typing import Any, Final

from jsonschema import Draft202012Validator

from boerdi.domain.config_models.ablauf import Schritt
from boerdi.services.ablauf.pruefung_texte import t as _t

#: Gehören zu einem mitgeschickten Entwurf — fest gesetzt, lähmten sie den Schritt.
_NIE_FEST: Final = ("vorlage", "vertiefen", "erneut_zeigen")
#: Schließen sich aus (``dienst._strukturentwurf``: ``inhalte_ausschluss``).
_AUSSCHLUSS: Final = ("aus_dokument", "aus_inhalten")


def _teilschema(parameter: dict[str, Any], name: str) -> dict[str, Any]:
    """Das Schema eines Arguments MIT den ``$defs`` des Werkzeugs — ein ``$ref`` darauf fände allein
    nichts (zweites Review A, NIT 10)."""
    teil = dict(parameter["properties"][name])
    if "$defs" in parameter:
        teil["$defs"] = parameter["$defs"]
    return teil


def befunde(s: Schritt, module: dict[str, Any], lang: str) -> list[str]:
    feste = (s.agent.feste_argumente if s.agent else None) or {}
    b: list[str] = []
    for werkzeug, argumente in feste.items():
        if werkzeug not in s.agent.werkzeuge:
            b.append(_t(lang, "feste_werkzeug", s=s.id, w=werkzeug[:60]))
            continue
        parameter = ((module.get(werkzeug) or {}).get("dienst") or {}).get("parameter")
        if not isinstance(parameter, dict):
            b.append(_t(lang, "feste_dienst", s=s.id, w=werkzeug))
            continue
        erlaubt = parameter.get("properties") or {}
        for name, wert in argumente.items():
            if name not in erlaubt:
                b.append(_t(lang, "feste_argument", s=s.id, w=werkzeug, a=name[:40],
                            e=", ".join(sorted(erlaubt))))
            elif fehler := next(Draft202012Validator(_teilschema(parameter, name)).iter_errors(
                    wert), None):
                b.append(_t(lang, "feste_wert", s=s.id, w=werkzeug, a=name,
                            f=fehler.message[:120]))
            elif name in _NIE_FEST:
                b.append(_t(lang, "feste_nie", s=s.id, w=werkzeug, a=name))
        if all(argumente.get(n) is True for n in _AUSSCHLUSS):
            b.append(_t(lang, "feste_ausschluss", s=s.id, w=werkzeug, a=", ".join(_AUSSCHLUSS)))
    return b
