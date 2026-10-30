"""Schalter gespeicherter Bereiche normalisieren — für den Cache der Leser (Paket 18E, N1).

Das Gate prüft einen Bereich mit seinem Modell im Lax-Modus und speichert das ROHDOKUMENT
(``api/config_guards.modell_fehler``): ``log_all_turns: "false"`` passiert es, weil Pydantic den
Text als ``False`` liest. Leser, die den Bereich roh nehmen (``cfg.get("log_all_turns")``,
``bool(…)``), lasen ihn als wahr — ein „aus“ wirkte als „an“ (Review 18E-1, S1: das
Sicherheitsprotokoll bekam jeden Zug, ein abgeschalteter Fremdserver blieb im Angebot).

Statt jede Lesestelle einzeln: ``ConfigStore`` normalisiert beim Füllen des Caches jedes Feld, das
das Bereichsmodell als ``bool`` führt — auch in Unterblöcken, Zuordnungen und Listen von Modellen —
mit derselben Regel wie das Gate. Die Datenbank bleibt roh (Editoren lesen sie direkt), ein
unbrauchbarer Wert bleibt stehen (das Gate weist ihn beim nächsten Speichern ab), Felder ohne
Modell (``extra``) bleiben unberührt. Das Original wird nie verändert: geänderte Zweige werden
kopiert.
"""

from __future__ import annotations

import types
from typing import Annotated, Any, Union, get_args, get_origin

from pydantic import BaseModel, RootModel, TypeAdapter, ValidationError

_BOOL = TypeAdapter(bool)


def _kern(typ: Any) -> Any:
    """``Annotated[X, …]`` → ``X``; ``X | None`` → ``X``."""
    while get_origin(typ) is Annotated:
        typ = get_args(typ)[0]
    if get_origin(typ) in (Union, types.UnionType):
        rest = [a for a in get_args(typ) if a is not type(None)]
        if len(rest) == 1:
            return _kern(rest[0])
    return typ


def _wert(typ: Any, wert: Any) -> tuple[Any, bool]:
    """``(neuer Wert, geändert)`` für ``wert`` unter der Typangabe ``typ``."""
    typ = _kern(typ)
    if typ is bool:
        if wert is None or isinstance(wert, bool):
            return wert, False
        try:
            return _BOOL.validate_python(wert), True
        except ValidationError:
            return wert, False
    if isinstance(typ, type) and issubclass(typ, BaseModel):
        return _modell(typ, wert)
    herkunft, argumente = get_origin(typ), get_args(typ)
    if herkunft is dict and isinstance(wert, dict) and len(argumente) == 2:
        neu, geaendert = {}, False
        for schluessel, eintrag in wert.items():
            neu[schluessel], g = _wert(argumente[1], eintrag)
            geaendert |= g
        return (neu, True) if geaendert else (wert, False)
    if herkunft is list and isinstance(wert, list) and len(argumente) == 1:
        paare = [_wert(argumente[0], eintrag) for eintrag in wert]
        if any(g for _e, g in paare):
            return [e for e, _g in paare], True
    return wert, False


def _modell(modell: type[BaseModel], wert: Any) -> tuple[Any, bool]:
    if issubclass(modell, RootModel):
        return _wert(modell.model_fields["root"].annotation, wert)
    if not isinstance(wert, dict):
        return wert, False
    neu: dict[str, Any] | None = None
    for name, feld in modell.model_fields.items():
        schluessel = feld.alias or name
        if schluessel not in wert:
            continue
        ersatz, geaendert = _wert(feld.annotation, wert[schluessel])
        if geaendert:
            if neu is None:
                neu = dict(wert)
            neu[schluessel] = ersatz
    return (neu, True) if neu is not None else (wert, False)


def normalisiere_schalter(bereich: str, daten: dict[str, Any]) -> dict[str, Any]:
    """``daten`` des Bereichs mit gelesenen Schaltern — dasselbe Objekt, wenn nichts zu tun war."""
    from boerdi.domain.config_models import model_for

    modell = model_for(bereich)
    if modell is None or not isinstance(daten, dict):
        return daten
    neu, _geaendert = _modell(modell, daten)
    return neu
