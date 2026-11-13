"""Die UI-Blöcke eines Ablaufs (aus ``treiber`` gelöst, Querschnitts-Review 2026-11-06, Q4): aus
fertigen Daten gegen den Vertrag des Moduls, über den Dienst eines Moduls ohne Sprachmodell, und
der Fortschritt eines Auftrags.
"""

from __future__ import annotations

from typing import Any

from boerdi.api.schemas_ui import UiBlock
from boerdi.domain.ui_bloecke import neuer_block
from boerdi.services.ablauf import werkzeuge
from boerdi.ui_module import katalog, schalter
from boerdi.ui_module.namen import FORTSCHRITT, STRUKTURENTWURF


def block(modul: str, daten: dict[str, Any]) -> UiBlock | None:
    """Ein Block aus fertigen Daten — geprüft gegen den Vertrag des Moduls."""
    from boerdi.ui_module import strukturentwurf_text as st
    from boerdi.ui_module.werkzeuge import textfassung

    manifest = katalog.katalog().get(modul)
    if manifest is None or katalog.daten_fehler(manifest, daten):
        return None
    text = st.textfassung(daten) if modul == STRUKTURENTWURF else textfassung(manifest, daten)
    return neuer_block(modul, manifest["version"], manifest["art"], daten, text)


async def modul_block(modul: str, daten: dict[str, Any], *,
                      simulation: bool = False) -> UiBlock | None:
    """Erst als fertige Daten, sonst über den Dienst des Moduls — nur für Module ohne Sprachmodell
    (``ui_upload``: Studio-Schalter). Ein ausgeschaltetes Modul baut kein Block.

    ``simulation`` (AS-1): nie über den Dienst — für ein Modul, das der Betrieb über seinen Dienst
    baut, ein Platzhalter-Block mit der Art des Moduls (ein abfragendes wartet wie im Betrieb). Für
    jedes andere gilt wie im Betrieb: passen die Daten nicht, kein Block (``bei_fehler``, Review
    AS-1, Befund 1)."""
    if not schalter.aktiv(modul):
        return None
    if (fertig := block(modul, daten)) is not None:
        return fertig
    if modul not in werkzeuge.MODUL_DIENST_OHNE_MODELL:
        return None
    if simulation:
        manifest = katalog.katalog().get(modul)
        return (None if manifest is None
                else neuer_block(modul, manifest["version"], manifest["art"], daten, ""))
    from boerdi.ui_module import dienst
    from boerdi.ui_module.aufruf import Umgebung as ModulUmgebung
    from boerdi.ui_module.aufruf import asynchron

    manifest = katalog.katalog().get(modul)
    if manifest is None or not dienst.name(manifest):
        return None
    return (await asynchron(modul, daten, ModulUmgebung(aus_ablauf=True))).block


def fortschritt(ablauf_id: str, job_id: str, text: str, sprache: str) -> UiBlock | None:
    """Paket K1b: der Block ``ui_fortschritt`` zu einem gestarteten Auftrag — mit dem Kürzel, nie
    der Job-ID; ``None``, wenn das Modul im Studio aus ist (dann bleibt nur „Stand prüfen“)."""
    from boerdi.i18n import bot_text
    from boerdi.services.auftraege.client import kuerzel

    if not schalter.aktiv(FORTSCHRITT):
        return None
    # Review K1b, Befund 5: das Manifest erlaubt 300 Zeichen — länger fiele der Block still weg.
    satz = (text or bot_text(sprache, "action.ablauf.auftragGestartet"))[:300].rstrip()
    return block(FORTSCHRITT, {"ablauf": ablauf_id, "kuerzel": kuerzel(job_id), "text": satz})
