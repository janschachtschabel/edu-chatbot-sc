"""Die Rahmen von ``ui_upload`` für die KI (aus ``upload_antwort`` gelöst, Review Paket U, MINOR 7).

Was die KI nach einer Antwort des Upload-Felds sieht — ``[ORDNER …]``, ``[DOKUMENT …]``,
``[ABLAGE …]`` bzw. bei ``bereitgestellt`` die Rahmen aus ``upload_bereitgestellt`` — und der
Rahmen der offenen Frage. Nur Zahlen, Befunde und Überschriften, nie Text oder Kennungen; die
Möglichkeiten danach nennt :func:`_fragen` nach den Schaltern des Zugs. Prüfen, normalisieren und
die Sicherheitsprüfung bleiben in ``upload_antwort``.
"""

from __future__ import annotations

import logging
from typing import Any, Final

from boerdi.ui_module import upload_bereitgestellt as bereit
from boerdi.ui_module.rahmen import zeile
from boerdi.ui_module.upload_antwort import dateien, dateien_satz, gelesene, uebersicht

logger = logging.getLogger(__name__)

ORDNER_FRAME_START: Final = (
    "[ORDNER DER PERSON — sie hat im Auswahlfeld einen Ordner erfasst; nur Ordnernamen und Zahlen, "
    "Dateien wurden nicht hochgeladen. Ihre Nachricht darunter bezieht sich darauf.]")
OFFEN_FRAME_START: Final = (
    "[DEINE LETZTE FRAGE — du hast ein Auswahlfeld für einen Ordner gezeigt; die Person hat dort "
    "nichts geschickt. Ihre Nachricht darunter kann sich darauf beziehen.]")
ORDNER_FRAME_END: Final = "[ENDE ORDNER]"
DOKUMENT_FRAME_START: Final = (
    "[DOKUMENT DER PERSON — sie hat im Auswahlfeld ein Dokument lesen lassen; hier siehst du nur "
    "Befund und Überschriften. Ihre Nachricht darunter bezieht sich darauf.]")
#: Plan 2026-11-16, Durchtest TG-7 (M2): den Text liest die KI selbst (``dokument_lesen``) — sonst
#: bot sie „Erklär mir … daraus“ an und riet dann, das Dokument noch einmal hochzuladen. Im
#: Muster-Weg fehlt das Werkzeug; dann sagt sie das ehrlich.
_LESEN: Final = ("Fragen zum Inhalt beantwortest du mit dokument_lesen (erst die Gliederung, dann "
                 "Abschnitte), nicht aus dem Gedächtnis; fehlt das Werkzeug, sag, dass du den "
                 "Text hier nicht lesen kannst.")
DOKUMENT_FRAME_END: Final = "[ENDE DOKUMENT]"
ABLAGE_FRAME_START: Final = (
    "[ABLAGE DER PERSON — sie hat Dateien aus dem Auswahlfeld per Klick in ihren persönlichen "
    "Bereich in WLO übertragen; du siehst nur Zahlen. Ihre Nachricht darunter bezieht sich "
    "darauf.]")
ABLAGE_FRAME_END: Final = "[ENDE ABLAGE]"
#: TG-2 (G-E5): was nach dem Bereitstellen geschieht, klärt die KI mit der Person. Review M3: die
#: Nachricht ist hier meist nur die Blase des Moduls — darum zählt der Verlauf; und ein
#: Ablauf-Vorschlag IST ein Werkzeugaufruf (``ablauf-…``), verboten ist nur der ungefragte Entwurf.
_FRAGEN: Final = (
    "Geht aus dem Verlauf und der Nachricht nicht hervor, was sie mit den Daten will: frag kurz "
    "und nenne passende Möglichkeiten (etwa {beispiele}). Ist es klar (etwa Themenbaum): ruf den "
    "passenden Ablauf auf bzw. schlag ihn vor. Entwirf nichts ungefragt.")
