"""Nähe Material → Punkt über Einbettungen (Paket N3, Plan 2026-11-19; aus
``strukturentwurf_zuordnung`` gelöst im Review vom 19.11.).

- **Schwelle je Modell** (:data:`SCHWELLEN`): Kosinus-Werte verschiedener Einbettungsmodelle haben
  verschiedene Skalen. Nachgezogen wird nur mit einem gemessenen Modell; sonst nicht (eine
  Log-Zeile). Messen mit dem eingestellten Modell (``LLM_EMBED_MODEL``):
  ``uv run python scripts/zuordnung_messen.py`` (Beispielsatz) und
  ``uv run python scripts/zuordnung_messen_echt.py`` (echte WLO-Materialien, Kalibrierung und
  Prüfung getrennt), dann die Schwelle hier eintragen.
- **Frist:** der Aufruf endet spätestens am Fristende des Dienstes, höchstens nach
  :data:`OBERGRENZE_S` (zweites Review: hängt der Anbieter, kommt der Entwurf ohne Nachziehen statt
  die Frist des Laufs aufzubrauchen). Auf einen LLM-Platz wartet er nur :data:`PLATZ_S` — kürzer als
  die Frist des Betriebs (``LLM_SLOT_WAIT_S``), so scheitert bei Last nur er, der Zug gilt nicht als
  ausgelastet (``llm_parallel._anstellen``, wie die Zustimmungsprüfung, Review 19-5). Unter
  :data:`MINDEST_REST_S` Restzeit kein Aufruf.
- **Rechnen mit numpy:** einmal normieren, eine Matrix Materialien × Punkte, ``argmax`` — 500 × 30
  Vektoren in Millisekunden, die Ereignisschleife steht nicht. Bei Gleichstand gewinnt der zuerst
  stehende Punkt (``argmax`` nimmt den ersten).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from typing import Any, Final

import numpy as np

logger = logging.getLogger(__name__)

#: Kosinus-Ähnlichkeit je Einbettungsmodell, ab der ein Material einem Punkt gehört. Gewählt am
#: 19.11.2026 (Notiz Paket N3, zweites Review) NUR an der Kalibrierhälfte der echten
#: WLO-Materialien (``scripts/zuordnung_messen_echt.py``): text-embedding-3-small 0,36 — die Mitte
#: des besten Bereichs dort; unabhängig geprüft an der anderen Hälfte (97 %) und am Beispielsatz
#: (``scripts/zuordnung_messen.py``, 100 %).
SCHWELLEN: Final[dict[str, float]] = {"text-embedding-3-small": 0.36}
#: Rundung: 0,370 gilt als 0,37 (Vektoren aus Gleitkomma treffen die Schwelle nie genau).
TOLERANZ: Final = 1e-9
#: Unter dieser Restzeit (s) bis zum Fristende entfällt die Einbettung.
MINDEST_REST_S: Final = 1.0
#: So lange (s) dauert die Einbettung höchstens, auch bei langer Frist des Dienstes.
OBERGRENZE_S: float = 10.0
#: So lange (s) wartet sie höchstens auf einen LLM-Platz.
PLATZ_S: Final = 2.5
#: Anteil der Frist des Betriebs, die der Aufruf höchstens auf einen Platz wartet (< 1).
_PLATZ_ANTEIL: Final = 0.5
#: Phase der Einbettung im Zähler des Zugs (``usage_acc``).
PHASE: Final = "strukturentwurf_zuordnung"

#: Texte → je Text ein Vektor (gleiche Reihenfolge); wirft bei jedem Fehler.
Einbetten = Callable[[list[str]], Awaitable[Sequence[Sequence[float]]]]


def schwelle(modell: str | None) -> float | None:
    """Die gemessene Schwelle des Modells (auch mit Präfix ``openai/``) — ``None`` ungemessen."""
    name = str(modell or "").rsplit("/", 1)[-1].strip()
    return SCHWELLEN.get(name)


def kosinus(a: Sequence[float], b: Sequence[float]) -> float:
    va, vb = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    betrag = float(np.linalg.norm(va) * np.linalg.norm(vb))
    return float(va @ vb) / betrag if betrag else 0.0


def _normiert(m: np.ndarray) -> np.ndarray:
    laenge = np.linalg.norm(m, axis=1, keepdims=True)
    return m / np.where(laenge == 0, 1.0, laenge)


def beste_punkte(punkte: Sequence[Sequence[float]], materialien: Sequence[Sequence[float]],
                 grenze: float) -> list[int | None]:
    """Je Material die Stelle des ähnlichsten Punkts — ``None`` unter ``grenze``. Wirft
    ``ValueError`` bei Vektoren ungleicher Länge."""
    p, m = np.asarray(punkte, dtype=float), np.asarray(materialien, dtype=float)
    if p.ndim != 2 or m.ndim != 2 or p.shape[1] != m.shape[1]:
        raise ValueError("Vektoren ungleicher Form")
    aehnlich = _normiert(m) @ _normiert(p).T
    beste = aehnlich.argmax(axis=1)
    werte = aehnlich[np.arange(len(m)), beste]
    return [int(b) if w >= grenze - TOLERANZ else None for b, w in zip(beste, werte, strict=True)]


def _platz_frist(rest: float) -> float:
    """Kürzer als die Frist des Betriebs — sonst setzte ein Ablauf den Zug auf „ausgelastet“."""
    from boerdi.settings import get_settings

    betrieb = get_settings().llm_slot_wait_s
    frist = min(max(rest, 0.0), PLATZ_S)
    return frist if betrieb <= 0 else min(frist, betrieb * _PLATZ_ANTEIL)


def einbetten_mit(usage_acc: dict[str, Any] | None, frist_ende: float | None = None) -> Einbetten:
    """Die echte Naht: ``llm_einbettungen`` (ein Aufruf), gebucht im Zähler des Zugs, mit kurzer
    Geduld für den Platz (bis ``frist_ende``, höchstens die Hälfte der Frist des Betriebs)."""

    async def rufe(texte: list[str]) -> list[list[float]]:
        from boerdi.services import llm_einbettungen

        platz = None
        if frist_ende is not None:
            platz = _platz_frist(frist_ende - asyncio.get_running_loop().time())
        return await llm_einbettungen.einbettungen(texte, usage_acc=usage_acc, phase=PHASE,
                                                   platz_frist_s=platz)

    return rufe


async def naechste(punkt_texte: list[str], material_texte: list[str], einbetten: Einbetten | None,
                   *, modell: str, frist_ende: float | None = None) -> list[int | None] | None:
    """Je Material die Stelle des nächsten Punkts (oder ``None``) — ``None`` insgesamt ohne
    Nachziehen: kein Material, keine Naht, ungemessenes Modell, zu wenig Zeit, Ausfall."""
    if not material_texte or not punkt_texte or einbetten is None:
        return None
    if (grenze := schwelle(modell)) is None:
        logger.info("Zuordnung: keine gemessene Schwelle für %s — ohne Nachziehen", modell[:60])
        return None
    texte = punkt_texte + material_texte
    jetzt = asyncio.get_running_loop().time()
    # zweites Review, MINOR 1: eigene Obergrenze, auch bei langer (oder ohne) Frist des Dienstes
    ende = jetzt + OBERGRENZE_S if frist_ende is None else min(frist_ende, jetzt + OBERGRENZE_S)
    if ende - jetzt < MINDEST_REST_S:
        logger.info("Zuordnung: zu wenig Zeit für die Einbettung")
        return None
    try:
        async with asyncio.timeout_at(ende):
            vektoren = list(await einbetten(texte))
        if len(vektoren) != len(texte):
            raise ValueError(f"{len(vektoren)} Vektoren für {len(texte)} Texte")
        return beste_punkte(vektoren[:len(punkt_texte)], vektoren[len(punkt_texte):], grenze)
    except Exception as e:  # noqa: BLE001 — Frist, Last (LlmAusgelastet), Anbieter: ohne Nachziehen
        logger.info("Zuordnung: Einbettung ohne Ergebnis (%s)", type(e).__name__)
        return None
