"""Dienst ``upload_angebot`` (Paket U3-1b, Plan 2026-11-04 §16.5): Auswahlfeld von ``ui_upload``.

Die KI nennt nur den Zweck und einen Satz an die Person; Grenzen und Schalter setzt das Backend.
Seit Plan 2026-11-16, TG-2, ist der Zweck neutral ``bereitstellen`` (``sammlungsstruktur`` bleibt
gültig): das Feld stellt Daten bereit, was damit geschieht, klärt die KI danach.
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
from boerdi.services.mcp import faehigkeiten
from boerdi.services.mcp.auth import has_personal_auth
from boerdi.ui_module import katalog
from boerdi.ui_module.datenquelle import Ergebnis
from boerdi.ui_module.katalog import Manifest

if TYPE_CHECKING:
    from boerdi.ui_module.aufruf import Umgebung

GRENZEN: Final = {"max_dateien": 500, "max_tiefe": 8, "max_mb_datei": 50}
#: Das erste Werkzeug der Stapel-Ablage (``services/ablage/mcp_ablage``).
ABLAGE_WERKZEUG: Final = "wlo_prepare_file_batch"

#: Textfassung für Widgets ohne das Modul (ältere Einbettung, Bündel nicht ladbar).
TEXTFASSUNG: Final = ("Hier würde ein Auswahlfeld für einen Ordner erscheinen. Lädt es nicht, "
                      "bitte das Chat-Fenster neu laden.")
QUITTUNG: Final = ("OK: Unter deiner Antwort steht ein Auswahlfeld, in dem die Person einen "
                   "Ordner wählen oder ablegen kann; hochgeladen wird nur, was sie ausdrücklich "
                   "lesen lässt oder nach WLO überträgt. Sag in einem "
                   "Satz, was sie tun soll. Ihr Befund (Ordner und Zahlen) kommt im nächsten Zug. "
                   "Dein Zug endet hier — rufe kein weiteres Werkzeug.")
FEHLER: Final = "Fehler: Das Auswahlfeld ließ sich nicht erzeugen. Antworte ohne es."


def dokument_erlaubt() -> bool:
    """Darf diese Person in diesem Zug ein Dokument im Chat verwerten? (Studio + Anmeldung)"""
    cfg = load_upload_config()
    return cfg.dokument_im_chat and (cfg.dokument_ohne_anmeldung or has_personal_auth())


def nicht_gelesen_satz() -> str:
    """Satz an die KI, wenn ein Strukturdokument markiert, aber nicht gelesen wurde (Probe
    2026-11-10): ohne den Grund bat sie, es noch einmal zu wählen — eine Schleife, solange das
    Lesen an der Anmeldung hing. Gerechnet im laufenden Zug, wie ``schalter()``."""
    if not load_upload_config().dokument_im_chat:
        return ("Das Strukturdokument wurde NICHT gelesen: Dokumente lesen ist in diesem Chat "
                "abgeschaltet. Sag das der Person; biete das Auswahlfeld dafür nicht noch "
                "einmal an.")
    if not dokument_erlaubt():
        return ("Das Strukturdokument wurde NICHT gelesen: das geht nur mit WLO-Anmeldung, und "
                "die Person ist hier nicht (bestätigt) angemeldet. Sag ihr, dass sie sich zuerst "
                "mit ihrem WLO-Konto anmelden muss; danach kann sie es im Auswahlfeld lesen "
                "lassen. Bitte sie bis dahin nicht, es noch einmal auszuwählen oder zu "
                "markieren.")
    # Review Probe 2026-11-10, Befund 2: gerechnet mit dem Stand dieses Zugs — beim Zeigen des
    # Moduls kann der Knopf gefehlt haben (alte Vorgabe, Anmeldung dazwischen); darum nicht
    # behaupten, sie habe ihn übergangen. Plan 2026-11-16, TG-2: neutral, der Knopf hat kein Ziel;
    # Review M3 (d): das Feld erst auf Wunsch zeigen (wie „Entwirf nichts ungefragt“).
    return ("Das Strukturdokument wurde NICHT gelesen. Braucht die Person seinen Inhalt, sag ihr, "
            "dass sie es im Auswahlfeld mit „Lesen lassen“ lesen lassen kann; zeige ui_upload "
            "dafür erst, wenn sie das will.")


def _ohne_grund(cfg_an: bool, anmeldung_hilft: bool) -> str:
    """Der Grund einer Absage für die Quittung (Review Probe 2026-11-10, Befund 1): die Anmeldung
    nur, wo sie hilft — sonst schickte die KI die Person zur Anmeldung, die nichts ändert."""
    if not cfg_an:
        return " (im Chat abgeschaltet)"
    return "" if has_personal_auth() or not anmeldung_hilft else " ohne WLO-Anmeldung"


def schalter() -> dict[str, bool]:
    cfg = load_upload_config()
    # Rückmeldung 16.11. (Review m6): die Ablage nur, wenn der MCP-Server die Stapel-Ablage führt
    ablage = cfg.ablage_in_wlo and faehigkeiten.kennt_werkzeug(ABLAGE_WERKZEUG)
    werte = {"dokument_im_chat": dokument_erlaubt(),
             "ablage_in_wlo": ablage and has_personal_auth()}
    if cfg.dokument_im_chat and not cfg.dokument_ohne_anmeldung and not has_personal_auth():
        # Paket R3-b: den Hinweis schreibt die KI, bevor sie die Schalter kennt — das Modul nennt
        # gleich darunter, dass Lesen erst nach der Anmeldung geht
        werte["lesen_nach_anmeldung"] = True
    if ablage and not has_personal_auth():
        # Rückmeldung 16.11.: die Ablage ist ab Werk an — ohne Anmeldung nennt das Feld die
        # Voraussetzung, statt den Weg zu verstecken
        werte["ablage_nach_anmeldung"] = True
    return werte


async def upload_angebot(manifest: Manifest, args: dict[str, Any], umgebung: Umgebung
                         ) -> Ergebnis:
    modul = manifest["name"]
    grenzen = {**GRENZEN, "max_mb_ablage": load_upload_config().max_mb}
    daten: dict[str, Any] = {"zweck": args["zweck"], "grenzen": grenzen, "schalter": schalter()}
    if hinweis := " ".join(str(args.get("hinweis") or "").split()):
        daten["hinweis"] = hinweis[:300]
    # Review 12.11., Befund 1: nur der Dokument-Ablauf will eine Einzeldatei als Strukturdokument —
    # und nur aus dem Ablauf heraus (Review TW-6, Befund 7: die KI sieht das Feld, es wirkt nicht)
    if args.get("einzeldatei_als_struktur") is True and umgebung.aus_ablauf:
        daten["einzeldatei_als_struktur"] = True
    if katalog.daten_fehler(manifest, daten):
        return Ergebnis(None, FEHLER, ToolOutcome(tool=modul, status="error", error="abweichung"))
    block = neuer_block(modul, manifest["version"], manifest["art"], daten, TEXTFASSUNG)
    schalter_ = daten["schalter"]
    return Ergebnis(block, QUITTUNG + _was_geht(schalter_) + _ablage_satz(schalter_),
                    ToolOutcome(tool=modul, status="success", item_count=1))


def _ablage_satz(schalter: dict[str, bool]) -> str:
    """Rückmeldung 16.11. (Review m5): die Ablage ist ab Werk an — die KI soll sie nicht verneinen
    und die Voraussetzung kennen."""
    if schalter.get("ablage_in_wlo"):
        # Paket K3: Metadaten erzeugt ein Flow — nur, wenn ein Träger ihn starten kann (der MCP).
        # Die Ablage selbst hängt nicht daran.
        from boerdi.services.ablauf import zug_basis

        satz = (" Die Person kann die erfassten Dateien im Feld in ihren persönlichen Bereich in "
                "WLO übertragen; dort entstehen Volltexte")
        return satz + (" und auf Wunsch Metadaten." if zug_basis.wlo_erschliessen() else
                       ". Metadaten erzeugen geht hier gerade nicht — versprich keine.")
    if schalter.get("ablage_nach_anmeldung"):
        return " Nach WLO übertragen kann sie die Dateien, wenn sie bei WLO angemeldet ist."
    return ""


def _was_geht(schalter: dict[str, bool]) -> str:
    """Gesamt-Review U3/U4/U5, Befund 5: die KI erfährt, was im Auswahlfeld geht — sonst
    verspräche sie anonym, einen Lehrplan zu lesen oder nach WLO zu übertragen."""
    saetze = []
    cfg = load_upload_config()
    if not schalter.get("dokument_im_chat"):
        saetze.append("Ein Dokument (z. B. einen Lehrplan) lesen lassen geht hier nicht"
                      + _ohne_grund(cfg.dokument_im_chat, not cfg.dokument_ohne_anmeldung))
    if not schalter.get("ablage_in_wlo"):
        saetze.append("Übertragen nach WLO geht hier nicht"
                      + _ohne_grund(cfg.ablage_in_wlo, True))
    return (" " + "; ".join(saetze) + " — sag das, wenn es danach fragt.") if saetze else ""
