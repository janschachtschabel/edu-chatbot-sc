"""Audit F-6: die gespeicherte Nachricht auf den ausgelieferten Stand nachziehen.

``persist_and_build_response`` speichert die Assistenz-Nachricht, BEVOR die Karten
nach ``display_rules.groups`` beschnitten werden und bevor der M16-Resolver läuft
(der die Karten ganz ersetzen und eine Schwimmlinien-Ansicht bauen kann). Die
Antwort des Zuges trägt also den Endstand, ``GET /messages`` nach einem Reload
aber den Stand davor — der Nutzer sah nach dem Neuladen eine andere Kartenmenge
als im Gespräch, und bei einem Themenseiten-Zug gar keine Schwimmlinien.

Entschieden wurde (Nutzer, 2026-08-12) der Nachtrag: das erste Speichern bleibt,
wo es ist — es ist die Absturzsicherheit des Zuges, denn der M16-Resolver ist
NICHT in ein ``try/except`` gefasst. Danach zieht ein kleines UPDATE den
Endstand nach. Scheitert es, kostet das die Wiederherstellungs-Ansicht, niemals
den Zug.

Ohne DB (Attrappen-Sitzung), läuft darum immer.
"""

from __future__ import annotations

import asyncio

import pytest


def _run(coro):
    return asyncio.run(coro)


class _Sitzung:
    """Merkt sich Adds/Updates und ob zurückgerollt wurde."""

    def __init__(self, execute_fails: bool = False) -> None:
        self.added: list = []
        self.statements: list = []
        self.commits = 0
        self.rollbacks = 0
        self._execute_fails = execute_fails

    def add(self, obj) -> None:
        # Postgres vergibt die Id beim Flush; die Attrappe tut es beim Add.
        obj.id = 4711
        self.added.append(obj)

    async def execute(self, stmt):
        if self._execute_fails:
            raise RuntimeError("Verbindung weg")
        self.statements.append(stmt)
        return None

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


def test_save_message_liefert_die_id_zurueck() -> None:
    """Ohne Id kein Nachtrag — der Aufrufer muss die Zeile wiederfinden."""
    from boerdi.services.db_sessions import save_message

    sess = _Sitzung()
    neu = _run(save_message(sess, "bb-1", "assistant", "Text", cards=[{"id": "a"}]))
    assert neu == 4711
    assert sess.commits == 1


def test_finalize_message_schreibt_den_endstand() -> None:
    from boerdi.services.db_sessions import finalize_message

    sess = _Sitzung()
    ok = _run(finalize_message(
        sess, 4711, cards=[{"id": "b"}], debug={"_topic_page_view": {"title": "T"}},
    ))
    assert ok is True
    assert len(sess.statements) == 1
    assert sess.commits == 1
    assert sess.rollbacks == 0


def test_finalize_message_reisst_den_zug_nicht_mit() -> None:
    """Die Nachricht liegt bereits sicher auf der Platte. Ein gescheiterter
    Nachtrag darf weder werfen noch die Sitzung vergiftet zurücklassen — sonst
    scheitert alles, was der Zug danach noch schreibt (Audit F-1)."""
    from boerdi.services.db_sessions import finalize_message

    sess = _Sitzung(execute_fails=True)
    ok = _run(finalize_message(sess, 4711, cards=[], debug={}))
    assert ok is False
    assert sess.rollbacks == 1


@pytest.mark.parametrize("vorher,nachher,erwartet", [
    ([{"id": "a"}, {"id": "b"}], [{"id": "a"}], True),   # Trim hat gekürzt
    ([{"id": "a"}], [{"id": "a"}], False),               # nichts verändert
    ([{"id": "a"}], [], True),                            # M16 hat ersetzt
])
def test_aenderungs_erkennung(vorher, nachher, erwartet) -> None:
    """Die Bedingung, die den zweiten Schreibvorgang auslöst."""
    from boerdi.services.turn_persist import _needs_finalize

    assert _needs_finalize(vorher, nachher, {}, {}) is erwartet


def test_aenderungs_erkennung_sieht_auch_die_themenseiten_ansicht() -> None:
    from boerdi.services.turn_persist import _needs_finalize

    assert _needs_finalize([], [], {}, {"_topic_page_view": {"title": "T"}}) is True
