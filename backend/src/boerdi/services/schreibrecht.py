"""Wer im WLO-Bestand schreiben darf (Paket 7, S4 — P5-9, Nutzer-Entscheid 2026-10-09).

Schreiben heißt anlegen, ändern oder in Sammlungen aufnehmen. Es geht in beiden
Modi nur mit einer persönlichen WLO-Anmeldung (:func:`has_personal_auth`). Der
Dienst-Block der Anlage (``MCP_AUTH_TOKEN``) gehört keiner Person; mit ihm
schreibt der Bot nur, wenn das Studio es ausdrücklich erlaubt
(``01-base/engine`` → ``betrieb.gastkonto_schreibt``, Vorgabe aus).

Bis Paket 7 genügte er im Muster-Modus (Audit 2026-09-29, B-H3): die Werkzeuge
standen mit jedem Block im Angebot, und ``redeem_write_approval`` löste ein „ja“
ohne Anmeldung ein. Der Agent-Modus verlangte die Anmeldung schon.

Für ``/api/agent`` gilt das nicht: dort entscheidet der Aufrufer
(``allow_curation``), und ohne Person bleibt es bei der Vorschau
(``agent_write``).
"""

from __future__ import annotations

from boerdi.services import betriebsschalter
from boerdi.services.mcp.auth import handelt_mit_dem_block_der_anlage, has_personal_auth


def schreiben_erlaubt() -> bool:
    """Darf dieser Zug schreibende Werkzeuge anbieten und eine Abnahme einlösen?"""
    if has_personal_auth():
        return True
    # Das Gastkonto ist der Block der Anlage. Ein Zug-Block geht ihm vor, auch der
    # anonyme — mit ihm lehnte der Server ab (Paket 9, Review Paket 7 MINOR 27).
    return betriebsschalter.gastkonto_schreibt() and handelt_mit_dem_block_der_anlage()
