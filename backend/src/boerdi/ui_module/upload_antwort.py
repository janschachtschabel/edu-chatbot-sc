"""Antwortform von ``ui_upload`` (Paket U3-1b, Plan 2026-11-04 §16.5).

Die Antwort ist der im Browser erfasste **Ordnerbaum** mit Zahlen — keine Dateinamen (das Schema
lässt keine zu), nur der Name eines markierten Strukturdokuments. An die KI geht er gerahmt als
eingerückte Übersicht (Name und Zahl der Dateien), gedeckelt auf :data:`UEBERSICHT_ZEICHEN`; die
Sicherheitsprüfung liest genau diese Übersicht vor der Nachricht (wie beim Entwurf).

Seit U3-2b auch ``aktion: "dokument"``: das System hat ein Dokument gelesen (``/api/ui/dokumente``)
und die Person will damit etwas tun (``ziel``). Der Rahmen ``[DOKUMENT DER PERSON …]`` trägt nur
Befund und die ersten Überschriften — den Text liest der Dienst selbst (``aus_dokument``). Die
Ziele sind eine Liste (:data:`_ZIEL`), damit weitere dazukommen können (Plan O-26).

Seit U3-3b auch ``aktion: "uebertragen"``: die Person hat die Dateien per Klick im Modul in ihren
persönlichen Bereich in WLO übertragen (``/api/ui/ablage/*``). Der Rahmen
``[ABLAGE DER PERSON …]`` trägt nur den Ordnernamen und Zahlen — keine Kennungen, keine
Dateinamen (das Schema lässt keine zu).
"""

from __future__ import annotations

from typing import Any, Final

from boerdi.ui_module.rahmen import zeile

ORDNER_FRAME_START: Final = (
    "[ORDNER DER PERSON — sie hat im Auswahlfeld einen Ordner erfasst; nur Ordnernamen und Zahlen, "
    "Dateien wurden nicht hochgeladen. Ihre Nachricht darunter bezieht sich darauf.]")
OFFEN_FRAME_START: Final = (
    "[DEINE LETZTE FRAGE — du hast ein Auswahlfeld für einen Ordner gezeigt; die Person hat dort "
    "nichts geschickt. Ihre Nachricht darunter kann sich darauf beziehen.]")
ORDNER_FRAME_END: Final = "[ENDE ORDNER]"
DOKUMENT_FRAME_START: Final = (
    "[DOKUMENT DER PERSON — sie hat im Auswahlfeld ein Dokument lesen lassen; den Text hat das "
    "System, du siehst nur Befund und Überschriften. Ihre Nachricht darunter bezieht sich darauf.]")
DOKUMENT_FRAME_END: Final = "[ENDE DOKUMENT]"
ABLAGE_FRAME_START: Final = (
    "[ABLAGE DER PERSON — sie hat Dateien aus dem Auswahlfeld per Klick in ihren persönlichen "
    "Bereich in WLO übertragen; du siehst nur Zahlen. Ihre Nachricht darunter bezieht sich "
    "darauf.]")
ABLAGE_FRAME_END: Final = "[ENDE ABLAGE]"
#: Was die Person mit dem gelesenen Dokument will → der Satz an die KI.
_ZIEL: Final = {
    "themenbaum": ("Ziel: ein Themenbaum-Entwurf aus diesem Dokument. Rufe ui_strukturentwurf mit "
                   "aus_dokument: true auf (thema: Titel oder Zweck des Dokuments, ohne vorlage); "
                   "das System liest das Dokument selbst."),
}
_GLIEDERUNG: Final = {"ueberschriften": "Überschriften", "nummeriert": "nummerierten Zeilen",
                      "teile": "Textteilen (keine Gliederung erkannt)"}
_WARNUNG: Final = {"bilder_entfernt": "Bilder wurden nicht übernommen",
                   "wenig_text": "wenig Text je Seite", "keine_gliederung": "keine Gliederung",
                   "gekuerzt": "der Text wurde gekürzt"}
