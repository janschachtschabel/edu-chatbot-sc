"""Paket K6 (Plan 2026-11-17, E16): „k von n fertig“ an ``POST /api/ui/auftrag/stand``.

Der Stand eines Auftrags über den MCP trägt ``progress`` (``client.Stand.fortschritt``, Teil a).
Die Antwort des Endpunkts nennt ihn als zwei Zahlen ``fertig``/``gesamt`` — nie Ausgaben, nie die
Job-ID. Ohne (brauchbaren) Fortschritt bleibt die Antwort wie bisher nur ``stand``.
"""

from __future__ import annotations

import pytest

from boerdi.services.auftraege import client
from tests.test_ui_auftrag_api import _stand, _umgebung, lage, web  # noqa: F401 — Fixtures


def test_der_fortschritt_geht_als_zahlen_hinaus(web, lage):  # noqa: F811
    lage.stand = client.Stand("laeuft", {"jobId": "job-1"}, fortschritt={"fertig": 12,
                                                                         "gesamt": 40})
    r = _stand(web)
    assert r.status_code == 200, r.text
    assert r.json() == {"stand": "laeuft", "fertig": 12, "gesamt": 40}
    assert "job-1" not in r.text


def test_ohne_fortschritt_bleibt_die_antwort_wie_bisher(web, lage):  # noqa: F811
    lage.stand = client.Stand("laeuft")
    assert _stand(web).json() == {"stand": "laeuft"}


@pytest.mark.parametrize("fortschritt", [
    {"fertig": 5, "gesamt": 0},
    {"fertig": 41, "gesamt": 40},
    {"fertig": -1, "gesamt": 40},
    {"fertig": True, "gesamt": 40},
    {"fertig": "12", "gesamt": 40},
    {"gesamt": 40},
])
def test_ein_unbrauchbarer_fortschritt_faellt_weg(web, lage, fortschritt):  # noqa: F811
    lage.stand = client.Stand("laeuft", fortschritt=fortschritt)
    assert _stand(web).json() == {"stand": "laeuft"}


# ── Durchtest Paket K (19.11.): gescheiterte getrennt ──────────────────────────────────────────

def test_gescheiterte_stehen_getrennt(web, lage):  # noqa: F811
    lage.stand = client.Stand("fehler", fortschritt={"fertig": 0, "gesamt": 3,
                                                     "fehlgeschlagen": 3})
    assert _stand(web).json() == {"stand": "fehler", "fertig": 0, "gesamt": 3,
                                  "fehlgeschlagen": 3}


@pytest.mark.parametrize("fehl", [0, 2, -1, True, "1"])
def test_ein_unbrauchbares_fehlgeschlagen_faellt_allein_weg(web, lage, fehl):  # noqa: F811
    lage.stand = client.Stand("laeuft", fortschritt={"fertig": 3, "gesamt": 4,
                                                     "fehlgeschlagen": fehl})
    assert _stand(web).json() == {"stand": "laeuft", "fertig": 3, "gesamt": 4}
