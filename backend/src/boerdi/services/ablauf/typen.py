"""Teile und Typen eines Ablaufs (Paket AS-Db, Plan 2026-11-09 §5e, D8) — die eine Quelle dafür,
welcher Schritt und welches Modul welchen Teil schreibt (Review AS-Db, Befund 6: vorher stand das
doppelt in ``pruefung`` und hier).

Was ein Schritt schreibt, hat einen bekannten Typ — soweit ihn der Code festlegt:

- ein Dienst nach :data:`DIENST_AUSGABE` (der Treiber speichert denselben Typ);
- ein lesendes WLO-Werkzeug liefert Text (``text``), ein schreibendes sein Ergebnis
  (``<werkzeug>@1``), ein Auftrag ``wlo.auftrag@1``;
- ein Modul die Normalform seiner Teile (:data:`MODUL_TEILE`, wie
  ``services/arbeitsstand_teile``), auch beim Modul-Auslöser — dazu Teile, die ein Modul außerhalb
  seines Manifests hinterlässt (:data:`ZUSATZ_TEILE`: ``ablage`` aus der Übertragung von
  ``ui_upload``);
- ein Freitext ``text``.

Die Ausgabe eines KI-Schritts hat keinen festen Typ (``None``) — ein Teil mit einem solchen
Schreiber wird nicht verglichen.

Was ein Dienst oder Modul als ganzen Teil erwartet, steht in :data:`DIENST_EINGABE` und
:data:`MODUL_EINGABE`. Mit Pfad oder Auswahl liest ein Schritt etwas anderes als den Teil — dann
gibt es keinen Vergleich. Rein, ohne I/O.
"""

from __future__ import annotations

from typing import Any, Final

from boerdi.domain.config_models.ablauf import AblaufArea, Schritt
from boerdi.services.ablauf import platzhalter, vergleich, werkzeuge
from boerdi.services.teil_verweise import NAME, TIEFE, alle_verweise, ist_auswahl, verweis

TEXT: Final = "text"
ORDNERBAUM: Final = "wlo.ordnerbaum@1"
DOKUMENT: Final = "wlo.dokument-verweis@1"
STRUKTUR: Final = "wlo.sammlungsstruktur@1"
ABLAGE: Final = "wlo.ablage@1"
AUFTRAG: Final = "wlo.auftrag@1"
#: AS-4a: die Startdaten (Teil ``start``).
START: Final = "wlo.start@1"
#: Der Name des Teils mit den Startdaten — kein Schritt darf ihn schreiben.
START_TEIL: Final = "start"
#: Ein Abgleich-Ergebnis — das liefert kein Schritt; ``ui_strukturabgleich`` bekommt seine Daten
#: fertig (Review AS-Db, Befund 2: einen Entwurf nimmt es nicht).
STRUKTURABGLEICH: Final = "wlo.strukturabgleich@1"


def _werkzeug_typ(werkzeug: str) -> str:
    """Der Typ, unter dem ein Ergebnis gespeichert wird, das keinen eigenen hat."""
    return f"{werkzeug}@1"


#: Die Teile, die Module hinterlassen: Name → Typ (``arbeitsstand_teile._teile``,
#: ``ablage/vorgang_teil``).
MODUL_TEILE: Final[dict[str, str]] = {"structure": ORDNERBAUM, "document": DOKUMENT,
                                      "draft": STRUKTUR, "ablage": ABLAGE}
