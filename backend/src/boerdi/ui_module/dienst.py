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
import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, Final

from jsonschema import Draft202012Validator

from boerdi.api.schemas_debug import ToolOutcome
from boerdi.domain.ui_bloecke import neuer_block
from boerdi.services.dokumente.stand import OhneVolltext
from boerdi.ui_module import katalog
from boerdi.ui_module import strukturentwurf as se
from boerdi.ui_module import strukturentwurf_merken as entwurf_merken
from boerdi.ui_module import strukturentwurf_text as st
from boerdi.ui_module.datenquelle import Ergebnis
from boerdi.ui_module.dienst_strukturabgleich import strukturabgleich
from boerdi.ui_module.dienst_upload import upload_angebot
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
    "kein_dokument": ("Fehler: Es liegt kein Dokument der Person vor (nicht hochgeladen, oder es "
                      "ist abgelaufen). Rufe {name} nicht mit aus_dokument auf; bitte die Person, "
                      "das Dokument im Auswahlfeld (ui_upload) noch einmal zu wählen."),
    # Review TG-3d–f, MINOR 3: nur Strukturdokumente aus WLO, und keins hat schon einen Volltext
    # Plan 2026-11-16, Durchtest TG-7 (m3): ein Lesefehler (Frist, Abruf) — der Text ist womöglich
    # da, nur gerade nicht zu bekommen
    "volltext_fehlt": ("Fehler: Den Volltext der Strukturdokumente der Person ({namen}) konnte "
                       "WLO gerade nicht liefern. Rufe {name} jetzt nicht noch einmal auf; sag "
                       "der Person, dass es in einigen Minuten noch einmal geht."),
    # m3: ``not_extracted`` heißt „aus der Datei kam (noch) kein Text“ — für eine Datei, deren Text
    # gerade entsteht, ebenso wie für einen Scan oder ein Bild, das nie Text hat. Das MCP
    # unterscheidet beides nicht; der Satz nennt beides ehrlich.
    "volltext_fehlt_datei": ("Fehler: Aus den Strukturdokumenten der Person ({namen}) hat WLO "
                             "(noch) keinen Text gewonnen — entweder entsteht er gerade, oder die "
                             "Datei enthält keinen lesbaren Text (etwa ein Scan oder ein Bild). "
                             "Rufe {name} jetzt nicht noch einmal auf; sag der Person beides: in "
                             "ein paar Minuten noch einmal versuchen, und geht es dann nicht, eine "
                             "Fassung mit Text hochladen (etwa ein PDF mit Textschicht oder "
                             "Word)."),
    # Nachprüfung TG-3d–f, MINOR 4: derselbe Code, der Satz nach dem Grund
    "volltext_fehlt_anmeldung": ("Fehler: Die Strukturdokumente der Person liegen in ihrem "
                                 "persönlichen Bereich in WLO ({namen}); ohne Anmeldung lassen "
                                 "sie sich nicht lesen. Rufe {name} jetzt nicht noch einmal auf; "
                                 "bitte die Person, sich bei WLO anzumelden."),
    "volltext_fehlt_zugriff": ("Fehler: Auf die Strukturdokumente der Person ({namen}) gibt es "
                               "keinen Zugriff, oder WLO findet sie nicht mehr. Rufe {name} nicht "
                               "noch einmal auf; sag der Person, dass sie die Dokumente neu "
                               "hochladen oder lesen lassen kann."),
    "keine_inhalte": ("Fehler: Im Vorgang liegen keine Metadaten der Materialien (Teil "
                      "metadaten). Rufe {name} nicht mit aus_inhalten auf; sag der Person, dass "
                      "die Materialien erst hochgeladen und gelesen sein müssen."),
    "abgewiesen": ("Fehler: Die Angaben zu den Materialien der Person hat die Prüfung "
                   "abgewiesen. Rufe {name} nicht noch einmal auf; sag der Person, dass aus diesen "
                   "Materialien kein Entwurf entstehen kann."),
    "pruefung_fehlt": ("Fehler: Die Angaben zu den Materialien ließen sich gerade nicht prüfen. "
                       "Rufe {name} nicht noch einmal auf; sag der Person, dass sie es gleich noch "
                       "einmal versuchen kann."),
    "inhalte_ausschluss": ("Fehler: aus_inhalten schließt vorlage und aus_dokument aus. Rufe "
                           "{name} für einen neuen Entwurf aus den Materialien nur mit "
                           "aus_inhalten auf."),
    "dokument_vorlage": ("Fehler: aus_dokument und vorlage schließen sich aus. Rufe {name} für "
                         "einen neuen Entwurf aus dem Dokument ohne vorlage auf."),
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


