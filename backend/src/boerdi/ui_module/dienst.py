"""Module mit Dienst (Paket U2, Plan 2026-11-04 T-4): das Backend erzeugt die Block-Daten selbst.

Anders als bei der Datenquelle (``ui_module/datenquelle``, ein MCP-Werkzeug liefert die Daten)
ruft hier ein Dienst des Backends — ``strukturentwurf``
(``services/strukturentwurf_dienst``) und ``upload_angebot`` (``ui_module/dienst_upload``). Die KI
sieht nur den Auftrag (``dienst.parameter`` im Manifest); der
Aufruf wird dagegen geprüft, der Dienst gerufen und sein Ergebnis gegen ``eingabe`` (und die
Deckel des Moduls) geprüft. Ergebnis wie bei der Datenquelle: Block, Text für die KI,
``ToolOutcome``.

Ein Fehlertext nennt nie Inhalte des Modells oder Ausnahmetexte — nur die Art.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, Final

from jsonschema import Draft202012Validator

from boerdi.api.schemas_debug import ToolOutcome
from boerdi.domain import ui_bloecke
from boerdi.domain.ui_bloecke import neuer_block
from boerdi.services import strukturentwurf_vokabular
from boerdi.services import strukturentwurf_zuordnung as zuordnung
from boerdi.services.dokumente.stand import OhneVolltext
from boerdi.services.strukturentwurf_dokument import ganzer_text
from boerdi.ui_module import dienst_ganztext, katalog
from boerdi.ui_module import strukturentwurf as se
from boerdi.ui_module import strukturentwurf_merken as entwurf_merken
from boerdi.ui_module import strukturentwurf_text as st
from boerdi.ui_module.datenquelle import Ergebnis

# Review N3, MINOR 8: die Fehlertexte stehen in ``dienst_fehler`` (die alten Namen bleiben); Review
# Paket A (zweites), MINOR 6: ebenso die Sätze zu fehlenden Volltexten
from boerdi.ui_module.dienst_fehler import FEHLER as _FEHLER
from boerdi.ui_module.dienst_fehler import FEHLER_ARGUMENTE as _FEHLER_ARGUMENTE
from boerdi.ui_module.dienst_fehler import FEHLER_SONST as _FEHLER_SONST
from boerdi.ui_module.dienst_fehler import ohne_volltext as _ohne_volltext
from boerdi.ui_module.dienst_fehler import volltext_fehler as _volltext_fehler
from boerdi.ui_module.dienst_fehler import volltext_satz as _volltext_satz  # noqa: F401 — Tests
from boerdi.ui_module.dienst_strukturabgleich import strukturabgleich
from boerdi.ui_module.dienst_upload import upload_angebot
from boerdi.ui_module.katalog import Manifest

if TYPE_CHECKING:
    from boerdi.ui_module.aufruf import Umgebung

#: Puffer vor dem Fristende des Laufs. Gelingt der Entwurf, endet die Runde mit ihm (Ende
#: „frage“, der Begleitsatz steht in derselben Runde); die Reserve braucht nur der Fehlerweg —
#: dann muss die nächste Runde noch ohne Entwurf antworten können (Review U2, Befund 7).
RESERVE_S: Final = 15.0

def name(manifest: Manifest) -> str | None:
    quelle = manifest.get("dienst")
    return quelle.get("name") if isinstance(quelle, dict) else None


def _fehlschlag(modul: str, text: str, art: str, latenz_ms: int = 0) -> Ergebnis:
    return Ergebnis(None, text, ToolOutcome(tool=modul, status="timeout" if art == "frist"
                                            else "error", error=art, latency_ms=latenz_ms))


def _moderation(stufe: str = "strukturentwurf_auszug"):
    """Querschnitts-Review 2026-11-06: der Auszug des Dokuments für Ebene 2 geht erst nach der
    Moderation ans Modell (``services/strukturentwurf_auszug``). Zweites Review A, NIT 11: der
    ganze Text unter ``strukturentwurf_ganztext``."""
    import functools

    from boerdi.services.safety.moderation import moderate

    # Review Q4, Befund 1: unter eigener Stufe gezählt, nicht im Alarm der Chat-Züge.
    return functools.partial(moderate, stufe=stufe)


async def _ebene_eins_pruefen(text: str, stufe: str | None = None, *,
                              offen: str | None = None) -> str | None:
    """Review TB-T1, Befund 1: Übersicht und Anfang der Materialien vor Ebene 1 durch die
    Moderation — ``abgewiesen``, ``pruefung_fehlt`` (ohne Urteil bei Ausfallmodus ``closed``,
    wie ``dokumente/aufnahme``) oder ``None``. ``stufe``: eine eigene Stufe der Moderation.
    ``offen``: das Ergebnis ohne Urteil im Modus ``open`` (sonst ``None`` = weiter)."""
    from boerdi.settings import get_settings

    urteil = await (_moderation(stufe) if stufe else _moderation())(text)
    if urteil.get("flagged"):
        return "abgewiesen"
    # Review Paket A, NIT 12: nur teilweise geprüft (sehr langer Text) ist kein Urteil übers Ganze
    ohne_urteil = not urteil or urteil.get("teilweise")
    if ohne_urteil:
        return "pruefung_fehlt" if get_settings().moderation_failure_mode == "closed" else offen
    return None


async def _ganztext_pruefen(text: str) -> str | None:
    """Ein Stück des ganzen Texts — eigene Stufe ``strukturentwurf_ganztext`` (NIT 11). Ohne Urteil
    im Modus ``open`` :data:`~dienst_ganztext.OHNE_URTEIL` (viertes Review A, MINOR 7): der ganze
    Text geht dann nie ungeprüft ans Modell, es gilt der Weg „gliederung“."""
    return await _ebene_eins_pruefen(text, stufe="strukturentwurf_ganztext",
                                     offen=dienst_ganztext.OHNE_URTEIL)


#: Paket N3: die Einbettungs-Naht der Zuordnung (Tests setzen eine Attrappe).
_einbetten = zuordnung.einbetten_mit


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
    if args.get("aus_inhalten") is True and (args.get("vorlage") is True
                                             or args.get("aus_dokument") is True):
        # Review TB-T1, Befund 13: vor dem Lesen der Vorlage
        return _fehlschlag(modul, _FEHLER["inhalte_ausschluss"].format(name=modul), "argumente")
    if args.get("vorlage") is True and not isinstance(umgebung.vorlage, dict) and umgebung.teile:
        # Paket V1: ohne mitgeschickten oder gemerkten Entwurf den übernommenen aus dem Vorgang —
        # auch Tage später (nach „Fortsetzen“ im Gespräch des Vorgangs, Entscheid E-F).
        if isinstance(entwurf := await umgebung.teile("draft"), dict) and entwurf.get("knoten"):
            umgebung = dataclasses.replace(umgebung, vorlage=entwurf)
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
    frist_ende = _frist(umgebung)
    dokument = ganz = None
    if args.get("aus_inhalten") is True:
        # TB-T1: die Metadaten der Materialien aus dem Vorgang (Teil ``metadaten``, vom Ablauf-
        # Werkzeug ``metadaten_lesen``) — serverseitig gelesen, nie aus den Argumenten.
        from boerdi.services.ablauf import metadaten

        teil = await umgebung.teile(metadaten.TEIL) if umgebung.teile is not None else None
        dokument = metadaten.als_dokument(teil)
        if dokument is None:
            return _fehlschlag(modul, _FEHLER["keine_inhalte"].format(name=modul),
                               "keine_inhalte")
        if (abgewiesen := await _ebene_eins_pruefen(metadaten.moderationstext(dokument))):
            return _fehlschlag(modul, _FEHLER[abgewiesen].format(name=modul), abgewiesen)
    elif args.get("aus_dokument") is True:
        # U3-2b: das Dokument der Sitzung, serverseitig gelesen — nie aus den Argumenten.
        if args.get("vorlage") is True:
            return _fehlschlag(modul, _FEHLER["dokument_vorlage"].format(name=modul), "argumente")
        dokument = await umgebung.dokument() if umgebung.dokument is not None else None
        if isinstance(dokument, OhneVolltext):
            # Plan 2026-11-20 §8, E1: endgültig ohne Text hat einen eigenen Code
            return _fehlschlag(modul, *_volltext_fehler(modul, dokument.fehlend))
        if dokument is None:
            return _fehlschlag(modul, _FEHLER["kein_dokument"].format(name=modul),
                               "kein_dokument")
        abgewiesen = None
        if getattr(dokument, "ungeprueft", False):
            # Plan 2026-11-16, TG-3d: ein Volltext aus WLO sah beim Lesen keine Moderation (anders
            # als ein im Chat hochgeladenes Dokument) — Übersicht und Anfang vor Ebene 1 prüfen
            from boerdi.services.strukturentwurf_dokument import uebersicht_und_anfang

            abgewiesen = await _ebene_eins_pruefen("\n".join(uebersicht_und_anfang(dokument)))
        # Plan 2026-11-19, A4 (E2): was ganz an Ebene 1 geht, ist vorher moderiert — in Stücken
        if not abgewiesen and (ganz := ganzer_text(dokument)) is not None:
            # Zweites Review A, MINOR 4: an die Frist des Dienstes gebunden
            abgewiesen = await dienst_ganztext.in_frist(ganz, _ganztext_pruefen, frist_ende)
            if abgewiesen == dienst_ganztext.OHNE_URTEIL:
                # Drittes Review A, MAJOR 4; viertes, MINOR 7: Frist abgelaufen oder Moderation
                # ohne Urteil im Modus ``open`` — der Weg „gliederung“, nie „ganz“ ungeprüft
                ganz = abgewiesen = None
        if abgewiesen:   # Review A: eigene Sätze für ein Dokument (nicht „Materialien“)
            satz = _FEHLER[f"{abgewiesen}_dokument"]
            return _fehlschlag(modul, satz.format(name=modul), abgewiesen)
    auftrag = dienst.Auftrag(
        thema=" ".join(args["thema"].split()), fach=args.get("fach"),
        bildungsstufe=args.get("bildungsstufe"), anzahl_oben=args.get("anzahl_oben", 10),
        tiefe=args.get("tiefe", 2), hinweise=str(args.get("hinweise") or ""),
        vertiefen=tuple(args.get("vertiefen") or ()), vorgaben=umgebung.vorgaben)
    t0 = time.monotonic()
    erzeugt = await dienst.erzeugen(
        auftrag, llm=dienst.llm_json(umgebung.usage_acc), frist_ende=frist_ende,
        vorlage=umgebung.vorlage if args.get("vorlage") is True else None, dokument=dokument,
        moderieren=_moderation() if dokument is not None else None,
        ganz_moderiert=ganz is not None,
        llm_vorwaermen=dienst.llm_json(umgebung.usage_acc, dienst.PHASE_VORWAERMEN)
        if ganz is not None else None)
    latenz_ms = int((time.monotonic() - t0) * 1000)
    daten = erzeugt.daten
    if daten is not None and args.get("aus_inhalten") is True:
        # Plan 2026-11-16, Durchtest TG-7 (NIT): die Materialien der Person sind kein Dokument mit
        # Gliederung — die Struktur ordnet die KI (das Format kennt ki, wlo, ordner, dokument)
        daten = {**daten, "quelle": "ki"}
        if dienst.platzhalter_thema(daten.get("thema")) and str(daten.get("titel") or "").strip():
            # Durchtest r2-1 (live wieder am 19.11.): die KI nennt als Thema „Themen aus den
            # bereitgestellten Dateien“ — der Titel des Entwurfs trägt das Sachgebiet
            daten["thema"] = str(daten["titel"])[:200]
        # Paket N3: Materialien → Punkte (``abschnitte`` des Modells, nachgezogen per Einbettung)
        daten = (await zuordnung.zuordnen(
            daten, teil, einbetten=_einbetten(umgebung.usage_acc, frist_ende),
            node_ids=await zuordnung.node_ids_der_auswahl(teil, umgebung.teile),
            frist_ende=frist_ende)).daten
    if daten is None:
        grund = erzeugt.grund or "fehler"
        return _fehlschlag(modul, _FEHLER.get(grund, _FEHLER_SONST).format(name=modul), grund,
                           latenz_ms)
    # Anschluss N2: Fach und Stufe des Entwurfs auf das WLO-Vokabular (kein Treffer → leer, mit
    # Hinweis an die KI — das Schema hat kein Hinweisfeld; N1/N2-Review, Befund 3)
    angeglichen = await strukturentwurf_vokabular.angleichen(daten)
    ergebnis = _block(manifest, angeglichen.daten, latenz_ms)
    if angeglichen.hinweise and ergebnis.block is not None:
        ergebnis = ergebnis._replace(text=f"{ergebnis.text}\nHinweis für die Person: "
                                          + " ".join(angeglichen.hinweise))
    if fehlend := getattr(dokument, "fehlend", ()):
        # MINOR 3: gemischt — die KI erfährt, welches Dokument noch keinen Volltext hat
        ergebnis = ergebnis._replace(text=f"{ergebnis.text}\n{_ohne_volltext(fehlend)}")
    return ergebnis


def _block(manifest: Manifest, daten: dict[str, Any], latenz_ms: int) -> Ergebnis:
    """Daten prüfen (Eingabe und Deckel) und als offenen Block mit Quittung liefern."""
    modul = manifest["name"]
    if not daten.get("knoten") or katalog.daten_fehler(manifest, daten) or se.fehler(daten):
        return _fehlschlag(modul, _FEHLER_SONST.format(name=modul), "abweichung", latenz_ms)
    if "gelesen" in daten and len(json.dumps(daten, ensure_ascii=False)) > (
            ui_bloecke.DATEN_DECKEL_ZEICHEN):
        # Review A, NIT 16: die Rückkontrolle ist nur Anzeige — sie hebt den Entwurf nie über den
        # Deckel der Blockdaten (der Block ginge sonst nicht in Antwort und Verlauf)
        daten = {k: v for k, v in daten.items() if k != "gelesen"}
    block = neuer_block(modul, manifest["version"], manifest["art"], daten, st.textfassung(daten))
    return Ergebnis(block, st.quittung(daten), ToolOutcome(
        tool=modul, status="success", item_count=se.anzahl(daten["knoten"]),
        latency_ms=latenz_ms))


_Dienst = Callable[[Manifest, dict[str, Any], "Umgebung"], Awaitable[Ergebnis]]
_DIENSTE: Final[dict[str, _Dienst]] = {
    "strukturentwurf": _strukturentwurf,
    # Paket U3-1b: das Auswahlfeld von ui_upload (Grenzen und Schalter setzt das Backend).
    "upload_angebot": upload_angebot,
    # Paket U4: der Entwurf gegen eine WLO-Sammlung (ohne LLM).
    "strukturabgleich": strukturabgleich,
}


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
    if dienst_name == "strukturentwurf" and umgebung.vorbelegung:
        # Plan 2026-11-16, TG-5 (G-E8): die Antworten des Laufs füllen, was die KI nicht setzt —
        # vor der Prüfung, damit auch ein vorbelegtes ``thema`` zählt und die Werte geprüft sind
        from boerdi.services.ablauf.vorbelegung import vorbelegt

        args = vorbelegt(args, umgebung.vorbelegung)
    if (isinstance(args, dict) and args.get("vorlage") is not True
            and (feste := (umgebung.feste_argumente or {}).get(modul))):
        # Plan 2026-11-19, A2 (E4): die festen Argumente des Schritts zuletzt — sie überschreiben
        # die KI (ein Dokument-Schritt entwirft nie frei, wenn sie ``aus_dokument`` vergisst).
        # Review A, MAJOR 1: nur für neue Entwürfe — mit ``vorlage`` (vertiefen, erneut zeigen)
        # schlössen sie sich aus, und die Bearbeitungen der Person gingen verloren
        args = {**args, **feste}
    pruefer = Draft202012Validator(manifest["dienst"]["parameter"])
    if not isinstance(args, dict) or (fehler := [f.message for f in pruefer.iter_errors(args)]):
        abweichung = "; ".join(fehler) if isinstance(args, dict) else "kein Objekt"
        return _fehlschlag(modul, _FEHLER_ARGUMENTE.format(name=modul, fehler=abweichung),
                           "argumente")
    return await _DIENSTE[dienst_name](manifest, args, umgebung)