#: Die eingerückte Ordner-Übersicht für die KI (und die Sicherheitsprüfung).
UEBERSICHT_ZEICHEN: Final = 3000
#: Höchstzahl der Ordner im Baum (wie ``MAX_KNOTEN`` im Modul); die Tiefe begrenzt das Schema.
MAX_ORDNER: Final = 500
_AKTION: Final = {
    "erfasst": "Die Person hat den Befund geschickt.",
    # Neutral: diesen Rahmen sieht die KI nur, wenn der Entwurf NICHT schon im Vorlauf entstand
    # (Review U3-1, Befund 14 — etwa ein Zug, der zusätzlich eine Aktion trägt).
    "ordner_als_entwurf": "Die Person wollte die Ordnerstruktur als Themenbaum-Entwurf übernehmen.",
}


def merken(block_id: str, modul: str, daten: dict[str, Any]) -> dict[str, Any]:
    return {"block_id": block_id, "modul": modul, "frage": "Ordner erfassen",
            "zweck": str(daten.get("zweck") or "")}


def _anzahl(ordner: Any) -> int:
    if not isinstance(ordner, dict):
        return 0
    return 1 + sum(_anzahl(k) for k in ordner.get("kinder") or [])


def grund(daten: dict[str, Any]) -> str | None:
    """Über das Schema hinaus: höchstens ``MAX_ORDNER`` Ordner insgesamt (die Tiefe deckelt das
    Schema mit festen Ebenen, Review U3-1 Befund 1) und ein Strukturdokument nur mit Namen."""
    if _anzahl(daten.get("struktur")) > MAX_ORDNER:
        return "zu viele Ordner"
    zahlen = daten.get("zahlen") or {}
    if (zahlen.get("strukturdokumente") or 0) != (1 if daten.get("strukturdokument") else 0):
        return "Strukturdokument und Zahl passen nicht"
    if (daten.get("aktion") == "dokument") != isinstance(daten.get("dokument"), dict):
        return "Dokument nur mit aktion dokument"
    ablage = daten.get("ablage")
    if (daten.get("aktion") == "uebertragen") != isinstance(ablage, dict):
        return "Ablage nur mit aktion uebertragen"
    if isinstance(ablage, dict) and sum(int(ablage.get(k) or 0) for k in _ABLAGE_TEILE) != int(
            ablage.get("gesamt") or 0):
        return "Zahlen der Ablage gehen nicht auf"
    return None


def _normal(ordner: dict[str, Any]) -> dict[str, Any]:
    return {**ordner, "name": zeile(ordner.get("name"), 120),
            "kinder": [_normal(k) for k in ordner.get("kinder") or []]}


def normalisiert(daten: dict[str, Any]) -> dict[str, Any]:
    neu = {**daten, "struktur": _normal(daten.get("struktur") or {})}
    if isinstance(sd := daten.get("strukturdokument"), dict):
        neu["strukturdokument"] = {**sd, "name": zeile(sd.get("name"), 120)}
    if isinstance(dok := daten.get("dokument"), dict):
        neu["dokument"] = {**dok, "name": zeile(dok.get("name"), 200),
                           "vorschau": [zeile(t, 120) for t in dok.get("vorschau") or []]}
    return neu


def uebersicht(struktur: dict[str, Any], deckel: int = UEBERSICHT_ZEICHEN) -> str:
    """Eingerückte Übersicht ``Name (Dateien)``; abgeschnitten mit Marke, wenn sie zu lang wird."""
    zeilen: list[str] = []
    laenge = 0

    def besuche(o: dict[str, Any], tiefe: int) -> bool:
        nonlocal laenge
        name = zeile(o.get("name"), 120) or "(Auswahl)"
        z = f"{'  ' * tiefe}- {name} ({int(o.get('alle_dateien') or 0)})"
        if laenge + len(z) + 1 > deckel:
            zeilen.append("…(gekürzt)")
            return False
        zeilen.append(z)
        laenge += len(z) + 1
        return all(besuche(k, tiefe + 1) for k in o.get("kinder") or [])

    besuche(struktur, 0)
    return "\n".join(zeilen)


