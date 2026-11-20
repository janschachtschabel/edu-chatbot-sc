"""Was ein ``werkzeug``-Schritt rufen darf (Paket A1): eigene Dienste und lesende MCP-Werkzeuge.

Schreibende Werkzeuge (``domain/write_confirm.CURATION_TOOLS``) nur mit Freigabe am Schritt
(Paket S,
:func:`freigebbar`). Ein Dienst ist eine Funktion Argumente → Wert (oder ``None``, wenn nichts
entsteht); sein Wert wird ein Teil des Vorgangs. Dienste ohne Netz stehen in :data:`REINE_DIENSTE`,
die übrigen rufen MCP-Werkzeuge (:data:`DIENST_MCP`).

Seit Plan 2026-11-16 (zweites Review TG-2) bekommt ein Dienst neben den Argumenten einen
:class:`DienstKontext`: einen Lader für Teile des Vorgangs, die er nur lesen will, wenn es sie gibt
(kein ``$teil`` — ein fehlender Teil führte sonst zu ``bei_fehler``), die Sprache und die
Kennung des lesbaren Dokuments der Sitzung. Bisherige Dienste brauchen ihn nicht.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Final, Protocol

from boerdi.domain.write_confirm import CURATION_TOOLS, is_confirmable
from boerdi.ui_module.namen import UPLOAD
from boerdi.ui_module.rollen import ist_gliederung, ist_material


@dataclass(frozen=True)
class DienstKontext:
    """Was ein Dienst außer seinen Argumenten lesen darf (zweites Review TG-2)."""

    #: Ein Teil des Vorgangs per Name (``None`` ohne den Teil).
    teile: Callable[[str], Awaitable[Any]]
    sprache: str = "de"
    #: Die Kennung des lesbaren Dokuments der Sitzung (``None``: keins). Fehlt der Lader (die
    #: Simulation), gilt ein Dokument im Vorgang als lesbar — sie prüft den Weg, nicht die Sitzung.
    dokument_id: Callable[[], Awaitable[str | None]] | None = None
    #: Plan 2026-11-16, TG-3e: die Kennungen ALLER lesbaren Dokumente der Sitzung (bis zu fünf).
    #: Geht vor ``dokument_id``: mit mehreren ist das Dokument eines Teils nicht immer das jüngste.
    dokument_ids: Callable[[], Awaitable[list[str]]] | None = None
    #: Plan 2026-11-16, TG-6 (G-E9): bietet das Upload-Feld hier die Ablage in WLO an — die
    #: Systemfelder des Upload-Dienstes (``dienst_upload.schalter``: Studio-Schalter, MCP kann die
    #: Stapel-Ablage, persönliche Anmeldung). ``None``: nein (die Simulation setzt die Anmeldung
    #: des Testfalls ein).
    wlo_ablage: Callable[[], bool] | None = None
    #: Review TG-4–6, MINOR 8: dazu lässt sich der Metadaten-Auftrag starten (Einrichtung,
    #: Anmeldung, Schlüssel, Flow freigegeben) — erst dann ist „gründlich über WLO“ ein Weg.
    wlo_erschliessen: Callable[[], bool] | None = None
    #: Durchtest Paket K (19.11.), drittes Review: öffnete eine Anmeldung den gründlichen Weg
    #: (Ablage nach Anmeldung, MCP-Träger, Flow freigegeben)? Für den Satz, warum es „gründlich“
    #: nicht gibt (``bereit.ohne_gruendlich``). ``None``: nein.
    nach_anmeldung: Callable[[], bool] | None = None


class Dienst(Protocol):
    """Ein Dienst: Argumente und optional der Kontext → Wert (``None``: nichts entstanden).
    Nachprüfung TG-2, NIT 9: ein Protokoll statt ``Callable[...]`` — die Signatur ist geprüft."""

    def __call__(self, args: dict[str, Any], k: Any = None, /) -> Awaitable[Any]: ...


async def _strukturentwurf_aus_ordnern(args: dict[str, Any], k: Any = None) -> Any:
    """Die erfasste Ordnerstruktur als Entwurf (ohne LLM, ``strukturentwurf_ordner``).

    Plan 2026-11-16, TG-3f: liegt im Vorgang der Teil ``struktur`` (die Auswahl mit Dateien) zu
    denselben Ordnern, liest der Dienst ihn statt ``structure`` — so bekommt jeder Punkt die
    Inhalte seines Ordners (gemerkt); liegt schon ``ablage`` vor, dazu ihre node_ids (erschlossen).
    Sonst wie bisher nur die Ordner."""
    from boerdi.ui_module.strukturentwurf_ordner import aus_ordnern
    from boerdi.ui_module.upload_antwort import ohne_dateien

    quelle = args.get("struktur")
    if isinstance(quelle, dict) and isinstance(quelle.get("struktur"), dict):
        quelle = quelle["struktur"]   # der Teil ``structure`` trägt {struktur, zahlen}
    if not isinstance(k, DienstKontext) or not isinstance(quelle, dict):
        return aus_ordnern(quelle)
    auswahl = await k.teile("struktur")
    mit = auswahl.get("struktur") if isinstance(auswahl, dict) else None
    # Nur dieselbe Auswahl: ohne Dateien muss sie genau der gelesene Ordnerbaum sein
    if isinstance(mit, dict) and ohne_dateien(mit) == ohne_dateien(quelle):
        from boerdi.services.arbeitsstand_teile import gebunden

        # Review TG-3a–c, R3-2: node_ids nur aus der Ablage desselben Upload-Felds
        ablage = await k.teile("ablage")
        # Nachprüfung TG-3d–f, MINOR 2: der Entwurf nennt die Auswahl, aus der er stammt
        return aus_ordnern(mit, ablage=ablage if gebunden(auswahl, ablage) else None,
                           quelle_block=auswahl.get("block_id"))
    return aus_ordnern(quelle)


async def _abdeckung_zaehlen(args: dict[str, Any], _k: Any = None) -> Any:
    """Paket M1: wie viele WLO-Inhalte es zu den Punkten des Entwurfs ``entwurf`` gibt
    (``services/abdeckung``, ohne LLM; Zahlen für ganz WLO)."""
    from boerdi.services.abdeckung import fuer_entwurf

    entwurf = args.get("entwurf")
    return await fuer_entwurf(entwurf) if isinstance(entwurf, dict) and entwurf.get(
        "knoten") else None


async def _struktur_mit_nodeids(args: dict[str, Any], _k: Any = None) -> Any:
    """Paket AS-Dd: der Entwurf ``entwurf`` mit den Kennungen der Sammlungen, die
    ``wlo_create_collection_tree`` angelegt hat (``angelegt``) — Folgeschritte treffen so die
    richtigen Knoten (``strukturentwurf_bestand.mit_kennungen``, ohne LLM)."""
    from boerdi.ui_module.strukturentwurf_bestand import mit_kennungen

    return mit_kennungen(args.get("entwurf"), args.get("angelegt"))


async def _baum_aus_entwurf(args: dict[str, Any], _k: Any = None) -> Any:
    """Paket AS-Dd (Review, Befund 5): der Baum für ``wlo_create_collection_tree`` aus dem Entwurf
    ``entwurf`` — mit dessen Titeln, damit ``struktur_mit_nodeids`` danach jeden Punkt findet."""
    from boerdi.services.mcp.arg_resolvers import bezeichnung_bekannt
    from boerdi.ui_module.strukturentwurf_bestand import baum_aus_entwurf, faecher_im_entwurf

    # SW-2 (Review, Befund 2): ein Fach reist nur mit, wenn das Vokabular es kennt — der Server
    # lehnte mit einem unbekannten den ganzen Baum ab.
    entwurf = args.get("entwurf")
    bekannt = {f for f in faecher_im_entwurf(entwurf)
               if await bezeichnung_bekannt("discipline", f)}
    return baum_aus_entwurf(entwurf, faecher=bekannt)


async def _metadaten_lesen(args: dict[str, Any], _k: Any = None) -> Any:
    """Plan 2026-11-10, TB-F2: die Metadaten der abgelegten Nodes aus dem Teil ``ablage``
    (``services/ablauf/metadaten``, ohne LLM, unter der Anmeldung der Person, ohne Cache)."""
    from boerdi.services.ablauf.metadaten import lesen

    return await lesen(args.get("ablage"))


async def _inhalte_aus_dateien(args: dict[str, Any], k: Any = None) -> Any:
    """Plan 2026-11-16, TG-4 (G-E9): aus den Dateinamen der Auswahl (Teil ``struktur``) ein Teil
    ``metadaten`` wie nach ``metadaten_lesen`` — ohne LLM, ohne Netz, auch anonym
    (``services/ablauf/inhalte_aus_dateien``). ``ui_strukturentwurf`` mit ``aus_inhalten`` baut
    daraus den Entwurf."""
    from boerdi.services.ablauf.inhalte_aus_dateien import aus_struktur

    sprache = k.sprache if isinstance(k, DienstKontext) else "de"   # NIT 18: Titel je Sprache
    return aus_struktur(args.get("struktur"), sprache)


#: Name einer Auswahl ohne eigenen Namen (mehrere Ordner gewählt), je Sprache.
_OHNE_NAMEN: Final = {"de": "Auswahl", "en": "selection"}


async def _bereitgestellt(_args: dict[str, Any], k: DienstKontext | None = None) -> Any:
    """Zweites Review TG-2 (MINOR 4/5): was im Vorgang **nutzbar** bereitliegt, ohne LLM —
    ``{"dokument": {"name", "lesbar"} | null, "ordner": {"name", "unterordner"} | null,
    "dateien": n, "inhaltsdateien": n}``.

    Ein Dokument ist lesbar, wenn es das lesbare Dokument der Sitzung ist (ein Dokument aus einer
    anderen Sitzung oder nach Ablauf der Frist ist es nicht). ``unterordner`` zählt die Ordner
    direkt unter der Wurzel — ohne sie gibt es keinen Entwurf aus Ordnern. Die Form ist
    erweiterbar: Abläufe verzweigen mit ``wenn_wert`` auf einzelne Stellen.

    Plan 2026-11-16, TG-3a: ``dateien`` zählt die nicht ignorierten Dateien, deren Namen im Teil
    ``struktur`` bereitliegen, ``inhaltsdateien`` davon die mit der Rolle ``inhalt`` — ein Ablauf
    verzweigt so auf „lose Dateien“. Ohne ``struktur`` (nur ``structure`` von vor TG-3a) beide 0:
    ohne Namen trägt der Weg über die Dateien nicht.

    Plan 2026-11-16, TG-3e: ``strukturdokumente`` — je Strukturdokument des Vorgangs (Teil
    ``strukturdokument``, dazu die Knoten mit Rolle ``struktur`` aus ``ablage``) ``{name,
    lesbar}``, und ``lesbare_strukturdokumente`` als Zahl (für ``wenn_wert``). Ein Sitzungsdokument
    ist lesbar wie ``dokument``; ein Knoten in WLO gilt als lesbar (ob das Repositorium schon einen
    Volltext hat, weiß erst der Leser).

    Plan 2026-11-16, TG-6 (Ablauf „Themenbaum erstellen“, G-E6, G-E9): ``art`` — was davon ein
    Ablauf übernehmen kann, in dieser Reihenfolge: ``dokument`` (ein lesbares), ``ordner`` (mit
    Unterordnern), ``dateien`` (mit Namen der Rolle ``inhalt``), sonst ``None``; ``name`` nennt es
    für den Text („das Dokument „…““, je Sprache); ``wlo_ablage`` — bietet das Upload-Feld hier die
    Ablage in WLO an (Systemfelder des Upload-Dienstes, :attr:`DienstKontext.wlo_ablage`).
    Review TG-4–6, MINOR 8: ``wlo_erschliessen`` — dazu lässt sich der Metadaten-Auftrag starten
    (:attr:`DienstKontext.wlo_erschliessen`); nur dann bietet der Ablauf „gründlich“ an.
    Durchtest Paket K (19.11.): ``ohne_gruendlich`` — sonst ein Satz, warum nicht (hilft eine
    Anmeldung: sie fehlt; sonst: der Dienst ist nicht da), für den Text des Schritts ``schnell``.
    Plan 2026-11-17, U6: ``schnell`` und ``wlo_frage`` sind entfallen (den Ort wählt das
    Upload-Feld) — kein Werks-Seed liest ``wlo_erschliessen`` oder ``ohne_gruendlich`` mehr; beide
    bleiben für eigene Abläufe."""
    if k is None:
        return {"dokument": None, "ordner": None, "dateien": 0, "inhaltsdateien": 0,
                "strukturdokumente": [], "lesbare_strukturdokumente": 0, "art": None,
                "name": None, "wlo_ablage": False, "wlo_erschliessen": False,
                "ohne_gruendlich": None}
    from boerdi.services.dokumente import strukturdokument_teil as sd
    from boerdi.services.dokumente.strukturdokument import im_vorgang

    dok = await k.teile("document")
    eintraege = await im_vorgang(k.teile)
    # Die Sitzung nur fragen, wenn es etwas zu prüfen gibt (ein Dokument im Vorgang)
    brauchen = isinstance(dok, dict) or any(sd.upload_id(e) for e in eintraege)
    kennungen = await _lesbare_kennungen(k) if brauchen else None
    dokumente = _bereite_strukturdokumente(eintraege, kennungen)
    bereit = {"dokument": _bereites_dokument(dok, kennungen),
              "ordner": await _bereite_ordner(k), **await _bereite_dateien(k),
              "strukturdokumente": dokumente,
              "lesbare_strukturdokumente": sum(1 for d in dokumente if d["lesbar"])}
    ablage = bool(k.wlo_ablage is not None and k.wlo_ablage())
    erschliessen = ablage and bool(k.wlo_erschliessen is not None and k.wlo_erschliessen())
    return {**bereit, **_art_und_name(bereit, k.sprache), "wlo_ablage": ablage,
            "wlo_erschliessen": erschliessen,
            "ohne_gruendlich": None if erschliessen else _ohne_gruendlich(k)}


def _ohne_gruendlich(k: DienstKontext) -> str:
    from boerdi.i18n import bot_text  # nur für diesen Satz

    hilft = k.nach_anmeldung is not None and k.nach_anmeldung()
    return bot_text(k.sprache, "action.ablauf.gruendlichNurAngemeldet" if hilft
                    else "action.ablauf.gruendlichNichtDa")


#: TG-6: wie ``name`` das Bereitgestellte nennt (je Sprache) — der Name selbst steht in „…“.
_NAMEN_SATZ: Final = {
    "de": {"dokument": "das Dokument „{n}“", "ordner": "die Ordner „{n}“",
           "dateien": "{z} Dateien aus „{n}“"},
    "en": {"dokument": "the document “{n}”", "ordner": "the folders “{n}”",
           "dateien": "{z} files from “{n}”"},
}


def _art_und_name(bereit: dict[str, Any], sprache: str) -> dict[str, Any]:
    """TG-6: ``art`` und ``name`` dessen, was ein Ablauf übernehmen kann (Vorrang Dokument, Ordner
    mit Unterordnern, Dateien mit Namen) — ``None`` ohne Nutzbares."""
    saetze = _NAMEN_SATZ.get(sprache, _NAMEN_SATZ["de"])
    dok, ordner = bereit["dokument"], bereit["ordner"] or {}
    lesbar = [d["name"] for d in bereit["strukturdokumente"] if d["lesbar"]]
    if isinstance(dok, dict) and dok.get("lesbar"):
        lesbar.insert(0, dok["name"])
    if lesbar:
        return {"art": "dokument", "name": saetze["dokument"].format(n=lesbar[0])}
    if ordner.get("unterordner"):
        return {"art": "ordner", "name": saetze["ordner"].format(n=ordner.get("name"))}
    if bereit["inhaltsdateien"]:
        return {"art": "dateien", "name": saetze["dateien"].format(
            z=bereit["inhaltsdateien"], n=ordner.get("name") or _OHNE_NAMEN.get(
                sprache, _OHNE_NAMEN["de"]))}
    return {"art": None, "name": None}


async def _lesbare_kennungen(k: DienstKontext) -> set[str] | None:
    """Die Kennungen der lesbaren Sitzungsdokumente — ``None``: nicht prüfbar (Simulation). TG-3e:
    alle lesbaren (``dokument_ids``) und das jüngste (``dokument_id``) zusammen."""
    if k.dokument_ids is None and k.dokument_id is None:
        return None
    kennungen = set(await k.dokument_ids()) if k.dokument_ids is not None else set()
    if k.dokument_id is not None and (kennung := await k.dokument_id()):
        kennungen.add(kennung)
    return kennungen


def _bereite_strukturdokumente(eintraege: list[dict[str, str]], kennungen: set[str] | None
                               ) -> list[dict[str, Any]]:
    from boerdi.services.dokumente import strukturdokument_teil as sd

    aus = []
    for e in eintraege:
        kennung = sd.upload_id(e)
        lesbar = kennung is None or kennungen is None or kennung in kennungen
        aus.append({"name": e["name"][:120], "lesbar": lesbar})
    return aus


async def _bereite_dateien(k: DienstKontext) -> dict[str, int]:
    from boerdi.ui_module.upload_antwort import dateien

    teil = await k.teile("struktur")
    liste = dateien(teil.get("struktur")) if isinstance(teil, dict) else []
    rollen = [d.get("rolle") for d in liste]
    return {"dateien": sum(1 for r in rollen if ist_gliederung(r) or ist_material(r)),
            "inhaltsdateien": sum(1 for r in rollen if ist_material(r))}


def _bereites_dokument(dok: Any, kennungen: set[str] | None) -> dict[str, Any] | None:
    from boerdi.ui_module.rahmen import zeile

    if not isinstance(dok, dict) or not isinstance(dok.get("name"), str):
        return None
    lesbar = kennungen is None or dok.get("ref") in {f"dokument:{i}" for i in kennungen}
    return {"name": zeile(dok["name"], 120), "lesbar": lesbar}


async def _bereite_ordner(k: DienstKontext) -> dict[str, Any] | None:
    from boerdi.ui_module.rahmen import zeile

    teil = await k.teile("structure")
    struktur = teil.get("struktur") if isinstance(teil, dict) else None
    if not isinstance(struktur, dict):
        return None
    kinder = struktur.get("kinder")
    name = zeile(struktur.get("name"), 120) or _OHNE_NAMEN.get(k.sprache, _OHNE_NAMEN["de"])
    return {"name": name, "unterordner": len(kinder) if isinstance(kinder, list) else 0}


def _bereit_kurz(wert: Any) -> str:
    """Die Kurzbeschreibung von ``bereit`` (Leiste, „Gesammelte Daten“): nur Nutzbares."""
    if not isinstance(wert, dict):
        return "—"
    teile = []
    if isinstance(dok := wert.get("dokument"), dict) and dok.get("lesbar"):
        teile.append(f"Dokument „{dok.get('name')}“")
    if isinstance(ordner := wert.get("ordner"), dict) and ordner.get("unterordner"):
        teile.append(f"Ordner „{ordner.get('name')}“")
    if isinstance(n := wert.get("dateien"), int) and n > 0:
        teile.append(f"{n} {'Datei' if n == 1 else 'Dateien'}")   # TG-3a
    if isinstance(n := wert.get("lesbare_strukturdokumente"), int) and n > 1:
        # TG-3e: mehrere Strukturdokumente (eines nennt schon „Dokument …“)
        teile.append(f"{n} Strukturdokumente")
    return ", ".join(teile) or "—"


#: Kurzbeschreibung des Ergebnisses je Dienst (sonst ``titel`` oder der Typname, ``treiber``).
ZUSAMMENFASSUNG: Final[dict[str, Callable[[Any], str]]] = {"bereitgestellt": _bereit_kurz}


DIENSTE: Final[dict[str, Dienst]] = {
    "strukturentwurf_aus_ordnern": _strukturentwurf_aus_ordnern,
    "abdeckung_zaehlen": _abdeckung_zaehlen,
    "struktur_mit_nodeids": _struktur_mit_nodeids,
    "baum_aus_entwurf": _baum_aus_entwurf,
    "metadaten_lesen": _metadaten_lesen,
    "bereitgestellt": _bereitgestellt,
    "inhalte_aus_dateien": _inhalte_aus_dateien,
}

#: Die MCP-Werkzeuge, die ein Dienst ruft — sperrt die Sicherheitsprüfung eines davon (etwa bei
#: persönlichen Daten, ``regex_gate.SPERRE_PERSOENLICH``), ist der Dienst mit gesperrt (Review M1,
#: Befund 6).
DIENST_MCP: Final[dict[str, frozenset[str]]] = {
    "abdeckung_zaehlen": frozenset({"count_wlo_content_matches"}),
    "metadaten_lesen": frozenset({"get_nodes_details"}),
}

#: Dienste ohne Netz — die Simulation rechnet sie selbst (Querschnitts-Review AS-D, Befund 1: sonst
#: sagte ein von Hand geschriebenes Ergebnis einen Weg voraus, den es nicht gibt).
REINE_DIENSTE: Final = frozenset(DIENSTE) - set(DIENST_MCP)

#: Lesende MCP-Werkzeuge, die ein Schritt rufen darf (am Code geprüft, 2026-11-05).
LESENDE_MCP: Final = frozenset({
    "search_wlo_all", "get_node_details", "browse_collection_tree", "get_collection_contents",
    "get_topic_page_content",
})


def ablauf_schreibt(ablauf: Any) -> bool:
    """Ändert der Ablauf etwas im Repositorium — ein schreibendes Werkzeug, ein Auftrag oder der
    Upload (Querschnitts-Review AS-5, Befund 6)? Solche Abläufe bietet die KI nur mit voller
    Erlaubnis an und startet sie nie direkt (TB-E3)."""
    return any(s.typ == "auftrag" or (s.typ == "modul" and s.modul == UPLOAD)
               or (s.typ == "werkzeug" and schreibend(s.werkzeug or ""))
               # Review TB-E3, Befund 3: auch ein KI-Schritt, der hochladen oder schreiben darf
               or (s.typ == "agent" and s.agent is not None
                   and any(w == UPLOAD or schreibend(w) for w in s.agent.werkzeuge))
               for s in ablauf.schritte)


def ablauf_schreibt_selbst(ablauf: Any) -> bool:
    """TW-6 (Rückmeldung 12.11.): schreibt der Ablauf **von sich aus** — ein Auftrag oder ein
    schreibendes Werkzeug (auch am KI-Schritt)? Das Upload-Feld zählt hier nicht: es überträgt nur
    nach einem eigenen Klick der Person, mit Anmeldung und eingeschaltetem Studio-Schalter. Maßstab
    für den Direktstart (``vorschlag._direkt``); für die Erlaubnis der Einbettung bleibt
    :func:`ablauf_schreibt` (mit Upload)."""
    return any(s.typ == "auftrag"
               or (s.typ == "werkzeug" and schreibend(s.werkzeug or ""))
               or (s.typ == "agent" and s.agent is not None
                   and any(schreibend(w) for w in s.agent.werkzeuge))
               for s in ablauf.schritte)


#: Review TG-4–6, MAJOR 2: Teile, mit denen ein schreibender Ablauf nicht im selben Vorgang
#: beginnen darf — Knoten im Repositorium und ein Metadaten-Lauf darauf (N14).
FRISCH_BEI: Final = ("ablage", "metadatenlauf")


def frisch_noetig(teile: Any, lauf: Any) -> bool:
    """MAJOR 2: braucht ein schreibender Ablauf einen frischen Vorgang? Nur, wenn die Teile (Namen)
    eine Ablage oder einen Metadaten-Lauf enthalten oder dort ein Lauf noch nicht beendet ist
    (wartet oder läuft — ein beendeter oder fremder schließt ohnehin). Eine Stelle für den Start
    (``zug``) und den Direktstart (``vorschlag.direkt_knopf``, zweites Review F)."""
    from boerdi.services.ablauf.treiber import BEENDET

    namen = set(teile or ())
    return (any(name in namen for name in FRISCH_BEI)
            or (isinstance(lauf, dict) and lauf.get("status") not in BEENDET))


def ablauf_schreibt_ungefragt(ablauf: Any) -> bool:
    """Plan 2026-11-16, TG-6: der Maßstab für den **Direktstart** (``vorschlag._direkt``, Prüfung
    ``direkt_schreibt``) — wie :func:`ablauf_schreibt_selbst`, aber ein Auftrag zählt nicht, vor
    dem auf jedem Weg direkt eine echte Rückfrage steht (:func:`_ehrlich_gefragt`).

    Begründung wie TW-6 beim Upload-Feld: Geschrieben wird erst nach einem eigenen Klick der
    Person, mit Anmeldung — „Themenbaum erstellen“ beginnt mit Fragen und erzeugt Metadaten nur auf
    dem gründlichen Weg nach „Ja, Metadaten erzeugen“. Schreibende Werkzeuge zählen weiter (TB-E3).
    Den frischen Vorgang (N14) entscheidet weiter :func:`ablauf_schreibt_selbst` — eine alte Ablage
    ginge sonst als „frisch hochgeladen“ an den Flow."""
    return any((s.typ == "auftrag" and not _ehrlich_gefragt(ablauf, i))
               or (s.typ == "werkzeug" and schreibend(s.werkzeug or ""))
               or (s.typ == "agent" and s.agent is not None
                   and any(schreibend(w) for w in s.agent.werkzeuge))
               for i, s in enumerate(ablauf.schritte))


def _ehrlich_gefragt(ablauf: Any, i: int) -> bool:
    """Review TG-4–6, MAJOR 1: kommt man zum Auftrag ``i`` nur über eine Frage, die auch Nein
    sagen lässt — jeder Schritt davor ist eine Wahl mit mindestens einer Option, die **nicht** zum
    Auftrag führt, deren Freitext nicht zu ihm führt und von der eine Option zu ihm führt; oder eine
    Freigabe. Strenger als ``pruefung._direkt_gefragt`` (``auftrag_rueckfrage``): dort zählt jede
    Wahl, auch „Deutsch / Englisch“, wenn beide zum Auftrag führen — das ist keine Zustimmung.

    Zweites Review TG-4–6, C: Die andere Option muss wirklich wegführen — von ihr aus ist ein
    ``ende`` erreichbar, ohne über den Auftrag zu gehen (:func:`_ohne_auftrag_zum_ende`). Ein
    „Nein“, das nur zu einer zweiten Frage führt, deren Antworten wieder zum Auftrag oder zur ersten
    Frage führen, ist keine Wahl.

    Nachprüfung TG-4–6, MINOR 4: Eine Option zum Auftrag mit ``synonyme`` ist keine Zustimmung —
    ohne Freitext trifft ein Teilwort auch verneint („Nein, nicht erzeugen“ über „erzeugen“); die
    Prüfung meldet sie (``auftrag_synonym``).

    Plan 2026-11-20, P3: ein Auftrag mit ``zustimmung: upload``
    (``pruefung.upload_zustimmung_passt``) zählt als gefragt — er startet ohne Box nur nach dem
    Upload-Klick der Person in DIESEM Lauf (``upload_zustimmung``), sonst mit der Freigabe-Box."""
    from boerdi.services.ablauf.pruefung import (
        mit_wahl,
        nachfolger,
        schreibt_mit_freigabe,
        upload_zustimmung_passt,
    )

    if ablauf.schritte[i].zustimmung == "upload" and upload_zustimmung_passt(ablauf, i):
        return True
    ziel = ablauf.schritte[i].id
    vor = [v for j, v in enumerate(ablauf.schritte) if ziel in nachfolger(ablauf, j)]

    def frage(v: Any) -> bool:
        ziele = [o.ziel for o in v.optionen or []]
        return (mit_wahl(v) and ziel in ziele
                and any(z != ziel and _ohne_auftrag_zum_ende(ablauf, z, ziel) for z in ziele)
                and not any(o.ziel == ziel and o.synonyme for o in v.optionen or [])
                and (v.freitext is None or v.freitext.ziel != ziel))

    return i > 0 and bool(vor) and all(frage(v) or schreibt_mit_freigabe(v) for v in vor)


def _ohne_auftrag_zum_ende(ablauf: Any, start: str, auftrag: str) -> bool:
    """C: erreicht man von ``start`` ein ``ende``, ohne den Schritt ``auftrag`` zu betreten (alle
    Kanten, auch ``bei_fehler``)?"""
    from boerdi.services.ablauf.pruefung import nachfolger

    index = {s.id: n for n, s in enumerate(ablauf.schritte)}
    gesehen, offen = {start}, [start]
    while offen:
        sid = offen.pop()
        if (n := index.get(sid)) is None:
            continue
        if ablauf.schritte[n].typ == "ende":
            return True
        for z in nachfolger(ablauf, n):
            if z != auftrag and z not in gesehen:
                gesehen.add(z)
                offen.append(z)
    return False


def schreibend(name: str) -> bool:
    return name in CURATION_TOOLS


#: Paket S (Review S1, Befund 8): Löschen nicht aus einem Ablauf — offen als Entscheid des Nutzers.
#: SW-3 (SE-3): auch das Löschen leerer Sammlungen im Stapel.
_NICHT_IM_ABLAUF: Final = frozenset({"wlo_delete_content", "wlo_delete_collection",
                                     "wlo_delete_collections"})


def freigebbar(name: str) -> bool:
    """Paket S: ein schreibendes Werkzeug, das ein Schritt mit Freigabe rufen darf — bestätigbar
    (Vorschau, Schlüssel), kein Löschen. Seit S4 auch ein Plan (``is_plan``): er läuft nach dem Ja
    mit „Plan fortsetzen“ über mehrere Züge, der Lauf geht weiter, wenn er fertig ist."""
    return is_confirmable(name) and name not in _NICHT_IM_ABLAUF


def bekannt(name: str) -> bool:
    return name in DIENSTE or name in LESENDE_MCP


#: Module, deren Block der Treiber immer über ihren Dienst baut — nur Dienste ohne Sprachmodell
#: (Review A1, Befund 4). Der Dienst setzt Systemfelder wie Schalter und Grenzen; der Schritt gibt
#: nur dessen Parameter mit (Rückmeldung 2026-11-15, ``treiber_bloecke.modul_block``).
MODUL_DIENST_OHNE_MODELL: Final = frozenset({UPLOAD})
