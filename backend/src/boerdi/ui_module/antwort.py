"""Die offene Frage eines abfragenden UI-Moduls und die Antwort darauf (Paket U1-d1, Plan §14).

Ein abfragender Block (``ui_entscheidung``) beendet den Zug; die Sitzung merkt sich die Frage
(:func:`merke_frage`, ``entities["_offene_frage"]``). Der nächste Vordergrund-Zug schließt sie —
mit oder ohne Antwort. Kommt eine ``ui_antwort`` mit, prüft :func:`antwort_pruefen` sie gegen die
gemerkte Frage und das Antwort-Schema des Moduls. Nur die geprüfte Antwort geht weiter: als
gerahmter Block vor der Nachricht an die KI (:func:`antwort_block`), im Debug-Block der
Nutzernachricht (``_ui_antwort``) und daraus im Verlauf als Status des Blocks
(:func:`status_ableiten`). Kommt keine geprüfte Antwort, steht die geschlossene Frage selbst
gerahmt vor der Nachricht (:func:`frage_block`, Review U1-d1); die Ergänzung einer geprüften
Antwort liest die Sicherheitsprüfung mit (:func:`sicherheits_text`).

Werkzeugaufrufe werden nicht gespeichert, der nächste Zug sieht nur Text — deshalb trägt der
Block Frage und Beschriftungen selbst, nicht nur Kennungen.

Rein und ohne I/O; das Schließen in der Sitzung macht ``services/ui_antwort``.
"""

from __future__ import annotations

import logging
from typing import Any, Final

from boerdi.api.schemas_ui import UiAntwort, UiBlock
from boerdi.domain.endmarken import entschaerfe_endmarken
from boerdi.ui_module import katalog
from boerdi.ui_module import strukturentwurf_antwort as entwurf
from boerdi.ui_module.namen import STRUKTURENTWURF

logger = logging.getLogger(__name__)

#: In ``session_state["entities"]``: die Frage, auf die der nächste Zug antworten darf.
OFFENE_FRAGE: Final = "_offene_frage"
#: Im Debug-Block der Nutzernachricht: die geprüfte Antwort.
DEBUG_KEY: Final = "_ui_antwort"

ANTWORT_FRAME_START: Final = (
    "[ANTWORT AUF DEINE FRAGE — die Person hat im Auswahlfeld geantwortet; ihre Nachricht "
    "darunter ist die lesbare Fassung derselben Antwort.]"
)
ANTWORT_FRAME_END: Final = "[ENDE ANTWORT]"
#: Review U1-d1, Befund 3: die Frage, wenn die Person NICHT im Auswahlfeld antwortet (getippt,
#: älteres Widget, POST-Rückfall) — sonst kennte der Folgezug weder Frage noch Möglichkeiten.
FRAGE_FRAME_START: Final = (
    "[DEINE LETZTE FRAGE — die Person hat nicht im Auswahlfeld geantwortet; ihre Nachricht "
    "darunter kann die Antwort sein.]"
)
FRAGE_FRAME_END: Final = "[ENDE FRAGE]"

_ZEILE: Final = 300


def merke_frage(entities: dict[str, Any], block: UiBlock) -> None:
    """Die offene Frage eines abfragenden Blocks — nur, was die Prüfung der Antwort braucht.
    Beim Strukturentwurf (U2) Kennung, Titel und Umfang (``strukturentwurf_antwort.merken``)."""
    daten = block.daten
    if block.modul == STRUKTURENTWURF:
        entities[OFFENE_FRAGE] = entwurf.merken(block.block_id, block.modul, daten)
        return
    entities[OFFENE_FRAGE] = {
        "block_id": block.block_id,
        "modul": block.modul,
        "frage": str(daten.get("frage") or ""),
        "optionen": [{"id": o["id"], "label": o["label"]}
                     for o in daten.get("optionen") or [] if isinstance(o, dict)],
        "mehrfach": daten.get("mehrfach") is True,
        "freitext": daten.get("freitext") is True,
    }


def _grund(offen: Any, antwort: UiAntwort) -> str | None:
    """Warum die Antwort nicht zur offenen Frage passt — ``None``, wenn sie passt."""
    if not isinstance(offen, dict) or offen.get("block_id") != antwort.block_id:
        return "keine offene Frage mit dieser Kennung"
    manifest = katalog.katalog().get(str(offen.get("modul")))
    if manifest is None or manifest.get("art") != "abfragen":
        return "Modul unbekannt"
    if fehler := katalog.antwort_fehler(manifest, antwort.daten):
        return "; ".join(fehler)
    if offen.get("modul") == STRUKTURENTWURF:
        return entwurf.grund(antwort.daten)
    gewaehlt = antwort.daten.get("gewaehlt") or []
    if not set(gewaehlt) <= {o.get("id") for o in offen.get("optionen") or []}:
        return "Kennung, die die Frage nicht anbot"
    if len(gewaehlt) > 1 and offen.get("mehrfach") is not True:
        return "mehrere gewählt bei Einzelwahl"
    if "freitext" in antwort.daten and offen.get("freitext") is not True:
        return "Freitext, den die Frage nicht anbot"
    return None


