"""Plan 2026-11-15, WF-1 (L8): am Ende eines Ablaufs ohne Arbeitsstand — etwa einer Führung aus
Nachrichten und Seiten — keine Chips „Neues Vorhaben“ und „Arbeitsstand löschen“. Es gibt keinen
Stand, den man löschen oder hinter sich lassen müsste."""

from __future__ import annotations

import asyncio

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.services import vorgang_aktion
from boerdi.services.ablauf import zug
from tests.test_ablauf_zug import (
    _S,
    _req,
    umgebung,  # noqa: F401 — Fixture
)


def _ablauf(schritte):
    return AblaufArea.model_validate({"id": "probe", "titel": {"de": "Probe"}, "aktiv": True,
                                      "ausloeser": [{"art": "knopf"}], "schritte": schritte})


def test_ohne_arbeitsstand_keine_vorgangs_chips(umgebung):  # noqa: F811 — Fixture
    a = _ablauf([{"id": "a", "typ": "nachricht", "text": {"de": "Hallo."}},
                 {"id": "e", "typ": "ende", "text": {"de": "Fertig."}}])
    antwort = asyncio.run(zug.starten_mit(_S(), _req(), {"entities": {}}, a))
    assert "Fertig." in antwort.content
    assert not set(antwort.quick_replies or []) & set(vorgang_aktion.knoepfe("de"))


def test_mit_arbeitsstand_bleiben_die_vorgangs_chips(umgebung):  # noqa: F811 — Fixture
    a = _ablauf([{"id": "t", "typ": "werkzeug", "werkzeug": "abdeckung_zaehlen",
                  "argumente": {"entwurf": {"$teil": "draft"}}, "schreibt": "z", "bei_fehler": "e"},
                 {"id": "e", "typ": "ende", "text": {"de": "Fertig."}}])
    antwort = asyncio.run(zug.starten_mit(_S(), _req(), {"entities": {}}, a))
    assert set(vorgang_aktion.knoepfe("de")) <= set(antwort.quick_replies or [])


def test_getippter_text_ist_ein_arbeitsstand(umgebung):  # noqa: F811 — Fixture
    """Review WF-1, Befund 1: was die Person tippt, steht im Vorgang — dann braucht sie den Weg,
    ihn zu löschen. Eine Wahl schreibt nur die Beschriftung der Redaktion und zählt nicht."""
    from boerdi.services.ablauf.zug_basis import hat_arbeitsstand

    wahl = [{"id": "w", "typ": "nachricht", "text": {"de": "?"}, "schreibt": "gruppe",
             "optionen": [{"id": "a", "label": {"de": "A"}, "ziel": "e"}]},
            {"id": "e", "typ": "ende", "text": {"de": "Fertig."}}]
    assert not hat_arbeitsstand(_ablauf(wahl))
    frei = [{**wahl[0], "freitext": {"ziel": "e", "schreibt": "gruppe"}}, wahl[1]]
    assert hat_arbeitsstand(_ablauf(frei))
