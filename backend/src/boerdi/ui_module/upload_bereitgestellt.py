"""Antwort ``aktion: "bereitgestellt"`` von ``ui_upload`` (Plan 2026-11-17, Paket U4/U5, E11/E13).

Ein Upload-Weg statt „Senden“, „Lesen lassen“ und „Übertragen“: Die Person wählt nach der Auswahl,
**wo** verarbeitet wird (``ort``), und stellt bereit. Die Antwort trägt dazu je Datei die feste
Nummer ``i`` der Auswahl und die Rolle (``dateien``):

- ``ort: chat`` — die Dateien wurden hier gelesen (``POST /api/ui/dokumente`` je Datei); je Datei
  die ``upload_id``. Nicht lesbare Dateien (Format) fehlen in ``dateien``.
- ``ort: wlo`` — die Dateien liegen im persönlichen Bereich (``/api/ui/ablage/*``); ``ablage`` trägt
  die Zahlen wie bei ``uebertragen``; ``i`` verknüpft mit dem Teil ``ablage`` (den der Server beim
  Ablegen schrieb, nie diese Antwort).
- ``ort: namen`` — nichts hochgeladen, nur die Auswahl (Teil ``struktur``).

Alles, was die Antwort nennt, ist Angabe des Browsers: die Teile ``strukturdokument`` und
``metadaten`` prüft bzw. rechnet der Server beim Speichern neu (``arbeitsstand._speichern``,
``dokumente/metadaten_lokal``). Hier steht nur, was über das Schema hinaus gelten muss
(:func:`grund`), und der Rahmen für die KI (:func:`zeilen`): Zahlen und wie sie zugreift — keine
Namen, keine Kennungen, kein Text.
"""

from __future__ import annotations

from typing import Any, Final

from boerdi.domain.dokument_art import ENDUNG as _LESBAR
from boerdi.services.config_loader.upload import load_upload_config
from boerdi.ui_module.rollen import ist_gliederung, ist_material

AKTION: Final = "bereitgestellt"
ORTE: Final = ("chat", "wlo", "namen")
_MIB: Final = 1024 * 1024
#: NIT 9: warum eine Datei der Auswahl nicht gelesen wurde (die Antwort trägt keinen Grund; der
#: Server leitet ihn aus Endung und Größe ab — der Rest ging nicht hoch: Grenze der Sitzung, Fehler
#: beim Lesen oder von der Person angehalten; zweites Review, NIT 8).
_GRUENDE: Final = (("format", "Format"), ("gross", "zu groß"),
                   ("sonst", "nicht hochgeladen: Grenze, Fehler oder angehalten"))
FRAME_START: Final = (
    "[BEREITGESTELLT VON DER PERSON — sie hat im Auswahlfeld Dateien bereitgestellt; du siehst nur "
    "Zahlen. Ihre Nachricht darunter bezieht sich darauf.]")
FRAME_END: Final = "[ENDE BEREITGESTELLT]"
_ZUGRIFF: Final = (
    "Das Gelesene liegt im Vorgang, nicht hier: Teil struktur (Auswahl mit Dateinamen), "
    "metadaten (Titel, Beschreibung, Schlagworte je Inhalt, quelle chatbot) und strukturdokument "
    "(gelesene Strukturdokumente). Fragen zum Inhalt beantwortest du mit dokument_lesen, nicht aus "
    "dem Gedächtnis; Abläufe und Werkzeuge greifen mit $teil darauf zu.")


def ist(daten: dict[str, Any]) -> bool:
    return daten.get("aktion") == AKTION


def gelesene(daten: dict[str, Any]) -> list[dict[str, Any]]:
    """Die Dateien mit ``upload_id`` (nur ``ort: chat``), in der Reihenfolge der Antwort."""
    if not ist(daten) or daten.get("ort") != "chat":
        return []
    return [d for d in daten.get("dateien") or []
            if isinstance(d, dict) and isinstance(d.get("upload_id"), str)]