def antwort_pruefen(offen: Any, antwort: UiAntwort) -> dict[str, Any] | None:
    """Die geprüfte Antwort ``{block_id, modul, frage, daten, labels}`` — oder ``None``."""
    if grund := _grund(offen, antwort):
        # Ohne Inhalt: Kennungen und Freitext sind Eingaben der Person.
        logger.info("UI-Antwort verworfen: %s", grund.split(":")[0])
        return None
    labels = {o["id"]: o["label"] for o in offen.get("optionen") or []}
    # U2 (Review, Befund 4): beim Entwurf jeder Text eine Zeile — gilt auch für die Vorlage.
    daten = (entwurf.normalisiert(antwort.daten) if offen["modul"] == STRUKTURENTWURF
             else dict(antwort.daten))
    return {"block_id": antwort.block_id, "modul": offen["modul"], "frage": offen["frage"],
            "daten": daten,
            "labels": [labels[k] for k in antwort.daten.get("gewaehlt") or [] if k in labels]}


def _zeile(wert: object, deckel: int = _ZEILE) -> str:
    """Eine Zeile: ein Umbruch darf im Block keinen eigenen Abschnitt beginnen."""
    return " ".join(str(wert).split())[:deckel] if wert is not None else ""


def _gerahmt(start: str, zeilen: list[str], ende: str) -> str:
    """Zeilen im Rahmen. Frage, Beschriftungen (Modell) und Ergänzung (Person) dürfen den Block
    nicht vorzeitig schließen — in keiner Schreibweise der Endmarke (``domain/endmarken``)."""
    return "\n".join([start, entschaerfe_endmarken("\n".join(zeilen)), ende])


def _freitext(daten: dict[str, Any]) -> str:
    wert = daten.get("freitext")
    return wert.strip() if isinstance(wert, str) else ""


def antwort_block(geprueft: dict[str, Any]) -> str:
    """Der gerahmte Block für die KI, vor der Nachricht der Person."""
    if geprueft.get("modul") == STRUKTURENTWURF:
        kopf, zeilen = entwurf.zeilen(geprueft)
        return _gerahmt(kopf, zeilen, entwurf.ENTWURF_FRAME_END)
    daten = geprueft.get("daten") or {}
    gewaehlt = [f"{_zeile(label)} ({_zeile(kennung, 40)})"
                for label, kennung in zip(geprueft.get("labels") or [],
                                          daten.get("gewaehlt") or [], strict=False)]
    zeilen = [f"Frage: „{_zeile(geprueft.get('frage'))}“",
              f"Gewählt: {'; '.join(gewaehlt)}"]
    if ergaenzung := _freitext(daten):
        zeilen.append(f"Ergänzung der Person: {_zeile(ergaenzung, 1000)}")
    return _gerahmt(ANTWORT_FRAME_START, zeilen, ANTWORT_FRAME_END)


def frage_block(offen: dict[str, Any]) -> str:
    """Die übergangene Frage (``merke_frage``) gerahmt für die KI, vor der Nachricht der Person —
    nur, wenn keine geprüfte Antwort kam (Review U1-d1, Befund 3)."""
    if offen.get("modul") == STRUKTURENTWURF:
        return _gerahmt(entwurf.LETZTER_FRAME_START, entwurf.frage_zeilen(offen),
                        entwurf.ENTWURF_FRAME_END)
    zeilen = [f"Frage: „{_zeile(offen.get('frage'))}“", "Möglichkeiten:"]
    zeilen += [f"{nr}. {_zeile(o.get('label'))}"
               for nr, o in enumerate(offen.get("optionen") or [], start=1) if isinstance(o, dict)]
    if offen.get("mehrfach") is True:
        zeilen.append("Mehrere Möglichkeiten waren erlaubt.")
    if offen.get("freitext") is True:
        zeilen.append("Eine eigene Ergänzung im Freitext war erlaubt.")
    return _gerahmt(FRAGE_FRAME_START, zeilen, FRAGE_FRAME_END)