#: Teile, die ein Modul außerhalb von ``vorgang.schreibt`` hinterlässt (Review AS-Db, Befund 1).
ZUSATZ_TEILE: Final[dict[str, tuple[str, ...]]] = {"ui_upload": ("ablage",)}
#: Was ``wlo_create_collection_tree`` hinterlässt (nach der Freigabe, ``treiber.weiter_freigabe``).
ANGELEGT: Final = _werkzeug_typ("wlo_create_collection_tree")
DIENST_AUSGABE: Final[dict[str, str]] = {
    "strukturentwurf_aus_ordnern": STRUKTUR,
    "abdeckung_zaehlen": "wlo.abdeckung@1",
    "struktur_mit_nodeids": STRUKTUR,
    "baum_aus_entwurf": _werkzeug_typ("baum_aus_entwurf"),
}
#: Dienst → Argument → erwarteter Typ, wenn das Argument ein ganzer Teil ist. Zugleich die Liste
#: aller Argumente eines Dienstes (alle Pflicht) — die Prüfung meldet unbekannte und fehlende.
DIENST_EINGABE: Final[dict[str, dict[str, str]]] = {
    "strukturentwurf_aus_ordnern": {"struktur": ORDNERBAUM},
    "abdeckung_zaehlen": {"entwurf": STRUKTUR},
    "struktur_mit_nodeids": {"entwurf": STRUKTUR, "angelegt": ANGELEGT},
    "baum_aus_entwurf": {"entwurf": STRUKTUR},
}
#: Dienst-Argumente, die auch eine Liste nehmen — eine Auswahl ist dort kein Befund.
LISTE_ERLAUBT: Final = frozenset({("struktur_mit_nodeids", "angelegt")})
#: Die Listen, die ein Teil eines bekannten Typs trägt — sucht eine Auswahl eine andere, warnt die
#: Prüfung (Querschnitts-Review AS-D, Befund 2b).
LISTEN: Final[dict[str, frozenset[str]]] = {
    STRUKTUR: frozenset({"knoten"}),
    ANGELEGT: frozenset({"nodes"}),
    ABLAGE: frozenset({"inhalte", "frueher"}),
}
#: Modul → erwarteter Typ, wenn ``daten`` als Ganzes ein Teil ist (``daten: {"$teil": "draft"}``).
MODUL_EINGABE: Final[dict[str, str]] = {"ui_strukturentwurf": STRUKTUR,
                                        "ui_strukturabgleich": STRUKTURABGLEICH}

Typen = dict[str, str | None]


def modul_teile(module: dict[str, Any], modul: str | None) -> Typen:
    """Name → Typ der Teile, die Modul ``modul`` hinterlassen kann (``None``: Typ unbekannt)."""
    schreibt = ((module.get(modul or "") or {}).get("vorgang") or {}).get("schreibt") or []
    namen = [n for n in schreibt if isinstance(n, str)] + list(ZUSATZ_TEILE.get(modul or "", ()))
    return {n: MODUL_TEILE.get(n) for n in namen}


def teile_aus_dem_gespraech(module: dict[str, Any]) -> Typen:
    """Was irgendein Modul im Gespräch hinterlassen kann — es kann im Vorgang liegen, bevor ein
    Ablauf startet."""
    alle: Typen = {}
    for name in module:
        alle.update(modul_teile(module, name))
    return alle


def schritt_ausgaben(s: Schritt, module: dict[str, Any]) -> Typen:
    """Name → Typ der Teile, die Schritt ``s`` schreibt — je nach Art (ein verdecktes ``schreibt``
    an einer ``nachricht`` füllt nichts, Review AS-3b, Befund 9)."""
    aus: Typen = {}
    if s.typ == "werkzeug" and s.schreibt:
        aus[s.schreibt] = dienst_typ(s.werkzeug or "")
    if s.typ == "auftrag" and s.schreibt:
        aus[s.schreibt] = AUFTRAG
    if s.typ == "agent" and s.agent:
        for w in s.agent.werkzeuge:
            aus.update(modul_teile(module, w))
        if s.agent.ausgabe:
            aus[s.agent.ausgabe] = None
    if s.typ == "modul":
        aus.update(modul_teile(module, s.modul))
    if s.typ in ("nachricht", "modul") and s.freitext:
        aus[s.freitext.schreibt] = TEXT
    return aus


def dienst_typ(werkzeug: str) -> str:
    """Der Typ, den ein ``werkzeug``-Schritt seinem Ergebnis gibt — der Treiber speichert ihn
    (Review AS-Db, Befund 3: eine Quelle für Tabelle und Speicherung)."""
    if werkzeug in werkzeuge.DIENSTE:
        return DIENST_AUSGABE.get(werkzeug, _werkzeug_typ(werkzeug))
    return TEXT if werkzeug in werkzeuge.LESENDE_MCP else _werkzeug_typ(werkzeug)


def start_teile(ablauf: AblaufArea, module: dict[str, Any]) -> Typen:
    """Was vor dem Start da ist: die Teile des Moduls eines Modul-Auslösers und (AS-4a) die
    Startdaten, wenn der Ablauf ein Startschema hat."""
    alle: Typen = {START_TEIL: START} if ablauf.start else {}
    for a in ablauf.ausloeser:
        if a.art == "modul":
            alle.update(modul_teile(module, a.modul))
    return alle