def _moderation():
    """Querschnitts-Review 2026-11-06: der Auszug des Dokuments für Ebene 2 geht erst nach der
    Moderation ans Modell (``services/strukturentwurf_auszug``)."""
    import functools

    from boerdi.services.safety.moderation import moderate

    # Review Q4, Befund 1: unter eigener Stufe gezählt, nicht im Alarm der Chat-Züge.
    return functools.partial(moderate, stufe="strukturentwurf_auszug")


async def _ebene_eins_pruefen(text: str) -> str | None:
    """Review TB-T1, Befund 1: Übersicht und Anfang der Materialien vor Ebene 1 durch die
    Moderation — ``abgewiesen``, ``pruefung_fehlt`` (ohne Urteil bei Ausfallmodus ``closed``,
    wie ``dokumente/aufnahme``) oder ``None``."""
    from boerdi.settings import get_settings

    urteil = await _moderation()(text)
    if urteil.get("flagged"):
        return "abgewiesen"
    if not urteil and get_settings().moderation_failure_mode == "closed":
        return "pruefung_fehlt"
    return None


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
        # auch Tage später und aus einer neuen Sitzung derselben Person.
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
    dokument = None
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
            return _fehlschlag(modul, _FEHLER[_volltext_satz(dokument.fehlend)].format(
                name=modul, namen=_namen(dokument.fehlend)), "volltext_fehlt")
        if dokument is None:
            return _fehlschlag(modul, _FEHLER["kein_dokument"].format(name=modul),
                               "kein_dokument")
        if getattr(dokument, "ungeprueft", False):
            # Plan 2026-11-16, TG-3d: ein Volltext aus WLO sah beim Lesen keine Moderation (anders
            # als ein im Chat hochgeladenes Dokument) — Übersicht und Anfang vor Ebene 1 prüfen
            from boerdi.services.strukturentwurf_dokument import uebersicht_und_anfang

            if (abgewiesen := await _ebene_eins_pruefen("\n".join(
                    uebersicht_und_anfang(dokument)))):
                return _fehlschlag(modul, _FEHLER[abgewiesen].format(name=modul), abgewiesen)
    auftrag = dienst.Auftrag(
        thema=" ".join(args["thema"].split()), fach=args.get("fach"),
        bildungsstufe=args.get("bildungsstufe"), anzahl_oben=args.get("anzahl_oben", 10),
        tiefe=args.get("tiefe", 2), hinweise=str(args.get("hinweise") or ""),
        vertiefen=tuple(args.get("vertiefen") or ()), vorgaben=umgebung.vorgaben)
    t0 = time.monotonic()
    erzeugt = await dienst.erzeugen(
        auftrag, llm=dienst.llm_json(umgebung.usage_acc), frist_ende=_frist(umgebung),
        vorlage=umgebung.vorlage if args.get("vorlage") is True else None, dokument=dokument,
        moderieren=_moderation() if dokument is not None else None)
    latenz_ms = int((time.monotonic() - t0) * 1000)
    daten = erzeugt.daten
    if daten is not None and args.get("aus_inhalten") is True:
        # Plan 2026-11-16, Durchtest TG-7 (NIT): die Materialien der Person sind kein Dokument mit
        # Gliederung — die Struktur ordnet die KI (das Format kennt ki, wlo, ordner, dokument)
        daten = {**daten, "quelle": "ki"}
    if daten is None:
        grund = erzeugt.grund or "fehler"
        return _fehlschlag(modul, _FEHLER.get(grund, _FEHLER_SONST).format(name=modul), grund,
                           latenz_ms)
    ergebnis = _block(manifest, daten, latenz_ms)
    if fehlend := getattr(dokument, "fehlend", ()):
        # MINOR 3: gemischt — die KI erfährt, welches Dokument noch keinen Volltext hat
        ergebnis = ergebnis._replace(text=f"{ergebnis.text}\n{_ohne_volltext(fehlend)}")
    return ergebnis


