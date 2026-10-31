"""Paket 19 (Audit 2026-10-31, M-6): gespeicherte Nachrichten haben einen Deckel.

``ChatRequest.message`` hat seit dem Entscheid 2026-08-18 keinen Deckel — der Prompt-Weg bleibt so.
Gespeichert wurde aber ebenfalls alles: 2 Routen × 120/min × 2 MiB Rumpf ≈ 480 MB/min je IP in
``messages``, aufgeräumt erst nach der Aufbewahrungsfrist. Jetzt kappt ``save_message`` den
Inhalt der Person (Rolle ``user``)
auf :data:`db_sessions.MAX_GESPEICHERT` Zeichen, mit derselben Kürzungsmarke wie das
Verlaufsfenster — gekürzter Text sieht nie wie vollständiger aus.

Ohne DB (Attrappen-Sitzung) wie ``test_message_privacy_gate.py``.
"""

from __future__ import annotations

import asyncio

import pytest

from boerdi.domain.history_window import KUERZUNGS_HINWEIS
from boerdi.services import config_loader as cl
from boerdi.services import db_sessions


class _Sitzung:
    def __init__(self) -> None:
        self.added: list = []

    def add(self, obj) -> None:
        obj.id = 1
        self.added.append(obj)

    async def commit(self) -> None:
        return None


@pytest.fixture(autouse=True)
def _ohne_store():
    cl.bind_store(None)  # ohne Store: Datenschutz-Vorgabe „speichern“
    yield


def _gespeichert(inhalt: str, role: str = "user") -> str:
    sess = _Sitzung()
    asyncio.run(db_sessions.save_message(sess, "bb-0123456789abcdef", role, inhalt))
    return sess.added[0].content


def test_der_deckel_ist_zwanzigtausend():
    assert db_sessions.MAX_GESPEICHERT == 20_000


def test_lange_nachrichten_der_person_werden_mit_marke_gekappt():
    inhalt = "a" * 2_000_000
    gespeichert = _gespeichert(inhalt, "user")
    assert gespeichert.endswith(KUERZUNGS_HINWEIS)
    assert len(gespeichert) == db_sessions.MAX_GESPEICHERT + len(KUERZUNGS_HINWEIS)


def test_antworten_des_bots_bleiben_ungekuerzt():
    """Review, Punkt 8: der Volltext eines Dokuments (M17, ``content_text_action``) steht als
    Bot-Nachricht im Verlauf und wird im Folgezug gebraucht — die Angriffsfläche ist die Person."""
    inhalt = "c" * 60_000
    assert _gespeichert(inhalt, "assistant") == inhalt


def test_bis_zum_deckel_bleibt_alles():
    inhalt = "b" * db_sessions.MAX_GESPEICHERT
    assert _gespeichert(inhalt) == inhalt
    assert _gespeichert("kurz") == "kurz"
