"""Antwortform von ``ui_upload`` (Paket U3-1b, Plan 2026-11-04 §16.5).

Die Antwort ist der im Browser erfasste **Ordnerbaum** mit Zahlen. An die KI geht er gerahmt als
eingerückte Übersicht (Name und Zahl der Dateien), gedeckelt auf :data:`UEBERSICHT_ZEICHEN`. Die
Sicherheitsprüfung liest mehr als die KI (:func:`sicherheit`: Entwurf aus den Ordnern, Übersicht,
Dokument- und Dateinamen) — seit Review TG-3a–c, R3-1 nur als **Namen**: sie gehen an die
Moderation, nicht an die Krisen- und Drohungsmuster und nicht ins Protokoll
(``antwort.sicherheits_teile``,
``Form.sicherheit_nur_namen``).

Seit Plan 2026-11-16, TG-3a (Datenmodell, G-E1) trägt jeder Ordner seine Dateien (``dateiliste``:
feste Nummer ``i``, Name, Endung, Größe, Rolle; nie Binärdaten). Sie werden der Teil ``struktur``
(``arbeitsstand_teile``). Die KI sieht davon nur eine Zusammenfassung (:func:`dateien_satz`), keine
Liste; die Moderation liest die Namen trotzdem, gedeckelt (:data:`DATEINAMEN_ZEICHEN`) — ein
späterer Schritt (Entwurf aus losen Dateien) gibt sie weiter. Ausgeschlossene Dateien (Rolle
``ignorieren``) tragen keinen Namen (R3-4); ein altes Bündel, das ihn noch schickt, verliert ihn in
:func:`rueckwaerts`. Antworten ohne ``dateiliste`` (Widget vor TG-3a) bleiben gültig.

Seit U3-2b auch ``aktion: "dokument"``: das System hat ein Dokument gelesen (``/api/ui/dokumente``).
Der Rahmen ``[DOKUMENT DER PERSON …]`` trägt nur Befund und die ersten Überschriften — den Text
liest ein Dienst selbst (etwa ``aus_dokument``). Plan 2026-11-16, TG-3e: bis zu fünf markierte
Strukturdokumente; mehrere gelesene stehen zusätzlich in ``dokumente`` (``dokument`` ist dann das
erste daraus — eine Antwort mit einem Dokument bleibt wie vorher).

Seit Plan 2026-11-16, TG-2 (G-E4, G-E5) **zielneutral**: das Feld stellt nur bereit. Die Rahmen
``[ORDNER …]`` und ``[DOKUMENT …]`` sagen, was bereitliegt, und weisen keinen Entwurf mehr an; die
KI fragt, was die Person damit machen will, und ruft bzw. schlägt passende Abläufe vor
(:func:`_fragen`; Wortlaut nach Review TG-2, M3, die Möglichkeiten nach den Schaltern des Zugs, m2).
Alte Antworten aus offenen Verläufen — ``aktion: "ordner_als_entwurf"`` und ``dokument.ziel`` —
hebt :func:`rueckwaerts` vor der Schema-Prüfung auf die neue Form (wie „Senden“ bzw. „Lesen
lassen“, ohne direkten Entwurf).

Seit U3-3b auch ``aktion: "uebertragen"``: die Person hat die Dateien per Klick im Modul in ihren
persönlichen Bereich in WLO übertragen (``/api/ui/ablage/*``). Der Rahmen
``[ABLAGE DER PERSON …]`` trägt nur den Ordnernamen und Zahlen — keine Kennungen, keine
Dateinamen (der Teil ``ablage`` des Schemas lässt keine zu).

Review Paket U (19.11.), MINOR 7: die Rahmen für die KI (``zeilen``, ``ende``, ``frage_zeilen``)
stehen in ``upload_rahmen``; hier bleiben Prüfen, Normalisieren und die Sicherheitsprüfung.
"""

from __future__ import annotations

from typing import Any, Final

from boerdi.ui_module import upload_bereitgestellt as bereit
from boerdi.ui_module.rahmen import zeile

