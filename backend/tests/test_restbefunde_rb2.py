"""Paket RB-2 (2026-11-09): die Sicht „Daten“ im Studio nennt Typen beim Namen.

Drift-Wächter: jeder Typ, den ``services/ablauf/typen`` kennt, hat im Studio einen Namen
(``ablauf-daten.component.ts``, ``TYP_NAMEN``) — ein neuer Typ ohne Namen fiele dort auf die
Kennung zurück (kein Fehler, aber unlesbar).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from boerdi.services.ablauf import typen

STUDIO = (Path(__file__).resolve().parents[2] / "frontend" / "projects" / "studio" / "src" / "app"
          / "schema-form" / "ablauf-daten.component.ts")


def _typen(wert: Any) -> set[str]:
    """Alle Typkennungen in ``wert`` (auch verschachtelt): ``text`` oder ``…@<n>``."""
    if isinstance(wert, str):
        return {wert} if wert == typen.TEXT or re.fullmatch(r"[a-z0-9_.-]+@\d+", wert) else set()
    if isinstance(wert, dict):
        return {t for x in wert.values() for t in _typen(x)}
    if isinstance(wert, (list, tuple, set, frozenset)):
        return {t for x in wert for t in _typen(x)}
    return set()


def _studio_namen() -> set[str]:
    """Die Schlüssel des Blocks ``TYP_NAMEN = {…}`` — nicht irgendein Treffer in der Datei."""
    quelle = STUDIO.read_text(encoding="utf-8")
    block = re.search(r"TYP_NAMEN[^=]*=\s*\{(.*?)\n\};", quelle, re.S)
    assert block, "TYP_NAMEN nicht gefunden"
    return set(re.findall(r"^\s*'([^']+)':", block.group(1), re.M))


def test_jeder_bekannte_typ_hat_im_studio_einen_namen():
    """Review RB-2, Befund 5: die Typen selbst einsammeln — eine Handliste vergäße neue."""
    bekannt = {t for name, wert in vars(typen).items() if name.isupper() for t in _typen(wert)}
    assert {typen.TEXT, typen.START, typen.STRUKTURABGLEICH, typen.ANGELEGT} <= bekannt
    fehlt = sorted(bekannt - _studio_namen())
    assert not fehlt, f"ohne Namen im Studio: {fehlt}"