def ausgaben(ablauf: AblaufArea, module: dict[str, Any] | None = None
             ) -> dict[str, set[str | None]]:
    """Name → die Typen aller Schreiber im Ablauf (auch Modul-Auslöser); ``None`` in der Menge: ein
    Schreiber mit unbekanntem Typ (dann kein Vergleich)."""
    if module is None:
        from boerdi.ui_module import katalog

        module = katalog.katalog()
    alle: dict[str, set[str | None]] = {}
    quellen = [schritt_ausgaben(s, module) for s in ablauf.schritte] + [start_teile(ablauf, module)]
    for teile in quellen:
        for name, typ in teile.items():
            alle.setdefault(name, set()).add(typ)
    return alle


def verweise(wert: Any) -> list[tuple[str, str | None, Any]]:
    """Name, Pfad (bei einer Auswahl ihre ``liste``) und Verweis-Objekt jedes ``$teil`` in
    ``wert`` — so tief, wie der Treiber einsetzt (``teil_verweise.TIEFE``; tiefer meldet die
    Prüfung ``zu_tief``). Derselbe Wanderer wie die Formprüfungen (``alle_verweise``)."""
    return [(n, p, w) for n, p, w, _t in alle_verweise(wert, bis=TIEFE)]


def schritt_verweise(s: Schritt) -> list[tuple[str, str | None, Any]]:
    """:func:`verweise` in ``daten`` und ``argumente`` des Schritts."""
    return verweise(s.daten) + verweise(s.argumente)


def verweis_namen(s: Schritt) -> list[str]:
    """Die Teile, die Schritt ``s`` über ``$teil`` liest (``daten``, ``argumente``; auch
    Auswahlen) — ohne Doppel, nur gültige Namen."""
    return [n for n in dict.fromkeys(n for n, _p, _w in schritt_verweise(s)) if NAME.match(n)]


def gelesene_teile(s: Schritt) -> list[str]:
    """Alle Teile, die Schritt ``s`` liest: ``$teil``, Platzhalter in ``text`` und ``freigabe``,
    an einer Verzweigung ``wenn_teil`` und die Quelle von ``wenn_wert`` — die eine Quelle für die
    Sicht „Daten“ und die Prüfung (Review AS-Dc, Befund 2)."""
    namen = verweis_namen(s)
    texte = [*(s.text or {}).values(), *(s.freigabe or {}).values()]
    namen += [name if art == "teil" else START_TEIL
              for t in texte for art, name, _p, gueltig in platzhalter.finden(t) if gueltig]
    if s.typ == "verzweigung" and isinstance(s.weiter, list):
        for r in s.weiter:
            if r.wenn_teil:
                namen.append(r.wenn_teil)
            if r.wenn_wert is not None and (q := vergleich.quelle(r.wenn_wert.quelle)) is not None:
                namen.append(q[0])
    return [n for n in dict.fromkeys(namen) if NAME.match(n)]


def auswahl_an_objekt(s: Schritt) -> list[str]:
    """Die Argumente eines Dienstes, die als Ganzes ein Objekt erwarten (:data:`DIENST_EINGABE`),
    aber eine Auswahl tragen — eine Auswahl ist immer eine Liste, der Dienst lieferte nie etwas
    (Querschnitts-Review AS-D, Befund 2c; für Module ``daten_auswahl``)."""
    if s.typ != "werkzeug":
        return []
    name = s.werkzeug or ""
    return [arg for arg in DIENST_EINGABE.get(name, {})
            if (name, arg) not in LISTE_ERLAUBT and ist_auswahl((s.argumente or {}).get(arg))]


def auswahl_liste(wert: Any) -> str | None:
    """Das erste Glied der ``liste`` einer Auswahl (``None`` ohne)."""
    liste = wert.get("liste") if isinstance(wert, dict) else None
    return liste.split(".")[0] if isinstance(liste, str) and liste else None


def erwartete_eingaben(s: Schritt) -> list[tuple[str, str]]:
    """(Teilname, erwarteter Typ) der ganzen Teile, die Schritt ``s`` liest."""
    erwartet: list[tuple[str, str]] = []
    if s.typ == "werkzeug" and (eingabe := DIENST_EINGABE.get(s.werkzeug or "")):
        for arg, typ in eingabe.items():
            wert = (s.argumente or {}).get(arg)
            if (v := verweis(wert)) is not None and v[1] is None and not ist_auswahl(wert):
                erwartet.append((v[0], typ))
    if s.typ == "modul" and (typ := MODUL_EINGABE.get(s.modul or "")):
        if (v := verweis(s.daten)) is not None and v[1] is None and not ist_auswahl(s.daten):
            erwartet.append((v[0], typ))
    return erwartet