#: Alte Antwortformen, die ein offener Verlauf noch schicken kann (G-E4, ein Release lang).
_ALTE_AKTION: Final = {"ordner_als_entwurf": "erfasst"}
_ALTES_ZIEL: Final = "themenbaum"
#: Die eingerückte Ordner-Übersicht für die KI (und die Sicherheitsprüfung).
UEBERSICHT_ZEICHEN: Final = 3000
#: Höchstzahl der Ordner im Baum (wie ``MAX_KNOTEN`` im Modul); die Tiefe begrenzt das Schema.
MAX_ORDNER: Final = 500
#: TG-3a: Höchstzahl der Dateien in allen ``dateiliste`` zusammen (wie ``GRENZEN.maxDateien`` im
#: Modul) — das Schema deckelt nur je Ordner.
MAX_DATEIEN: Final = 500
#: TG-3a: so viele Zeichen Dateinamen liest die Sicherheitsprüfung (wie die Ordner-Übersicht).
#: Mit Entwurf (6000), Übersicht (3000) und Dokument (rund 1200) bleibt der Vorsatz weit unter dem,
#: was die Moderation ganz prüft (8 Abschnitte zu 4000 Zeichen, ``safety/moderation``) — so schieben
#: 500 lange Namen die Nachricht dahinter nicht in die nur teilweise geprüfte Mitte.
DATEINAMEN_ZEICHEN: Final = 3000


def rueckwaerts(daten: dict[str, Any]) -> dict[str, Any]:
    """TG-2 (G-E4): eine alte Antwort vor der Schema-Prüfung auf die neue Form heben — der Knopf
    „Als Themenbaum-Entwurf übernehmen“ gilt wie „Senden“, ``ziel: themenbaum`` entfällt. Nur
    genau diese alten Werte: ein unbekanntes Ziel bleibt stehen, und das Schema verwirft es."""
    neu = dict(daten)
    if (alt := neu.get("aktion")) in _ALTE_AKTION:
        neu["aktion"] = _ALTE_AKTION[alt]
    if isinstance(dok := neu.get("dokument"), dict) and dok.get("ziel") == _ALTES_ZIEL:
        neu["dokument"] = {k: v for k, v in dok.items() if k != "ziel"}
    if isinstance(neu.get("struktur"), dict):
        # Review TG-3a–c, R3-4: ein Bündel vor R3-4 schickt Namen ausgeschlossener Dateien mit —
        # sie fallen hier weg (das Schema lässt sie nicht mehr zu)
        neu["struktur"] = _ohne_ignorierte_namen(neu["struktur"])
    return neu


def _ohne_ignorierte_namen(ordner: dict[str, Any]) -> dict[str, Any]:
    neu = dict(ordner)
    if isinstance(liste := ordner.get("dateiliste"), list):
        neu["dateiliste"] = [{k: v for k, v in d.items() if k != "name"}
                             if isinstance(d, dict) and d.get("rolle") == "ignorieren" else d
                             for d in liste]
    if isinstance(kinder := ordner.get("kinder"), list):
        neu["kinder"] = [_ohne_ignorierte_namen(k) if isinstance(k, dict) else k for k in kinder]
    return neu


def merken(block_id: str, modul: str, daten: dict[str, Any]) -> dict[str, Any]:
    # Review Paket U, MINOR 4: die Orte, die der Ablauf zulässt — Antwort und Endpunkte prüfen sie
    return {"block_id": block_id, "modul": modul, "frage": "Ordner erfassen",
            "zweck": str(daten.get("zweck") or ""), "orte": bereit.erlaubte_orte(daten)}


def _anzahl(ordner: Any) -> int:
    if not isinstance(ordner, dict):
        return 0
    return 1 + sum(_anzahl(k) for k in ordner.get("kinder") or [])


def dateien(ordner: Any) -> list[dict[str, Any]]:
    """TG-3a: alle Dateien des Baums (``dateiliste`` je Ordner), von oben nach unten — leer bei
    einer Antwort ohne Dateien (vor TG-3a)."""
    if not isinstance(ordner, dict):
        return []
    eigene = [d for d in ordner.get("dateiliste") or [] if isinstance(d, dict)]
    return eigene + [d for k in ordner.get("kinder") or [] for d in dateien(k)]


def mit_dateien(ordner: Any) -> bool:
    """TG-3a: trägt die Antwort Dateien je Ordner (neues Widget) — auch eine leere Liste?"""
    return isinstance(ordner, dict) and isinstance(ordner.get("dateiliste"), list)


def ohne_dateien(ordner: dict[str, Any]) -> dict[str, Any]:
    """TG-3a: der Baum ohne ``dateiliste`` — die Sicht ``structure`` (nur Ordner, wie vorher)."""
    return {**{k: v for k, v in ordner.items() if k != "dateiliste"},
            "kinder": [ohne_dateien(k) for k in ordner.get("kinder") or [] if isinstance(k, dict)]}