_DOKUMENT_BEREIT: Final = f"Bereit: das gelesene Dokument. {_LESEN}"
_ORDNER_BEREIT: Final = "Bereit: die Ordnerstruktur mit Zahlen."
_GLIEDERUNG: Final = {"ueberschriften": "Überschriften", "nummeriert": "nummerierten Zeilen",
                      "teile": "Textteilen (keine Gliederung erkannt)"}
_WARNUNG: Final = {"bilder_entfernt": "Bilder wurden nicht übernommen",
                   "wenig_text": "wenig Text je Seite", "keine_gliederung": "keine Gliederung",
                   "gekuerzt": "der Text wurde gekürzt",
                   # Plan 2026-11-19, Paket C: gescannt, vom KI-Modell gelesen — Lesefehler möglich
                   "ocr": "per Texterkennung gelesen (Lesefehler möglich)"}
_ERFASST: Final = "Die Person hat den Befund geschickt."


def _fragen(*, dokument: bool = False, strukturdokument: bool = False) -> str:
    """Review TG-2, m2: nur Möglichkeiten nennen, die hier gehen — gerechnet mit den Schaltern
    dieses Zugs (Studio, Anmeldung, MCP), wie der Satz zum nicht gelesenen Dokument."""
    # spät: ``dienst_upload`` zieht MCP und Katalog nach — das Rahmen-Modul lädt sie erst beim
    # Aufruf (die Config lädt es über ``upload_bereitgestellt`` schon beim Import; zweites Review)
    from boerdi.ui_module.dienst_upload import schalter

    an = schalter()
    # Zweites Review TG-2, NIT 11: den Themenbaum nur nennen, wenn es dafür etwas gibt
    beispiele = ["einen Themenbaum daraus"] if _themenbaum_angeboten(dokument=dokument) else []
    if dokument:
        beispiele.append("mit dem Dokument arbeiten")
    elif strukturdokument and an.get("dokument_im_chat"):
        beispiele.append("das Strukturdokument lesen lassen")
    if an.get("ablage_in_wlo"):
        beispiele.append("die Dateien nach WLO übertragen")
    if not beispiele:
        return _FRAGEN.replace(" (etwa {beispiele})", "")
    return _FRAGEN.format(beispiele=", ".join(beispiele))


def _themenbaum_angeboten(*, dokument: bool) -> bool:
    """Gibt es einen Weg zum Themenbaum für DIESE Art von Daten (Nachprüfung TG-2, NIT 8) —
    ``ui_strukturentwurf`` (Studio-Schalter; es kann aus einem Dokument und aus Hinweisen
    entwerfen) oder einen aktiven Ablauf mit Vorschlag: für ein Dokument einen, der ein Dokument
    liest und mit ``ui_strukturentwurf`` entwirft (Voraussetzung ``dokument_lesen``), für Ordner
    einen mit ``strukturentwurf_aus_ordnern``. Im Zweifel ja (ein Lesefehler)."""
    from boerdi.services.ablauf import ausloeser
    from boerdi.ui_module import schalter as modul_schalter
    from boerdi.ui_module.namen import STRUKTURENTWURF

    def aus_dokument(a: Any) -> bool:
        # Plan 2026-11-16, TG-6: „Themenbaum erstellen“ hat die Voraussetzung nicht (es startet
        # auch für ein Thema) — es liest ein Dokument über ein Upload-Feld, das eine einzelne
        # Datei als Strukturdokument markiert
        liest = "dokument_lesen" in (a.voraussetzungen or []) or any(
            s.typ == "modul" and s.modul == "ui_upload"
            and (s.daten or {}).get("einzeldatei_als_struktur") is True for s in a.schritte)
        return liest and any(
            s.typ == "agent" and s.agent and STRUKTURENTWURF in s.agent.werkzeuge
            for s in a.schritte)

    def aus_ordnern(a: Any) -> bool:
        return any(s.typ == "werkzeug" and s.werkzeug == "strukturentwurf_aus_ordnern"
                   for s in a.schritte)

    try:
        if modul_schalter.aktiv(STRUKTURENTWURF):
            return True
        passt = aus_dokument if dokument else aus_ordnern
        return any(passt(a) for a in ausloeser.vorschlaege())
    except Exception as fehler:  # noqa: BLE001 — der Rahmen entsteht immer
        logger.warning("Angebot zum Themenbaum nicht feststellbar (%s)", type(fehler).__name__)
        return True


