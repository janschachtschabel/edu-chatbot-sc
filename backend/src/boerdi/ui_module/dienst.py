"""Module mit Dienst (Paket U2, Plan 2026-11-04 T-4): das Backend erzeugt die Block-Daten selbst.

Anders als bei der Datenquelle (``ui_module/datenquelle``, ein MCP-Werkzeug liefert die Daten)
ruft hier ein Dienst des Backends — heute nur ``strukturentwurf`` (``services/
strukturentwurf_dienst``). Die KI sieht nur den Auftrag (``dienst.parameter`` im Manifest); der
Aufruf wird dagegen geprüft, der Dienst gerufen und sein Ergebnis gegen ``eingabe`` (und die
Deckel des Moduls) geprüft. Ergebnis wie bei der Datenquelle: Block, Text für die KI,
``ToolOutcome``.

Ein Fehlertext nennt nie Inhalte des Modells oder Ausnahmetexte — nur die Art.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, Final

from jsonschema import Draft202012Validator

from boerdi.api.schemas_debug import ToolOutcome
from boerdi.domain.ui_bloecke import neuer_block
from boerdi.ui_module import katalog
from boerdi.ui_module import strukturentwurf as se
from boerdi.ui_module import strukturentwurf_merken as entwurf_merken
from boerdi.ui_module import strukturentwurf_text as st
from boerdi.ui_module.datenquelle import Ergebnis
from boerdi.ui_module.katalog import Manifest

if TYPE_CHECKING:
    from boerdi.ui_module.aufruf import Umgebung

#: Puffer vor dem Fristende des Laufs. Gelingt der Entwurf, endet die Runde mit ihm (Ende
#: „frage“, der Begleitsatz steht in derselben Runde); die Reserve braucht nur der Fehlerweg —
#: dann muss die nächste Runde noch ohne Entwurf antworten können (Review U2, Befund 7).
RESERVE_S: Final = 15.0

_FEHLER_ARGUMENTE: Final = ("Fehler: Der Aufruf von {name} passt nicht zur Beschreibung des "
                            "Werkzeugs. Berichtige die Argumente und rufe es noch einmal, oder "
                            "antworte in Prosa. Abweichungen: {fehler}")
_FEHLER: Final = {
    "vorlage": ("Fehler: Mit dieser Nachricht wurde kein Entwurf mitgeschickt. Rufe {name} ohne "
                "vorlage auf (ein neuer Entwurf) oder antworte in Prosa."),
    "ausgelastet": ("Fehler: Der Entwurf ließ sich gerade nicht erzeugen, das System ist "
                    "ausgelastet. Rufe {name} nicht noch einmal auf; sag der Person, dass sie es "
                    "gleich noch einmal versuchen kann."),
    "erneut": ("Fehler: erneut_zeigen gilt nur mit vorlage: true (dem Entwurf aus [ENTWURF DER "
               "PERSON] oder [DEIN LETZTER ENTWURF]). Rufe {name} mit vorlage auf."),
    "ohne_texte": ("Fehler: Der letzte Entwurf war zu groß und ist nur ohne Beschreibungen und "
                   "Schlagworte gemerkt; unverändert zeigen ginge nicht ohne sie. Rufe {name} "
                   "nicht mit erneut_zeigen auf; sag der Person, dass sie ihn aus dem früheren "
                   "Entwurf herunterladen kann, oder biete einen neuen oder vertieften an."),
    "vertiefen": ("Fehler: vertiefen gilt nur mit vorlage: true (dem Entwurf, den die Person "
                  "mitgeschickt hat). Rufe {name} mit vorlage auf oder ohne vertiefen."),
    "nichts_zu_vertiefen": ("Fehler: Im mitgeschickten Entwurf gibt es nichts zu vertiefen: kein "
                            "Punkt trägt einen der genannten Titel, oder alle haben schon genug "
                            "Unterpunkte. Nenne in vertiefen Titel genau wie im Entwurf "
                            "([ENTWURF DER PERSON]) oder antworte in Prosa."),
    "frist": ("Fehler: Für den Entwurf reichte die Zeit nicht. Rufe {name} nicht noch einmal auf; "
              "biete an, es mit weniger Punkten (anzahl_oben) oder tiefe 1 zu versuchen."),
}
_FEHLER_SONST: Final = ("Fehler: Der Entwurf ließ sich nicht erzeugen. Rufe {name} nicht noch "
                        "einmal auf; antworte ohne Entwurf.")


def name(manifest: Manifest) -> str | None:
    quelle = manifest.get("dienst")
    return quelle.get("name") if isinstance(quelle, dict) else None


def _fehlschlag(modul: str, text: str, art: str, latenz_ms: int = 0) -> Ergebnis:
    return Ergebnis(None, text, ToolOutcome(tool=modul, status="timeout" if art == "frist"
                                            else "error", error=art, latency_ms=latenz_ms))


def _frist(umgebung: Umgebung) -> float:
    """Fristende des Dienstes: vor dem Ende des Laufs (Reserve), höchstens die Gesamtfrist."""
    from boerdi.services.strukturentwurf_dienst import GESAMT_FRIST_S

    spaetestens = asyncio.get_running_loop().time() + GESAMT_FRIST_S
    if umgebung.frist_ende is None:
        return spaetestens
    return min(umgebung.frist_ende - RESERVE_S, spaetestens)


async def _strukturentwurf(manifest: Manifest, args: dict[str, Any], umgebung: Umgebung
                           ) -> Ergebnis:
    from boerdi.services import strukturentwurf_dienst as dienst

    modul = manifest["name"]
    if args.get("vorlage") is True and not isinstance(umgebung.vorlage, dict):
        return _fehlschlag(modul, _FEHLER["vorlage"].format(name=modul), "vorlage")
    if args.get("erneut_zeigen") is True:
        # Drittes Review U2, Befund 2: den gemerkten Stand unverändert wieder bearbeitbar zeigen.
        if args.get("vorlage") is not True:
            return _fehlschlag(modul, _FEHLER["erneut"].format(name=modul), "argumente")
        if entwurf_merken.ohne_texte(umgebung.vorlage):
            return _fehlschlag(modul, _FEHLER["ohne_texte"].format(name=modul), "ohne_texte")
        return _block(manifest, dict(umgebung.vorlage or {}), 0)
    if args.get("vertiefen") and args.get("vorlage") is not True:
        return _fehlschlag(modul, _FEHLER["vertiefen"].format(name=modul), "argumente")
    auftrag = dienst.Auftrag(
        thema=" ".join(args["thema"].split()), fach=args.get("fach"),
        bildungsstufe=args.get("bildungsstufe"), anzahl_oben=args.get("anzahl_oben", 10),
        tiefe=args.get("tiefe", 2), hinweise=str(args.get("hinweise") or ""),
        vertiefen=tuple(args.get("vertiefen") or ()))
    t0 = time.monotonic()
    erzeugt = await dienst.erzeugen(
        auftrag, llm=dienst.llm_json(umgebung.usage_acc), frist_ende=_frist(umgebung),
        vorlage=umgebung.vorlage if args.get("vorlage") is True else None)
    latenz_ms = int((time.monotonic() - t0) * 1000)
    daten = erzeugt.daten
    if daten is None:
        grund = erzeugt.grund or "fehler"
        return _fehlschlag(modul, _FEHLER.get(grund, _FEHLER_SONST).format(name=modul), grund,
                           latenz_ms)
    return _block(manifest, daten, latenz_ms)


def _block(manifest: Manifest, daten: dict[str, Any], latenz_ms: int) -> Ergebnis:
    """Daten prüfen (Eingabe und Deckel) und als offenen Block mit Quittung liefern."""
    modul = manifest["name"]
    if not daten.get("knoten") or katalog.daten_fehler(manifest, daten) or se.fehler(daten):
        return _fehlschlag(modul, _FEHLER_SONST.format(name=modul), "abweichung", latenz_ms)
    block = neuer_block(modul, manifest["version"], manifest["art"], daten, st.textfassung(daten))
    return Ergebnis(block, st.quittung(daten), ToolOutcome(
        tool=modul, status="success", item_count=se.anzahl(daten["knoten"]),
        latency_ms=latenz_ms))


_Dienst = Callable[[Manifest, dict[str, Any], "Umgebung"], Awaitable[Ergebnis]]
_DIENSTE: Final[dict[str, _Dienst]] = {"strukturentwurf": _strukturentwurf}


def parameter(manifest: Manifest) -> dict[str, Any] | None:
    """Die Parameter für die KI — ``None``, wenn das Backend den Dienst nicht kennt (dann kein
    Angebot)."""
    if name(manifest) not in _DIENSTE:
        return None
    return dict(manifest["dienst"]["parameter"])


async def aufruf(manifest: Manifest, args: Any, umgebung: Umgebung) -> Ergebnis:
    """Einen Auftrag prüfen und den Dienst rufen → ``Ergebnis`` (Block oder Fehlertext)."""
    modul = manifest["name"]
    dienst_name = name(manifest)
    if dienst_name not in _DIENSTE:
        return _fehlschlag(modul, f"Fehler: {modul} ist kein UI-Modul mit Dienst.", "modul")
    pruefer = Draft202012Validator(manifest["dienst"]["parameter"])
    if not isinstance(args, dict) or (fehler := [f.message for f in pruefer.iter_errors(args)]):
        abweichung = "; ".join(fehler) if isinstance(args, dict) else "kein Objekt"
        return _fehlschlag(modul, _FEHLER_ARGUMENTE.format(name=modul, fehler=abweichung),
                           "argumente")
    return await _DIENSTE[dienst_name](manifest, args, umgebung)