def grund(daten: dict[str, Any], auswahl: list[dict[str, Any]]) -> str | None:
    """Über das Schema hinaus: ``ort`` nur mit ``bereitgestellt`` (dort Pflicht); ``dateien`` nur
    mit ``chat``/``wlo`` (dort Pflicht); ``ablage`` nur mit ``wlo`` (dort Pflicht);
    ``upload_id`` nur mit ``chat``; jede Datei steht mit derselben Rolle in der Auswahl
    (``auswahl``: alle Dateien aus ``dateiliste``), keine doppelt. Dieselbe ``upload_id`` für
    mehrere ``i`` nur bei inhaltsgleichen Dateien (gleicher Name, gleiche Größe, gleiche Rolle —
    die Oberfläche lädt sie einmal hoch, Abstimmung 19.11.)."""
    if not ist(daten):
        return "Ort nur mit aktion bereitgestellt" if "ort" in daten or "dateien" in daten \
            else None
    ort = daten.get("ort")
    if ort is None:
        return "bereitgestellt braucht einen Ort"
    dateien = daten.get("dateien")
    if (ort in ("chat", "wlo")) != isinstance(dateien, list):
        return "Dateien nur mit Ort chat oder wlo"
    if (ort == "wlo") != isinstance(daten.get("ablage"), dict):
        return "Ablage nur mit Ort wlo"
    if not isinstance(dateien, list):
        return None
    if ort != "chat" and any("upload_id" in d for d in dateien):
        return "upload_id nur mit Ort chat"
    rollen = {d.get("i"): d.get("rolle") for d in auswahl}
    for d in dateien:
        if d.get("i") not in rollen:
            return "Datei nicht in der Auswahl"
        if rollen[d.get("i")] != d.get("rolle"):
            return "Rolle passt nicht zur Auswahl"
    if len({d.get("i") for d in dateien}) != len(dateien):
        return "Datei doppelt"
    return _dubletten_grund(dateien, auswahl)


def _dubletten_grund(dateien: list[dict[str, Any]], auswahl: list[dict[str, Any]]) -> str | None:
    je_datei = {d.get("i"): (d.get("name"), d.get("groesse"), d.get("rolle")) for d in auswahl}
    gleich: dict[str, set[Any]] = {}
    for d in dateien:
        if "upload_id" in d:
            gleich.setdefault(d["upload_id"], set()).add(je_datei.get(d.get("i")))
    if any(len(merkmale) > 1 for merkmale in gleich.values()):
        return "upload_id doppelt"
    return None


def erlaubte_orte(daten: dict[str, Any]) -> list[str]:
    """Review Paket U (19.11.), MINOR 4: die Orte, die ein Ablauf dem Feld lässt — aus den Daten
    des Blocks (``orte`` des Dienstes: gesperrt mit ``ablauf``; in der Simulation die Liste der
    Argumente). Andere Sperrgründe binden nicht (Anmeldung, Sitzung ändern sich im Lauf); ``namen``
    bleibt immer."""
    orte = daten.get("orte")
    if isinstance(orte, list):
        return [o for o in ORTE if o in orte or o == "namen"]
    if not isinstance(orte, dict):
        return list(ORTE)
    return [o for o in ORTE if not (isinstance(orte.get(o), dict)
                                    and orte[o].get("grund") == "ablauf")]


def ort_erlaubt(offen: Any, ort: str) -> bool:
    """Lässt die offene Frage diesen Ort zu? Eine Frage von vor MINOR 4 (ohne ``orte``) alle."""
    orte = offen.get("orte") if isinstance(offen, dict) else None
    return not isinstance(orte, list) or ort in orte


def ort_grund(daten: dict[str, Any], offen: Any) -> str | None:
    """MINOR 4: eine Antwort ``bereitgestellt`` an einem Ort, den der Ablauf nicht erlaubt."""
    if ist(daten) and not ort_erlaubt(offen, str(daten.get("ort"))):
        return "Ort im Ablauf nicht erlaubt"
    return None