def _namen(fehlend: tuple[tuple[str, str], ...]) -> str:
    """Die Namen fehlender Dokumente für die KI — eine Zeile je Name, ohne Anführungs- und
    Rahmenzeichen (Text der Person, Review TG-3d–f, MINOR 3)."""
    from boerdi.ui_module.rahmen import name_fuer_ki

    return ", ".join(f"„{name_fuer_ki(n)}“" for n, _grund in fehlend[:5])


def _volltext_satz(fehlend: tuple[tuple[str, str], ...]) -> str:
    """Nachprüfung TG-3d–f, MINOR 4: welcher Satz zu ``volltext_fehlt`` passt — später (der Text
    entsteht noch), Anmeldung fehlt, oder kein Zugriff bzw. nicht gefunden."""
    from boerdi.services.dokumente.strukturdokument import NICHT_EXTRAHIERT, SPAETER

    gruende = {g for _n, g in fehlend}
    if NICHT_EXTRAHIERT in gruende:
        # Durchtest TG-7, m3: vor dem Lesefehler — „noch nicht oder nie“ ist die ehrlichere Auskunft
        return "volltext_fehlt_datei"
    if gruende & SPAETER:
        return "volltext_fehlt"
    if gruende == {"ohne_anmeldung"}:
        return "volltext_fehlt_anmeldung"
    return "volltext_fehlt_zugriff"


def _ohne_volltext(fehlend: tuple[tuple[str, str], ...]) -> str:
    from boerdi.services.dokumente.strukturdokument import ABGELAUFEN, NICHT_EXTRAHIERT, SPAETER

    def satz(n: str, g: str) -> str:
        name = _namen(((n, g),))
        if g == NICHT_EXTRAHIERT:
            # Durchtest TG-7, m3
            return (f"Dokument {name}: (noch) keinen lesbaren Text — entsteht er gerade oder ist "
                    "es ein Scan; sonst eine Fassung mit Text hochladen.")
        if g in SPAETER:
            return f"Dokument {name}: Volltext gerade nicht lesbar, später erneut."
        if g == ABGELAUFEN:
            # Nachprüfung, NIT 6: ein Sitzungsdokument, das nicht mehr lesbar ist
            return f"Dokument {name}: nicht mehr lesbar (abgelaufen), bitte neu lesen lassen."
        if g == "ohne_anmeldung":
            return f"Dokument {name}: nur mit Anmeldung bei WLO lesbar."
        return f"Dokument {name}: kein Volltext lesbar."

    return " ".join(satz(n, g) for n, g in fehlend[:5])


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
    pruefer = Draft202012Validator(manifest["dienst"]["parameter"])
    if not isinstance(args, dict) or (fehler := [f.message for f in pruefer.iter_errors(args)]):
        abweichung = "; ".join(fehler) if isinstance(args, dict) else "kein Objekt"
        return _fehlschlag(modul, _FEHLER_ARGUMENTE.format(name=modul, fehler=abweichung),
                           "argumente")
    return await _DIENSTE[dienst_name](manifest, args, umgebung)