def _dokument_zeilen(dok: dict[str, Any]) -> list[str]:
    b = dok.get("befund") or {}
    seiten = f"{int(b['seiten'])} Seiten, " if isinstance(b.get("seiten"), int) else ""
    z = [_DOKUMENT_BEREIT, _fragen(dokument=True),
         (f"Dokument: {zeile(dok.get('name'), 200)} ({zeile(dok.get('format'), 10)}), {seiten}"
          f"{int(b.get('woerter') or 0)} Wörter, {int(b.get('abschnitte') or 0)} Abschnitte, "
          f"gegliedert nach {_GLIEDERUNG.get(str(b.get('gliederung_art')), 'Textteilen')}.")]
    if warnungen := [_WARNUNG[w] for w in b.get("warnungen") or [] if w in _WARNUNG]:
        z.append(f"Hinweise beim Lesen: {', '.join(warnungen)}.")
    if vorschau := dok.get("vorschau"):
        z += ["Erste Überschriften:", *(f"- {zeile(t, 120)}" for t in vorschau)]
    return z


def _dokumente_zeilen(liste: list[dict[str, Any]]) -> list[str]:
    """TG-3e: mehrere gelesene Dokumente — je Dokument eine Zeile mit Befund, die ersten
    Überschriften gedeckelt (wie bei einem: höchstens acht insgesamt)."""
    z = [f"Bereit: {len(liste)} gelesene Strukturdokumente. {_LESEN}",
         _fragen(dokument=True)]
    for n, dok in enumerate(liste, 1):
        b = dok.get("befund") or {}
        z.append(f"Dokument {n}: {zeile(dok.get('name'), 200)} ({zeile(dok.get('format'), 10)}), "
                 f"{int(b.get('abschnitte') or 0)} Abschnitte, gegliedert nach "
                 f"{_GLIEDERUNG.get(str(b.get('gliederung_art')), 'Textteilen')}.")
    vorschau = [f"- {zeile(dok.get('name'), 60)}: {zeile(t, 120)}"
                for dok in liste for t in (dok.get("vorschau") or [])[:2]][:8]
    if vorschau:
        z += ["Erste Überschriften:", *vorschau]
    return z


def _ablage_zeilen(daten: dict[str, Any], ablage: dict[str, Any]) -> list[str]:
    name = zeile((daten.get("struktur") or {}).get("name"), 120)
    z = [f"Ziel: persönlicher Bereich der Person, Ordner „{name or 'Auswahl'}“."
         if ablage.get("layout") == "ordner"
         else "Ziel: persönlicher Bereich der Person, ohne eigenen Ordner (direkt abgelegt).",
         (f"{int(ablage.get('gesamt') or 0)} Dateien: {int(ablage.get('abgelegt') or 0)} abgelegt, "
          f"{int(ablage.get('unklar') or 0)} unklar, {int(ablage.get('fehler') or 0)} mit Fehler, "
          f"{int(ablage.get('abgebrochen') or 0)} nicht gesendet.")]
    if ablage.get("ordner_verweigert"):
        z.append("Den Ordner durfte das Konto nicht anlegen — die Dateien liegen direkt im "
                 "persönlichen Bereich.")
    z.append("Vorgangsdatei (vorgang.json) abgelegt." if ablage.get("vorgang_abgelegt")
             else "Vorgangsdatei (vorgang.json) nicht abgelegt.")
    if int(ablage.get("unklar") or 0):
        z.append("„Unklar“ heißt: keine Antwort von WLO — die Person sieht im Modul, welche.")
    return z


