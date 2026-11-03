"""Testhilfe (U1-b2): die Dokument-Boxen einer Antwort — Inhaltsrahmen-Blöcke an ``ui``."""

from __future__ import annotations

from types import SimpleNamespace


def boxen(resp) -> list[SimpleNamespace]:
    """Je Inhaltsrahmen-Block eine Box mit ``kind``/``title``/``content`` wie früher."""
    return [SimpleNamespace(kind=b.daten["art"], title=b.daten["titel"],
                            content=b.daten["markdown"])
            for b in resp.ui.ui_bloecke if b.modul == "ui_inhaltsrahmen"]
