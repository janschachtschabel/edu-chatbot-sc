"""Dienst ``upload_angebot`` (Paket U3-1b, Plan 2026-11-04 §16.5): Auswahlfeld von ``ui_upload``.

Die KI nennt nur den Zweck und einen Satz an die Person; Grenzen und Schalter setzt das Backend.
``dokument_im_chat`` folgt dem Studio-Bereich ``01-base/upload-config`` (U3-2a) und der Anmeldung:
ohne sie nur, wenn ``dokument_ohne_anmeldung`` an ist. ``ablage_in_wlo`` (U3-3b) folgt dem
Studio **und** der bestätigten Anmeldung — ohne sie nie; ``grenzen.max_mb_ablage`` ist die
Größe je Datei, die ``/api/ui/ablage/datei`` annimmt. Ganz an- und abschalten lässt sich das
Modul über den Modul-Schalter des Studios. Die Endpunkte ``/api/ui/dokumente`` und
``/api/ui/ablage/*`` prüfen dieselben Schalter noch einmal.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from boerdi.api.schemas_debug import ToolOutcome
from boerdi.domain.ui_bloecke import neuer_block
from boerdi.services.config_loader.upload import load_upload_config
from boerdi.services.mcp.auth import has_personal_auth
from boerdi.ui_module import katalog
from boerdi.ui_module.datenquelle import Ergebnis
from boerdi.ui_module.katalog import Manifest

if TYPE_CHECKING:
    from boerdi.ui_module.aufruf import Umgebung

GRENZEN: Final = {"max_dateien": 500, "max_tiefe": 8, "max_mb_datei": 50}

#: Textfassung für Widgets ohne das Modul (ältere Einbettung, Bündel nicht ladbar).
TEXTFASSUNG: Final = ("Hier würde ein Auswahlfeld für einen Ordner erscheinen. Lädt es nicht, "
                      "bitte das Chat-Fenster neu laden.")
QUITTUNG: Final = ("OK: Unter deiner Antwort steht ein Auswahlfeld, in dem die Person einen "
                   "Ordner wählen oder ablegen kann; hochgeladen wird dabei nichts. Sag in einem "
                   "Satz, was sie tun soll. Ihr Befund (Ordner und Zahlen) kommt im nächsten Zug. "
                   "Dein Zug endet hier — rufe kein weiteres Werkzeug.")
FEHLER: Final = "Fehler: Das Auswahlfeld ließ sich nicht erzeugen. Antworte ohne es."


def dokument_erlaubt() -> bool:
    """Darf diese Person in diesem Zug ein Dokument im Chat verwerten? (Studio + Anmeldung)"""
    cfg = load_upload_config()
    return cfg.dokument_im_chat and (cfg.dokument_ohne_anmeldung or has_personal_auth())


def schalter() -> dict[str, bool]:
    return {"dokument_im_chat": dokument_erlaubt(),
            "ablage_in_wlo": load_upload_config().ablage_in_wlo and has_personal_auth()}


async def upload_angebot(manifest: Manifest, args: dict[str, Any], umgebung: Umgebung
                         ) -> Ergebnis:
    modul = manifest["name"]
    grenzen = {**GRENZEN, "max_mb_ablage": load_upload_config().max_mb}
    daten: dict[str, Any] = {"zweck": args["zweck"], "grenzen": grenzen, "schalter": schalter()}
    if hinweis := " ".join(str(args.get("hinweis") or "").split()):
        daten["hinweis"] = hinweis[:300]
    if katalog.daten_fehler(manifest, daten):
        return Ergebnis(None, FEHLER, ToolOutcome(tool=modul, status="error", error="abweichung"))
    block = neuer_block(modul, manifest["version"], manifest["art"], daten, TEXTFASSUNG)
    return Ergebnis(block, QUITTUNG + _was_geht(daten["schalter"]),
                    ToolOutcome(tool=modul, status="success", item_count=1))


def _was_geht(schalter: dict[str, bool]) -> str:
    """Gesamt-Review U3/U4/U5, Befund 5: die KI erfährt, was im Auswahlfeld geht — sonst
    verspräche sie anonym, einen Lehrplan zu lesen oder nach WLO zu übertragen."""
    saetze = []
    if not schalter.get("dokument_im_chat"):
        saetze.append("Ein Dokument (z. B. einen Lehrplan) lesen lassen geht hier nicht"
                      + ("" if has_personal_auth() else " ohne WLO-Anmeldung"))
    if not schalter.get("ablage_in_wlo"):
        saetze.append("Übertragen nach WLO geht hier nicht"
                      + ("" if has_personal_auth() else " ohne WLO-Anmeldung"))
    return (" " + "; ".join(saetze) + " — sag das, wenn es danach fragt.") if saetze else ""