def ende(geprueft: dict[str, Any]) -> str:
    if bereit.ist(daten := geprueft.get("daten") or {}):
        return bereit.ende(daten, ablage_ende=ABLAGE_FRAME_END, ordner_ende=ORDNER_FRAME_END)
    aktion = daten.get("aktion")
    return {"dokument": DOKUMENT_FRAME_END, "uebertragen": ABLAGE_FRAME_END}.get(
        str(aktion), ORDNER_FRAME_END)


def zeilen(geprueft: dict[str, Any]) -> tuple[str, list[str]]:
    daten = geprueft.get("daten") or {}
    if daten.get("aktion") == "dokument" and (liste := gelesene(daten)):
        if len(liste) == 1:
            return DOKUMENT_FRAME_START, _dokument_zeilen(liste[0])
        return DOKUMENT_FRAME_START, _dokumente_zeilen(liste)
    if daten.get("aktion") == "uebertragen" and isinstance(ablage := daten.get("ablage"), dict):
        return ABLAGE_FRAME_START, _ablage_zeilen(daten, ablage)
    if bereit.ist(daten):
        return bereit.zeilen(
            daten, ablage_zeilen=lambda d, a: (ABLAGE_FRAME_START, _ablage_zeilen(d, a)),
            ordner=_ordner_zeilen, auswahl=dateien(daten.get("struktur")))
    return _ordner_zeilen(daten)


def _ordner_zeilen(daten: dict[str, Any]) -> tuple[str, list[str]]:
    z = daten.get("zahlen") or {}
    sd = daten.get("strukturdokument")
    kopf = [_ERFASST, _ORDNER_BEREIT, _fragen(strukturdokument=isinstance(sd, dict)),
            (f"{int(z.get('ordner') or 0)} Ordner, {int(z.get('inhalte') or 0)} Inhalte, "
             f"{int(z.get('ignoriert') or 0)} ignoriert."),
            _markiert_zeile(daten)]
    if isinstance(sd, dict) and daten.get("aktion") == "erfasst":
        # spät wie in ``_fragen``: ``dienst_upload`` zieht MCP und Katalog nach
        from boerdi.ui_module.dienst_upload import nicht_gelesen_satz

        kopf.append(nicht_gelesen_satz())
    if satz := dateien_satz(daten):
        # TG-3a (Datenmodell, Optimierung 5): eine Zusammenfassung, nie die Liste der Namen —
        # Werkzeuge lesen sie aus dem Teil ``struktur``
        kopf.append(f"Dateien: {satz}. Ihre Namen liegen im Vorgang (Teil struktur), nicht hier.")
    if warnungen := daten.get("warnungen"):
        kopf.append(f"Hinweise beim Erfassen: {', '.join(zeile(w, 30) for w in warnungen)}")
    baum = uebersicht(daten.get("struktur") or {})
    return ORDNER_FRAME_START, [*kopf, "Ordner (Dateien darunter):", baum]


def _markiert_zeile(daten: dict[str, Any]) -> str:
    """Die markierten Strukturdokumente — TG-3e: mehrere mit allen Namen aus ``dateiliste`` (eine
    Antwort ohne Dateien kennt nur das erste)."""
    sd = daten.get("strukturdokument")
    if not isinstance(sd, dict):
        return "Kein Strukturdokument markiert."
    namen = [zeile(d.get("name"), 120) for d in dateien(daten.get("struktur"))
             if d.get("rolle") == "struktur"]
    if len(namen) > 1:
        return f"Strukturdokumente: {', '.join(namen)}"
    return f"Strukturdokument: {zeile(sd.get('name'), 120)}"


def frage_zeilen(offen: dict[str, Any]) -> list[str]:
    return [f"Auswahlfeld: {offen.get('frage') or 'Ordner erfassen'}"]