def _grund_je_datei(d: dict[str, Any], max_mb: int) -> str:
    endung = str(d.get("endung") or str(d.get("name") or "").rsplit(".", 1)[-1]).casefold()
    if endung not in _LESBAR:
        return "format"
    groesse = d.get("groesse")
    if isinstance(groesse, int) and groesse > max_mb * _MIB:
        return "gross"
    return "sonst"


def _zahl(n: int, eins: str, viele: str) -> str:
    return f"{n} {eins if n == 1 else viele}"


def _nicht_gelesen(daten: dict[str, Any], auswahl: list[dict[str, Any]]) -> str | None:
    """NIT 9: der Satz zu den nicht gelesenen Dateien (Inhalte und Strukturdokumente), je Grund —
    ohne Namen."""
    gelesen = {d.get("i") for d in daten.get("dateien") or []}
    max_mb = load_upload_config().max_mb
    zahlen: dict[str, dict[str, int]] = {}
    for d in auswahl:
        rolle = d.get("rolle")
        if (ist_gliederung(rolle) or ist_material(rolle)) and d.get("i") not in gelesen:
            je = zahlen.setdefault(_grund_je_datei(d, max_mb), {"inhalt": 0, "struktur": 0})
            # P1: ``beides`` steht bei den Strukturdokumenten (wie in ``zahlen``)
            je["struktur" if ist_gliederung(rolle) else "inhalt"] += 1
    teile = []
    for code, text in _GRUENDE:
        if not (je := zahlen.get(code)):
            continue
        was = [_zahl(je["inhalt"], "Inhalt", "Inhalte")] if je["inhalt"] else []
        if je["struktur"]:
            was.append(_zahl(je["struktur"], "Strukturdokument", "Strukturdokumente"))
        teile.append(" und ".join(was) + f" ({text})")
    if not teile:
        return None
    return ("Nicht gelesen: " + ", ".join(teile) + ". Von nicht gelesenen Inhalten gibt es nur den "
            "Namen (im Teil metadaten mit lesbar: false), von nicht gelesenen Strukturdokumenten "
            "nur den Namen in der Auswahl (Teil struktur).")


def zeilen(daten: dict[str, Any], *, ablage_zeilen: Any, ordner: Any,
           auswahl: list[dict[str, Any]] | None = None) -> tuple[str, list[str]]:
    """Der Rahmen je Ort — ``wlo`` wie ``uebertragen``, ``namen`` wie ``erfasst`` (die Rahmen dafür
    reicht ``upload_antwort`` herein), ``chat`` mit Zahlen und dem Zugriff (:data:`_ZUGRIFF`)."""
    ort = daten.get("ort")
    if ort == "wlo":
        return ablage_zeilen(daten, daten["ablage"])
    if ort != "chat":
        return ordner(daten)
    dateien = daten.get("dateien") or []
    # P1 (Plan 2026-11-20): ``beides`` ist beides — es zählt bei Inhalten und Strukturdokumenten
    inhalte = sum(1 for d in dateien if ist_material(d.get("rolle")))
    strukturen = sum(1 for d in dateien if ist_gliederung(d.get("rolle")))
    z = [f"Ort: hier im Chat gelesen — {inhalte} Inhalte (mit kurzen Angaben), "
         f"{strukturen} Strukturdokumente.",
         _ZUGRIFF]
    if satz := _nicht_gelesen(daten, auswahl or []):
        z.append(satz)
    z.append("Geht aus dem Verlauf und der Nachricht nicht hervor, was sie damit will: frag kurz. "
             "Entwirf nichts ungefragt.")
    return FRAME_START, z


def ende(daten: dict[str, Any], *, ablage_ende: str, ordner_ende: str) -> str:
    ort = daten.get("ort")
    return {"chat": FRAME_END, "wlo": ablage_ende}.get(str(ort), ordner_ende)
