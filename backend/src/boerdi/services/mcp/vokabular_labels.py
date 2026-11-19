"""Fach und Bildungsstufe aus dem WLO-Vokabular (Plan 2026-11-19, N2).

Quelle ist der Puffer des Filter-Resolvers (``arg_resolvers``: ``lookup_wlo_vocabulary``, beim
Start vorgewärmt, Ergebnis 24 h gepuffert). Diese Schicht liefert daraus

- :func:`labels` — die Labels eines Vokabulars als geschlossene Liste (für einen Prompt),
- :func:`fach` / :func:`stufe` — einen freien Wert abgebildet auf das Label des Vokabulars, und
- :func:`fach_geprueft` / :func:`stufe_geprueft` — dasselbe als :class:`Abbildung`, mit dem
  verworfenen Wert, damit ein Aufrufer ihn als Hinweis nennen kann.

**Fürs Schreiben nur genau oder über Alias** (ohne Groß-/Kleinschreibung, Leerraum vereinheitlicht).
Die Wortregeln des Filter-Resolvers (``_fuzzy_lookup``, Stufen 2 und 3) gelten hier nicht —
gemessen am echten Vokabular (Review N1/N2, 19.11.): „Technik“ → Arbeitslehre, „Geschichte/Politik“
→ Geschichte, „Politik und Wirtschaft“ → Politik, „Sekundarstufe I und II“ → Sekundarstufe I. Ein
Filter verträgt das, ein geschriebenes Fach nicht. Kein Treffer → leer.

Ohne Vokabular (MCP nicht erreichbar, leere Antwort, Frist) gilt, was vorher galt: die Prüfer des
Entwurfs (``ui_module/strukturentwurf.fach``/``bildungsstufe``). Die Stufe geht zuerst durch
deren Synonyme („Sek I“ → „Sekundarstufe I“), dann durch das Vokabular.

simplify: liest die Modul-Puffer von ``arg_resolvers`` direkt (wie ``bezeichnung_bekannt``), statt
sie in ein eigenes Modul zu ziehen — ``arg_resolvers`` ist groß, ein Umzug wäre ein eigenes Paket.
"""

from __future__ import annotations

import asyncio
import logging
import time
import weakref
from dataclasses import dataclass
from typing import Any, Final

from boerdi.services.mcp import arg_resolvers as ar
from boerdi.ui_module import strukturentwurf

logger = logging.getLogger(__name__)

FACH: Final = "discipline"
STUFE: Final = "educationalContext"
#: Höchstens so lange wartet ein Aufrufer auf das erste Laden (ein Hochladen soll nicht an einem
#: hängenden MCP-Server stehen); danach gilt „kein Vokabular“.
FRIST_S: Final = 5.0
#: Nach einem Fehlschlag (Frist, Fehlertext, leeres Vokabular) gilt so lange „kein Vokabular“, ohne
#: neuen Versuch — sonst wartete jede Inhaltsdatei erneut bis zu :data:`FRIST_S` auf den MCP.
SPERRE_S: Final = 60.0

#: Vokabular → Zeitpunkt (``_jetzt``), bis zu dem nach einem Fehlschlag nicht neu geladen wird.
_fehlschlag_bis: dict[str, float] = {}
#: Je Ereignisschleife und Vokabular eine Sperre: gleichzeitige Aufrufe laden einmal.
_sperren: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, dict[str, asyncio.Lock]] = (
    weakref.WeakKeyDictionary())


def _jetzt() -> float:
    return time.monotonic()


def _sperre(vocab: str) -> asyncio.Lock:
    je_vokabular = _sperren.setdefault(asyncio.get_running_loop(), {})
    return je_vokabular.setdefault(vocab, asyncio.Lock())


@dataclass(frozen=True)
class Vokabular:
    #: Label oder Alias (klein) → URI.
    schluessel: dict[str, str]
    #: URI → Label in der Schreibweise des Servers.
    labels: dict[str, str]


@dataclass(frozen=True)
class Abbildung:
    """Ergebnis von :func:`fach_geprueft`/:func:`stufe_geprueft`. ``label``: der Wert zum
    Schreiben oder ``None``. ``verworfen``: der eingegebene Wert (einzeilig), wenn ein Vokabular
    da ist und ihn nicht führt — sonst ``None`` (leer, Treffer, oder kein Vokabular)."""

    label: str | None
    verworfen: str | None = None


async def _laden(vocab: str) -> None:
    if ar._label_cache_loaded.get(vocab):
        return
    async with _sperre(vocab):
        if ar._label_cache_loaded.get(vocab) or _jetzt() < _fehlschlag_bis.get(vocab, 0.0):
            return  # ein gleichzeitiger Aufruf hat schon geladen oder ist gescheitert
        try:
            async with asyncio.timeout(FRIST_S):
                await ar._ensure_label_cache(vocab)
        except TimeoutError:
            logger.info("Vokabular %s: Laden dauerte über %.0f s", vocab, FRIST_S)


async def _vokabular(vocab: str) -> Vokabular | None:
    """Das geladene Vokabular — ``None``, wenn es (noch) keines gibt. Die Naht der Tests."""
    if _jetzt() < _fehlschlag_bis.get(vocab, 0.0):
        return None
    await _laden(vocab)
    labels = ar._uri_to_label.get(vocab) or {}
    if not ar._label_cache_loaded.get(vocab) or not labels:
        _fehlschlag_bis[vocab] = _jetzt() + SPERRE_S
        return None
    _fehlschlag_bis.pop(vocab, None)
    return Vokabular(schluessel=ar._label_to_uri_cache.get(vocab) or {}, labels=labels)


async def labels(vocab: str) -> list[str] | None:
    """Die Labels des Vokabulars, alphabetisch — ``None`` ohne Vokabular."""
    vok = await _vokabular(vocab)
    return sorted(set(vok.labels.values()), key=str.casefold) if vok else None


def _zeile(wert: Any) -> str:
    return " ".join(wert.split()) if isinstance(wert, str) else ""


def _abgebildet(vok: Vokabular, wert: str) -> Abbildung:
    if not wert:
        return Abbildung(label=None)
    uri = vok.schluessel.get(ar._norm_label(wert))
    label = vok.labels.get(uri) if uri else None
    return Abbildung(label=label, verworfen=None if label else wert)


async def fach_geprueft(wert: Any) -> Abbildung:
    """Das Fach-Label des Vokabulars zu ``wert``, mit verworfenem Wert — ohne Vokabular wie
    ``strukturentwurf.fach`` (dann nie ``verworfen``)."""
    vok = await _vokabular(FACH)
    if vok is None:
        return Abbildung(label=strukturentwurf.fach(wert))
    return _abgebildet(vok, _zeile(wert))


async def stufe_geprueft(wert: Any) -> Abbildung:
    """Das Bildungsstufen-Label des Vokabulars zu ``wert``, mit verworfenem Wert — ohne Vokabular
    wie ``strukturentwurf.bildungsstufe`` (dann nie ``verworfen``)."""
    bekannt = strukturentwurf.bildungsstufe(wert)
    vok = await _vokabular(STUFE)
    if vok is None:
        return Abbildung(label=bekannt)
    abbildung = _abgebildet(vok, bekannt or _zeile(wert))
    return Abbildung(label=abbildung.label,
                     verworfen=_zeile(wert) if abbildung.verworfen else None)


async def fach(wert: Any) -> str | None:
    """Nur das Label von :func:`fach_geprueft`."""
    return (await fach_geprueft(wert)).label


async def stufe(wert: Any) -> str | None:
    """Nur das Label von :func:`stufe_geprueft`."""
    return (await stufe_geprueft(wert)).label