def _dokument_zeilen(dok: dict[str, Any]) -> list[str]:
    b = dok.get("befund") or {}
    seiten = f"{int(b['seiten'])} Seiten, " if isinstance(b.get("seiten"), int) else ""
    z = [_ZIEL.get(str(dok.get("ziel")), _ZIEL["themenbaum"]),
         (f"Dokument: {zeile(dok.get('name'), 200)} ({zeile(dok.get('format'), 10)}), {seiten}"
          f"{int(b.get('woerter') or 0)} Wörter, {int(b.get('abschnitte') or 0)} Abschnitte, "
          f"gegliedert nach {_GLIEDERUNG.get(str(b.get('gliederung_art')), 'Textteilen')}.")]
    if warnungen := [_WARNUNG[w] for w in b.get("warnungen") or [] if w in _WARNUNG]:
        z.append(f"Hinweise beim Lesen: {', '.join(warnungen)}.")
    if vorschau := dok.get("vorschau"):
        z += ["Erste Überschriften:", *(f"- {zeile(t, 120)}" for t in vorschau)]
    return z


_ABLAGE_TEILE: Final = ("abgelegt", "unklar", "fehler", "abgebrochen")


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
    aktion = (geprueft.get("daten") or {}).get("aktion")
    return {"dokument": DOKUMENT_FRAME_END, "uebertragen": ABLAGE_FRAME_END}.get(
        str(aktion), ORDNER_FRAME_END)


def zeilen(geprueft: dict[str, Any]) -> tuple[str, list[str]]:
    daten = geprueft.get("daten") or {}
    if daten.get("aktion") == "dokument" and isinstance(dok := daten.get("dokument"), dict):
        return DOKUMENT_FRAME_START, _dokument_zeilen(dok)
    if daten.get("aktion") == "uebertragen" and isinstance(ablage := daten.get("ablage"), dict):
        return ABLAGE_FRAME_START, _ablage_zeilen(daten, ablage)
    z = daten.get("zahlen") or {}
    sd = daten.get("strukturdokument")
    kopf = [_AKTION.get(str(daten.get("aktion")), _AKTION["erfasst"]),
            (f"{int(z.get('ordner') or 0)} Ordner, {int(z.get('inhalte') or 0)} Inhalte, "
             f"{int(z.get('ignoriert') or 0)} ignoriert."),
            f"Strukturdokument: {zeile(sd.get('name'), 120)}" if isinstance(sd, dict)
            else "Kein Strukturdokument markiert."]
    if isinstance(sd, dict) and daten.get("aktion") == "erfasst":
        # spät: das Rahmen-Modul bleibt beim Laden frei von Config- und MCP-Importen
        from boerdi.ui_module.dienst_upload import nicht_gelesen_satz

        kopf.append(nicht_gelesen_satz())
    if warnungen := daten.get("warnungen"):
        kopf.append(f"Hinweise beim Erfassen: {', '.join(zeile(w, 30) for w in warnungen)}")
    baum = uebersicht(daten.get("struktur") or {})
    return ORDNER_FRAME_START, [*kopf, "Ordner (Dateien darunter):", baum]


def frage_zeilen(offen: dict[str, Any]) -> list[str]:
    return [f"Auswahlfeld: {offen.get('frage') or 'Ordner erfassen'}"]


def sicherheit(daten: dict[str, Any]) -> str:
    """Was die Sicherheitsprüfung liest: was ein Modell oder die Person davon sieht — vor der
    Nachricht, damit eine lange Nachricht es nicht in die ungeprüfte Mitte schiebt. Beim Entwurf
    zuerst GENAU dessen Punkte (Review U3-1, Befund 6: die Übersicht ist gedeckelt, der Entwurf
    nimmt andere Ordner), danach Übersicht und Name des Strukturdokuments."""
    from boerdi.ui_module import strukturentwurf_text as st
    from boerdi.ui_module.strukturentwurf_ordner import aus_ordnern

    teile: list[str] = []
    entwurf = (aus_ordnern(daten.get("struktur")) if daten.get("aktion") == "ordner_als_entwurf"
               else None)
    if entwurf:
        teile.append(st.kompakt(entwurf))
    if isinstance(dok := daten.get("dokument"), dict):
        teile += [zeile(dok.get("name"), 200), *(zeile(t, 120) for t in dok.get("vorschau") or [])]
    sd = daten.get("strukturdokument")
    teile += [uebersicht(daten.get("struktur") or {}),
              zeile(sd.get("name"), 120) if isinstance(sd, dict) else ""]
    return "\n".join(t for t in teile if t)