def vorsatz(geprueft: dict[str, Any] | None, geschlossen: dict[str, Any] | None,
            letzter: str = "") -> str:
    """Der Block vor der Nachricht des Folgezugs: die geprüfte Antwort, sonst die geschlossene
    Frage — oder nichts. Derselbe in beiden Maschinen (Agent-Zug, Muster-Weg seit U1-d2).

    ``letzter`` (drittes Review U2, Befund 2): der Rahmen des gemerkten Entwurfs
    (``strukturentwurf_merken.rahmen``). Er ersetzt bei einem geschlossenen Entwurf das
    „Seinen Stand kennst du nicht“ und entfällt, wenn der Entwurf gerade als Antwort kam."""
    entwurf = STRUKTURENTWURF
    if geprueft:
        haupt = antwort_block(geprueft)
        if geprueft.get("modul") == entwurf:
            letzter = ""
    elif geschlossen and not (geschlossen.get("modul") == entwurf and letzter):
        haupt = frage_block(geschlossen)
    else:
        haupt = ""
    return "\n\n".join(t for t in (haupt, letzter) if t)


def sicherheits_text(message: str, geprueft: dict[str, Any] | None) -> str:
    """Was die Sicherheitsprüfung liest: die Nachricht und die Ergänzung einer geprüften Antwort.

    Review U1-d1, Befund 1: Die Ergänzung (≤ 1000 Zeichen, vom Client) steht gerahmt im Prompt
    (:func:`antwort_block`) — sie muss durch dieselbe Prüfung wie die Nachricht. Ohne Ergänzung
    bleibt es die Nachricht, Zeichen für Zeichen.
    """
    daten = (geprueft or {}).get("daten") or {}
    if (geprueft or {}).get("modul") == STRUKTURENTWURF:
        # U2: was ein Modell vom Entwurf sieht, zuerst (Gegenreview, Befund 3).
        return f"{entwurf.sicherheit(daten)}\n{message}"
    ergaenzung = _freitext(daten)
    return f"{message}\n{ergaenzung}" if ergaenzung else message


#: Werkzeug-Ergebnisse der Schleifen (Agent und Muster-Weg): nach einer Frage läuft in derselben
#: Runde kein echtes Werkzeug mehr, und je Antwort steht höchstens eine Frage (U-E4).
NACH_DER_FRAGE: Final = ("Nicht ausgeführt: In dieser Runde steht schon eine Frage an die "
                         "Person; ihre Antwort kommt im nächsten Zug.")
ZWEITE_FRAGE: Final = ("Nicht ausgeführt: Je Antwort nur eine Frage mit Auswahlfeld. Die erste "
                       "wird gezeigt.")


def frage_satz(bloecke: list[UiBlock]) -> str:
    """Der Text-Schlüssel des festen Satzes unter einer Frage ohne Begleittext: beim
    Strukturentwurf ein eigener (U2), sonst „Bitte wähle unten aus.“"""
    abfragend = next((b for b in bloecke if b.art == "abfragen"), None)
    return "agent.entwurf" if abfragend and abfragend.modul == STRUKTURENTWURF else "agent.frage"


def frage_quittung(block: UiBlock) -> str:
    """Das Werkzeug-Ergebnis an die KI: Die Frage steht, die Person ist am Zug."""
    return (f"Die Frage wird der Person als Auswahlfeld gezeigt ({block.modul}). Dein Zug endet "
            "hier; ihre Antwort kommt im nächsten Zug vor ihrer Nachricht.")


def status_ableiten(nachrichten: list[dict[str, Any]], uis: list[dict[str, Any]]) -> None:
    """Status der abfragenden Blöcke im Verlauf, an Ort und Stelle in ``uis`` (je Nachricht das
    ``ui``-Dict, gleiche Reihenfolge wie ``nachrichten``).

    Gespeichert ist jeder abfragende Block ``offen``. Antwortet eine spätere Nutzernachricht auf
    ihn (``_ui_antwort`` mit seiner Kennung), ist er ``beantwortet`` samt Antwort; folgt eine
    Nutzernachricht ohne diese Antwort, ist er ``veraltet`` — jeder Vordergrund-Zug schließt die
    Frage. Sonst bleibt er ``offen``.
    """
    antworten: list[tuple[int, str | None, dict[str, Any] | None]] = []
    for i, n in enumerate(nachrichten):
        if n.get("role") != "user":
            continue
        debug = n.get("debug") if isinstance(n.get("debug"), dict) else {}
        roh = debug.get(DEBUG_KEY) if isinstance(debug, dict) else None
        if isinstance(roh, dict) and isinstance(roh.get("daten"), dict):
            antworten.append((i, roh.get("block_id"), roh["daten"]))
        else:
            antworten.append((i, None, None))
    for i, ui in enumerate(uis):
        for block in ui.get("ui_bloecke") or []:
            if block.get("art") != "abfragen" or block.get("status") != "offen":
                continue
            spaeter = [(kennung, daten) for j, kennung, daten in antworten if j > i]
            treffer = next((daten for kennung, daten in spaeter
                            if kennung == block.get("block_id")), None)
            if treffer is not None:
                block.update(status="beantwortet", antwort=treffer)
            elif spaeter:
                block["status"] = "veraltet"