def grund(daten: dict[str, Any]) -> str | None:
    """Über das Schema hinaus: höchstens ``MAX_ORDNER`` Ordner insgesamt (die Tiefe deckelt das
    Schema mit festen Ebenen, Review U3-1 Befund 1) und ein Strukturdokument nur mit Namen. TG-3a:
    höchstens ``MAX_DATEIEN`` Dateien, jede Nummer ``i`` nur einmal (sie verknüpft Ordner und
    Knoten)."""
    if _anzahl(daten.get("struktur")) > MAX_ORDNER:
        return "zu viele Ordner"
    alle = dateien(daten.get("struktur"))
    if len(alle) > MAX_DATEIEN:
        return "zu viele Dateien"
    if len({d.get("i") for d in alle}) != len(alle):
        return "Nummer einer Datei doppelt"
    # Review TG-3a–c, R3-2: ``i`` ist die Stelle in der Erfassung — kleiner als die Zahl aller
    # erfassten Dateien (Systemdateien zählen mit, stehen aber nicht in der Liste)
    if any(int(d.get("i") or 0) >= int((daten.get("zahlen") or {}).get("dateien") or 0)
           for d in alle):
        return "Nummer einer Datei außerhalb der Erfassung"
    if sum(1 for d in alle if d.get("rolle") == "struktur") > int(
            (daten.get("zahlen") or {}).get("strukturdokumente") or 0):
        # „höchstens“: liegt das Strukturdokument in einem Ordner über ``MAX_ORDNER``, fehlt es
        # in den Listen, zählt aber
        return "Strukturdokument in der Liste ohne Zahl"
    zahlen = daten.get("zahlen") or {}
    # TG-3e: bis zu fünf markierte; ``strukturdokument`` ist das erste davon (oder null)
    if bool(zahlen.get("strukturdokumente")) != bool(daten.get("strukturdokument")):
        return "Strukturdokument und Zahl passen nicht"
    if (daten.get("aktion") == "dokument") != isinstance(daten.get("dokument"), dict):
        return "Dokument nur mit aktion dokument"
    if (liste := daten.get("dokumente")) is not None:
        if daten.get("aktion") != "dokument" or not isinstance(liste, list) or not liste:
            return "Dokumente nur mit aktion dokument"
        kennungen = [d.get("upload_id") for d in liste if isinstance(d, dict)]
        if len(set(kennungen)) != len(liste):
            return "Dokument doppelt"
        if (daten.get("dokument") or {}).get("upload_id") != kennungen[0]:
            return "Dokument ist nicht das erste der Dokumente"
        if len(liste) > int(zahlen.get("strukturdokumente") or 0):
            return "mehr Dokumente gelesen als markiert"
    # Plan 2026-11-17, Paket U4: ``bereitgestellt`` (Ort, Dateien, Ablage nur bei Ort wlo)
    if fehler := bereit.grund(daten, alle):
        return fehler
    ablage = daten.get("ablage")
    if not bereit.ist(daten) and (daten.get("aktion") == "uebertragen") != isinstance(ablage, dict):
        return "Ablage nur mit aktion uebertragen"
    if isinstance(ablage, dict) and sum(int(ablage.get(k) or 0) for k in _ABLAGE_TEILE) != int(
            ablage.get("gesamt") or 0):
        return "Zahlen der Ablage gehen nicht auf"
    return None


def _normal(ordner: dict[str, Any]) -> dict[str, Any]:
    neu = {**ordner, "name": zeile(ordner.get("name"), 120),
           "kinder": [_normal(k) for k in ordner.get("kinder") or []]}
    if isinstance(liste := ordner.get("dateiliste"), list):
        # TG-3a: Dateinamen wie Ordnernamen — eine Zeile, höchstens 120 Zeichen
        neu["dateiliste"] = [{**d, "name": zeile(d.get("name"), 120)} if "name" in d else d
                             for d in liste]
    return neu


def normalisiert(daten: dict[str, Any]) -> dict[str, Any]:
    neu = {**daten, "struktur": _normal(daten.get("struktur") or {})}
    if isinstance(sd := daten.get("strukturdokument"), dict):
        neu["strukturdokument"] = {**sd, "name": zeile(sd.get("name"), 120)}
    if isinstance(dok := daten.get("dokument"), dict):
        neu["dokument"] = _dokument_normal(dok)
    if isinstance(liste := daten.get("dokumente"), list):
        neu["dokumente"] = [_dokument_normal(d) for d in liste if isinstance(d, dict)]
    return neu


def _dokument_normal(dok: dict[str, Any]) -> dict[str, Any]:
    return {**dok, "name": zeile(dok.get("name"), 200),
            "vorschau": [zeile(t, 120) for t in dok.get("vorschau") or []]}


def gelesene(daten: dict[str, Any]) -> list[dict[str, Any]]:
    """TG-3e: die gelesenen Dokumente einer Antwort in Lesereihenfolge — ``dokumente`` oder das
    eine ``dokument`` (Antwort mit einem Dokument, Widget vor TG-3e)."""
    if isinstance(liste := daten.get("dokumente"), list) and liste:
        return [d for d in liste if isinstance(d, dict)]
    return [dok] if isinstance(dok := daten.get("dokument"), dict) else []


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


_ABLAGE_TEILE: Final = ("abgelegt", "unklar", "fehler", "abgebrochen")


def _zahl(n: int, eins: str, viele: str) -> str:
    return f"{n} {eins if n == 1 else viele}"


def dateien_satz(daten: dict[str, Any]) -> str | None:
    """TG-3a: die Zusammenfassung der Dateien für die KI und die Kurzbeschreibung des Teils
    ``struktur`` — etwa „12 Dateien in 3 Ordnern, davon 1 Strukturdokument“. Gezählt wird, was
    nicht ignoriert ist. ``None`` ohne Dateien je Ordner (Antwort vor TG-3a)."""
    struktur = daten.get("struktur")
    if not mit_dateien(struktur):
        return None
    nutzbar = [d for d in dateien(struktur) if d.get("rolle") in ("inhalt", "struktur")]
    ordner = int((daten.get("zahlen") or {}).get("ordner") or 0)
    satz = _zahl(len(nutzbar), "Datei", "Dateien")
    satz += f" in {_zahl(ordner, 'Ordner', 'Ordnern')}" if ordner else " ohne Ordner"
    if strukturdokumente := sum(1 for d in nutzbar if d.get("rolle") == "struktur"):
        satz += f", davon {_zahl(strukturdokumente, 'Strukturdokument', 'Strukturdokumente')}"
    return satz


def sicherheit(daten: dict[str, Any]) -> str:
    """Was die Sicherheitsprüfung liest: was ein Modell oder die Person davon sieht — vor der
    Nachricht, damit eine lange Nachricht es nicht in die ungeprüfte Mitte schiebt. Zuerst die
    Punkte des Entwurfs aus den Ordnern, die auch die KI sieht (gedeckelt wie dessen
    Kompaktfassung), wenn es Unterordner gibt — immer, gleich welche
    ``aktion``: der Ablauf „aus Ordnern“ baut ihn aus jeder Antwort ohne LLM, und die Übersicht ist
    gedeckelt, der Entwurf nimmt andere Ordner (Review U3-1, Befund 6; Review TG-2, M2). Danach Name
    und Überschriften eines gelesenen Dokuments, Übersicht und Name des Strukturdokuments. TG-3a:
    zuletzt die Dateinamen, gedeckelt auf :data:`DATEINAMEN_ZEICHEN` — Text der Person wie die
    Ordnernamen; der Deckel hält die Nachricht im ganz geprüften Teil."""
    from boerdi.ui_module import strukturentwurf_text as st
    from boerdi.ui_module.strukturentwurf_ordner import aus_ordnern

    teile: list[str] = []
    if entwurf := aus_ordnern(daten.get("struktur")):
        teile.append(st.kompakt(entwurf))
    for dok in gelesene(daten):
        # TG-3e: jedes gelesene Dokument (Name und Überschriften, die die KI sieht)
        teile += [zeile(dok.get("name"), 200), *(zeile(t, 120) for t in dok.get("vorschau") or [])]
    sd = daten.get("strukturdokument")
    teile += [uebersicht(daten.get("struktur") or {}),
              zeile(sd.get("name"), 120) if isinstance(sd, dict) else "",
              _dateinamen(daten.get("struktur"))]
    return "\n".join(t for t in teile if t)


def _dateinamen(struktur: Any, deckel: int = DATEINAMEN_ZEICHEN) -> str:
    """TG-3a: die Dateinamen eine je Zeile, bis ``deckel`` Zeichen (danach mit Marke)."""
    zeilen: list[str] = []
    laenge = 0
    for d in dateien(struktur):
        z = zeile(d.get("name"), 120)
        if not z:
            continue
        if laenge + len(z) + 1 > deckel:
            zeilen.append("…(gekürzt)")
            break
        zeilen.append(z)
        laenge += len(z) + 1
    return "\n".join(zeilen)
