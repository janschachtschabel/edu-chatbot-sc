"""SW-4 (Plan 2026-11-14, Werkzeuge für Sammlungsstrukturen): der Strukturabgleich bis Ebene 4.

Führt der MCP-Server ``list_collection_tree`` (Stand „Sammlungsstrukturen“, 14.11.2026), liest
der Dienst den ganzen Baum als Liste und gleicht alle vier Ebenen ab; sonst bleibt es bei
``browse_collection_tree`` und zwei Ebenen (``test_strukturabgleich_u4``).

Die Antwortform stammt von diesem Stand, lokal gestartet gegen das Staging-Repository
(14.11.2026): ``path`` beginnt mit dem Titel der gelesenen Sammlung und endet mit dem eigenen,
``depth`` zählt ab 1 unter ihr, ``parentId`` ist die Elternsammlung. Der Server liest Ebene für
Ebene und sagt für die Liste, was er nicht lesen konnte (``incomplete``, ``restricted``) und wo
sie abbricht (``walkCapped``, ``skipLimitReached``).
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from boerdi.domain import strukturabgleich as sa
from boerdi.services import abdeckung, agent_tools
from boerdi.services.mcp import baum_lesen, client, faehigkeiten
from boerdi.services.mcp.client import McpAntwort
from boerdi.ui_module import dienst_strukturabgleich as dienst
from boerdi.ui_module import katalog
from boerdi.ui_module.aufruf import Umgebung, asynchron

MODUL = "ui_strukturabgleich"
OPTIK = "9e7ae956-e9df-430f-bace-f3db4b910013"
NAME = baum_lesen.WERKZEUG
BROWSE = "browse_collection_tree"


def _eintrag(kennung: str, pfad: list[str], eltern: str = OPTIK, **mehr) -> dict:
    return {"nodeId": kennung, "title": pfad[-1], "path": ["Optik", *pfad], "depth": len(pfad),
            "parentId": eltern, **mehr}


_LISTE = {
    "root": {"nodeId": OPTIK, "title": "Optik"}, "depth": 4, "count": 6, "skipCount": 0,
    "items": [
        _eintrag("g", ["Geometrische Optik"], contentCount=4),
        _eintrag("w", ["Wellenoptik"], contentCount=3),
        _eintrag("g-l", ["Geometrische Optik", "Linsen"], "g", contentCount=7),
        _eintrag("w-b", ["Wellenoptik", "Beugung"], "w"),
        _eintrag("g-l-s", ["Geometrische Optik", "Linsen", "Sammellinsen"], "g-l", contentCount=2),
        _eintrag("g-l-s-b", ["Geometrische Optik", "Linsen", "Sammellinsen", "Brennweite"],
                 "g-l-s", contentCount=0),
    ]}

_ENTWURF = {"titel": "Optik neu", "quelle": "ki", "knoten": [
    {"id": "k1", "titel": "Geometrische Optik", "kinder": [
        {"id": "k1-1", "titel": "Linsen", "kinder": [
            {"id": "k1-1-1", "titel": "Sammellinsen", "kinder": [
                {"id": "k1-1-1-1", "titel": "Brennweite"},
                {"id": "k1-1-1-2", "titel": "Abbildungsgleichung"}]},
            {"id": "k1-1-2", "titel": "Zerstreuungslinsen"}]}]},
    {"id": "k2", "titel": "Quantenoptik", "kinder": [
        {"id": "k2-1", "titel": "Photonen", "kinder": [{"id": "k2-1-1", "titel": "Beugung"}]}]},
]}
#: Die neuen Punkte des Entwurfs gegen ``_LISTE`` mit ihrer Ebene.
_NEU = {"k1-1-1-2": 4, "k1-1-2": 3, "k2": 1, "k2-1": 2, "k2-1-1": 3}


def _arten(erg: dict) -> dict:
    return {z["id"]: (z["art"], z.get("wlo", {}).get("nodeId")) for z in erg["zeilen"]}


def _ungewiss(zeilen: list[dict]) -> set[str]:
    assert not any("ungewiss" in z for z in zeilen if z["art"] != "neu")
    return {z["id"] for z in zeilen if z.get("ungewiss")}


def _mit(liste: dict, kennung: str, **marken) -> dict:
    return {**liste, "items": [{**e, **marken} if e["nodeId"] == kennung else e
                               for e in liste["items"]]}


# ── Rein: die Liste lesen ────────────────────────────────────────────────────────────────────

def test_die_liste_wird_zu_sammlungen_aller_ebenen():
    wlo = sa.wlo_aus_liste(_LISTE)
    assert [(w["nodeId"], w["ebene"], w["eltern"], w["eltern_titel"]) for w in wlo] == [
        ("g", 1, None, None), ("w", 1, None, None), ("g-l", 2, "g", "Geometrische Optik"),
        ("w-b", 2, "w", "Wellenoptik"), ("g-l-s", 3, "g-l", "Linsen"),
        ("g-l-s-b", 4, "g-l-s", "Sammellinsen")]
    # Die Inhaltszahl heißt hier ``contentCount``; die Liste ist je Elternknoten ungekürzt.
    assert [w["anzahl"] for w in wlo] == [4, 3, 7, None, 2, 0]
    assert not any(w["mehr"] for w in wlo)


def test_marken_je_sammlung_zaehlen_nicht():
    """Zweites Review SW-4, Befund 1: Sie stehen nur an Einträgen der gelieferten Seite, und für
    die gelesene Sammlung selbst gibt es keine — „nur dort ungewiss“ ließe einen zweiten Ausfall
    als nicht geschehen gelten. Der Dienst nimmt die Marke der ganzen Liste."""
    liste = _mit(_mit(_LISTE, "w", childrenUnread=True), "g-l", childrenRefused=True)
    assert not any(w["mehr"] for w in sa.wlo_aus_liste(liste))


def test_die_tiefe_des_entwurfs():
    assert sa.tiefe_von(_ENTWURF) == 4
    assert sa.tiefe_von({"knoten": [{"titel": "A1", "kinder": [{"titel": "B2"}]}]}) == 2
    tief = {"knoten": [{"titel": "1", "kinder": [{"titel": "2", "kinder": [{"titel": "3",
            "kinder": [{"titel": "4", "kinder": [{"titel": "5"}]}]}]}]}]}
    assert sa.tiefe_von(tief) == sa.TIEFE_LISTE
    # Ein Punkt ohne Titel zählt mit allem darunter nicht.
    assert sa.tiefe_von({"knoten": [{"titel": "", "kinder": [{"titel": "B"}]}]}) == 0
    assert sa.tiefe_von(None) == 0 and sa.tiefe_von({"knoten": "x"}) == 0


def test_kaputte_eintraege_der_liste_fallen_weg():
    kaputt = {"items": [
        "x", {"nodeId": "a", "title": "A", "depth": 0}, {"nodeId": "b", "title": "B", "depth": 5},
        {"nodeId": "c", "title": "C", "depth": True}, {"nodeId": "d", "title": "D", "depth": 2},
        {"nodeId": "e", "title": "E", "depth": 2, "parentId": ""},
        {"title": "ohne Kennung", "depth": 1},
        {"nodeId": "f", "title": "F", "depth": 2, "parentId": "p", "path": "kein Pfad"}]}
    assert sa.wlo_aus_liste(kaputt) == [
        {"nodeId": "f", "titel": "F", "ebene": 2, "eltern": "p", "eltern_titel": "",
         "anzahl": None, "mehr": False}]
    assert sa.wlo_aus_liste(None) == [] and sa.wlo_aus_liste({"items": "x"}) == []
    # Ein Server, der sich nicht an ``maxItems`` hält, bremst die Schleife nicht.
    viele = {"items": [_eintrag(f"n{i}", [f"Thema {i}"]) for i in range(sa.LISTE_SEITE + 50)]}
    assert len(sa.wlo_aus_liste(viele)) == sa.LISTE_SEITE


# ── Rein: der Abgleich je Ebene ──────────────────────────────────────────────────────────────

def test_vier_ebenen_unter_der_zugeordneten_sammlung():
    erg = sa.abgleichen(_ENTWURF, sa.wlo_aus_liste(_LISTE), tiefe=sa.TIEFE_LISTE)
    assert _arten(erg) == {
        "k1": ("vorhanden", "g"), "k1-1": ("vorhanden", "g-l"),
        "k1-1-1": ("vorhanden", "g-l-s"), "k1-1-1-1": ("vorhanden", "g-l-s-b"),
        "k1-1-1-2": ("neu", None), "k1-1-2": ("neu", None),
        # „Beugung“ gibt es nur auf Ebene 2 — der Punkt der Ebene 3 bekommt sie nicht.
        "k2": ("neu", None), "k2-1": ("neu", None), "k2-1-1": ("neu", None)}
    assert {z["id"]: z["ebene"] for z in erg["zeilen"] if z["art"] == "neu"} == _NEU
    assert [z["ebene"] for z in erg["zeilen"]] == [1, 2, 3, 4, 4, 3, 1, 2, 3]
    assert {w["nodeId"]: (w["ebene"], w.get("eltern_titel")) for w in erg["nur_in_wlo"]} == {
        "w": (1, None), "w-b": (2, "Wellenoptik")}
    assert erg["zahlen"] == {"vorhanden": 4, "aehnlich": 0, "neu": 5, "nur_in_wlo": 2}
    assert erg["gekuerzt"] is False and _ungewiss(erg["zeilen"]) == set()
    # Unter dem zugeordneten Elternpunkt gefunden: die Sammlung darüber steht nicht noch einmal da.
    assert not any("eltern_titel" in z.get("wlo", {}) for z in erg["zeilen"])


def test_ohne_die_liste_bleibt_es_bei_zwei_ebenen():
    erg = sa.abgleichen(_ENTWURF, sa.wlo_aus_liste(_LISTE))
    assert [z["id"] for z in erg["zeilen"]] == ["k1", "k1-1", "k2", "k2-1"]
    # Was tiefer liegt, hat dann keinen Punkt — es steht unter „nur in WLO“.
    assert {"g-l-s", "g-l-s-b"} <= {w["nodeId"] for w in erg["nur_in_wlo"]}


def test_ein_gebundener_punkt_nimmt_nur_kinder_seiner_sammlung():
    """Wie auf Ebene 2 (Review U4, Befund 3) — auf jeder Ebene: erst die gebundenen Punkte unter
    ihrer Sammlung, dann die ungebundenen gegen den Rest der Ebene."""
    liste = {"items": [
        _eintrag("a", ["Akustik"]), _eintrag("b", ["Biophysik"]),
        _eintrag("a-x", ["Akustik", "Grundlagen"], "a"),
        _eintrag("b-x", ["Biophysik", "Grundlagen"], "b"),
        _eintrag("a-x-l", ["Akustik", "Grundlagen", "Linsen"], "a-x"),
        _eintrag("b-x-l", ["Biophysik", "Grundlagen", "Linsen"], "b-x")]}
    entwurf = {"knoten": [
        {"id": "n", "titel": "Neu", "kinder": [{"id": "n-y", "titel": "Yttrium", "kinder": [
            {"id": "n-y-l", "titel": "Linsen"}]}]},
        {"id": "b", "titel": "Biophysik", "kinder": [{"id": "b-x", "titel": "Grundlagen",
                                                     "kinder": [{"id": "b-x-l",
                                                                 "titel": "Linsen"}]}]}]}
    erg = sa.abgleichen(entwurf, sa.wlo_aus_liste(liste), tiefe=4)
    art = _arten(erg)
    assert art["b-x"] == ("vorhanden", "b-x") and art["b-x-l"] == ("vorhanden", "b-x-l")
    # Der ungebundene Punkt bekommt, was auf seiner Ebene übrig ist …
    assert art["n-y-l"] == ("vorhanden", "a-x-l") and art["n-y"] == ("neu", None)
    # … und sagt, unter welcher Sammlung — „Linsen“ gibt es in vielen Zweigen.
    wlo = {z["id"]: z.get("wlo", {}) for z in erg["zeilen"]}
    assert wlo["n-y-l"]["eltern_titel"] == "Grundlagen"
    assert "eltern_titel" not in wlo["b-x-l"] and "eltern_titel" not in wlo["b"]


def test_unvollstaendig_ab_einer_ebene_heisst_dort_nicht_gefunden():
    """Der Server liest Ebene für Ebene: Bricht die Liste ab, ist die tiefste gelesene Ebene
    unvollständig — „neu“ darüber bleibt verbindlich."""
    wlo = sa.wlo_aus_liste(_LISTE)
    for ab in (1, 2, 3, 4):
        erg = sa.abgleichen(_ENTWURF, wlo, tiefe=4, unvollstaendig_ab=ab)
        assert _ungewiss(erg["zeilen"]) == {k for k, ebene in _NEU.items() if ebene >= ab}, ab
        assert erg["gekuerzt"] is True


def test_ein_punkt_ohne_titel_faellt_mit_allem_darunter_weg():
    """Er lässt sich nicht anlegen — und seine Kinder hingen sonst am Geschwister davor (im
    Abgleich wie in der Anzeige)."""
    liste = {"items": [_eintrag("a", ["Akustik"]), _eintrag("a-l", ["Akustik", "Linsen"], "a")]}
    entwurf = {"knoten": [
        {"id": "a", "titel": "Akustik"},
        {"id": "leer", "titel": " ", "kinder": [{"id": "kind", "titel": "Linsen", "kinder": [
            {"id": "enkel", "titel": "Brennweite"}]}]}]}
    for tiefe in (sa.TIEFE_BAUM, sa.TIEFE_LISTE):
        erg = sa.abgleichen(entwurf, sa.wlo_aus_liste(liste), tiefe=tiefe)
        assert _arten(erg) == {"a": ("vorhanden", "a")}, tiefe
        assert [w["nodeId"] for w in erg["nur_in_wlo"]] == ["a-l"]
    # Die Zählung der Abdeckung sieht dieselben Punkte — sonst zählte sie welche ohne Zeile.
    assert [p.id for p in abdeckung.punkte_aus_entwurf(entwurf)] == ["a"]


# ── Dienst ───────────────────────────────────────────────────────────────────────────────────

class _Server:
    """Antwortet je Aufruf mit der nächsten Antwort (die letzte bleibt)."""

    def __init__(self, *antworten):
        self.aufrufe: list = []
        self.antworten = list(antworten)

    async def __call__(self, tool, args, **kw):
        self.aufrufe.append((tool, args, kw))
        return self.antworten[min(len(self.aufrufe), len(self.antworten)) - 1]

    @property
    def werkzeuge(self) -> list[str]:
        return [a[0] for a in self.aufrufe]


def _teile(wert):
    async def lader(name):
        return wert if name == "draft" else None
    return lader


def _server_kennt_die_liste() -> None:
    assert faehigkeiten.uebernehmen([
        {"name": NAME, "input_schema": {"properties": {p: {} for p in (
            "nodeId", "collection", "depth", "maxItems", "skipCount", "includeContentCounts")}}},
        {"name": BROWSE, "input_schema": {"properties": {"nodeId": {}}}}])


def _lauf(monkeypatch, server, args=None, **umgebung):
    monkeypatch.setattr(client, "call_mcp_tool_antwort", server)
    return asyncio.run(asynchron(MODUL, args or {"sammlung": OPTIK},
                                 Umgebung(teile=_teile(_ENTWURF), **umgebung)))


def _liste(struktur: dict) -> McpAntwort:
    return McpAntwort("Sammlungsbaum …", strukturiert=struktur)


_ALT = McpAntwort("{}", strukturiert={"parent": OPTIK, "results": [
    {"nodeId": "g", "title": "Geometrische Optik", "children": [
        {"nodeId": "g-l", "title": "Linsen"}]}]})


def test_der_dienst_liest_die_liste_wenn_der_server_sie_fuehrt(monkeypatch):
    _server_kennt_die_liste()
    server = _Server(_liste(_LISTE))
    erg = _lauf(monkeypatch, server, {"sammlung": OPTIK, "titel": "von der KI genannt"})
    [(tool, args, kw)] = server.aufrufe
    assert tool == NAME and kw == {"use_cache": False}
    assert args == {"nodeId": OPTIK, "depth": 4, "maxItems": 250, "skipCount": 0,
                    "includeContentCounts": True}
    assert erg.block is not None and erg.outcome.status == "success"
    daten = erg.block.daten
    assert not katalog.daten_fehler(katalog.katalog()[MODUL], daten)
    assert [z["ebene"] for z in daten["zeilen"]] == [1, 2, 3, 4, 4, 3, 1, 2, 3]
    # Der Titel der gelesenen Sammlung kommt vom Server, nicht aus dem Argument.
    assert daten["sammlung"]["nodeId"] == OPTIK and daten["sammlung"]["titel"] == "Optik"
    assert daten["gekuerzt"] is False and "unvollstaendig" not in daten
    assert daten["zahlen"]["vorhanden"] == 4
    brennweite = next(z for z in daten["zeilen"] if z["id"] == "k1-1-1-1")
    assert brennweite["wlo"]["nodeId"] == "g-l-s-b" and brennweite["wlo"]["anzahl"] == 0
    assert "größer als gezeigt" not in erg.text and "vollständig" not in erg.text
    assert "4 Punkte vorhanden" in erg.text


def test_ohne_die_liste_am_server_bleibt_der_alte_weg(monkeypatch):
    server = _Server(_ALT)
    erg = _lauf(monkeypatch, server)
    assert server.werkzeuge == [BROWSE]
    assert [z["id"] for z in erg.block.daten["zeilen"]] == ["k1", "k1-1", "k2", "k2-1"]


def test_das_angebot_des_zugs_entscheidet_nicht(monkeypatch):
    """Entscheid SE-5: Ein KI-Schritt eines Ablaufs engt das Angebot auf seine Werkzeuge ein
    (``ki_schritt.einengen``) — die Baumliste steht dann nicht darin, und gerade dort wird tief
    abgeglichen. Maßgeblich ist der Stand des Servers; lesen darf der Dienst über
    ``dienst.braucht``."""
    _server_kennt_die_liste()
    for umgebung in ({"verfuegbar": frozenset({"search_wlo_all", MODUL})},
                     {"verfuegbar": frozenset({NAME})}, {"aus_ablauf": True}, {}):
        server = _Server(_liste(_LISTE))
        _lauf(monkeypatch, server, **umgebung)
        assert server.werkzeuge == [NAME], umgebung


def test_im_studio_abgeschaltet_liest_der_dienst_die_liste_nicht(monkeypatch):
    """Review SW-4, Befund 1: Wer die Baumliste am MCP-Server abschaltet (etwa wegen der Last),
    stoppt auch ihren teuersten Aufrufer."""
    _server_kennt_die_liste()
    monkeypatch.setattr(agent_tools, "verborgene_werkzeuge", lambda: frozenset({NAME}))
    server = _Server(_ALT)
    erg = _lauf(monkeypatch, server)
    assert server.werkzeuge == [BROWSE]
    assert [z["id"] for z in erg.block.daten["zeilen"]] == ["k1", "k1-1", "k2", "k2-1"]


def test_bleibt_dem_lauf_zu_wenig_zeit_liest_der_dienst_zwei_ebenen(monkeypatch):
    """Ein Fachportal mit Inhaltszahlen dauerte 11–19 s (gemessen 14.11.2026), der alte Weg 4–5."""
    _server_kennt_die_liste()

    async def lauf(rest_s: float):
        ende = asyncio.get_running_loop().time() + rest_s
        return await asynchron(MODUL, {"sammlung": OPTIK},
                               Umgebung(teile=_teile(_ENTWURF), frist_ende=ende))

    # Reserve des Laufs, eine Seite der Liste und der alte Weg, falls die Seite in ihre Frist läuft
    knapp = dienst.RESERVE_S + dienst._LISTE_BRAUCHT_S + dienst._RUECKFALL_S
    server = _Server(_ALT)
    monkeypatch.setattr(client, "call_mcp_tool_antwort", server)
    assert asyncio.run(lauf(knapp - 1)).block is not None
    assert server.werkzeuge == [BROWSE]
    server = _Server(_liste(_LISTE))
    monkeypatch.setattr(client, "call_mcp_tool_antwort", server)
    assert asyncio.run(lauf(knapp + 5)).block is not None
    assert server.werkzeuge == [NAME]


def test_ganz_gelesen_ist_nicht_gekuerzt_auch_wenn_nur_in_wlo_gedeckelt_ist(monkeypatch):
    """``gekuerzt`` heißt im Modul „nicht gefunden ist nicht sicher neu“ — das stimmt nicht, wenn
    der ganze Baum gelesen wurde und nur die Liste darunter gedeckelt ist."""
    _server_kennt_die_liste()
    viele = {**_LISTE, "items": [_eintrag(f"n{i}", [f"Thema {i}"]) for i in range(130)]}
    erg = _lauf(monkeypatch, _Server(_liste(viele)))
    daten = erg.block.daten
    assert len(daten["nur_in_wlo"]) == dienst.NUR_IN_WLO and daten["zahlen"]["nur_in_wlo"] == 130
    assert daten["gekuerzt"] is False and "größer als gezeigt" not in erg.text
    erg = _lauf(monkeypatch, _Server(_liste({**viele, "incomplete": True})))
    assert erg.block.daten["gekuerzt"] is True and erg.block.daten["unvollstaendig"] is True


def test_weitere_seiten_werden_gelesen_und_doppelte_zaehlen_einmal(monkeypatch):
    _server_kennt_die_liste()
    # Die Seiten überlappen: Bei einem Ausfall sind die Positionen des Servers nicht verlässlich.
    seite1 = {**_LISTE, "items": _LISTE["items"][:4], "more": {"nextSkipCount": 250}}
    seite2 = {**_LISTE, "skipCount": 250, "items": _LISTE["items"][2:]}
    server = _Server(_liste(seite1), _liste(seite2))
    erg = _lauf(monkeypatch, server)
    assert [a[1]["skipCount"] for a in server.aufrufe] == [0, 250]
    daten = erg.block.daten
    assert daten["zahlen"] == {"vorhanden": 4, "aehnlich": 0, "neu": 5, "nur_in_wlo": 2}
    assert [w["nodeId"] for w in daten["nur_in_wlo"]] == ["w", "w-b"]
    assert daten["gekuerzt"] is False


def test_bricht_die_liste_ab_ist_nur_die_tiefste_gelesene_ebene_ungewiss(monkeypatch):
    _server_kennt_die_liste()
    bis_ebene_3 = {**_LISTE, "items": _LISTE["items"][:5]}
    # die Grenze des Servers, oder mehr Seiten, als er hergibt
    for marke in ({"walkCapped": True}, {"skipLimitReached": True}):
        erg = _lauf(monkeypatch, _Server(_liste({**bis_ebene_3, **marke})))
        daten = erg.block.daten
        # „Brennweite“ (Ebene 4) wurde nicht gelesen: ab Ebene 3 heißt es „nicht gefunden“ …
        assert _ungewiss(daten["zeilen"]) == {"k1-1-2", "k2-1-1", "k1-1-1-1", "k1-1-1-2"}, marke
        # … auf Ebene 1 und 2 bleibt „neu“ verbindlich.
        assert daten["unvollstaendig"] is True and daten["gekuerzt"] is True
        assert "nicht vollständig gelesen: 4 der neuen Punkte" in erg.text
        assert "größer als gezeigt" not in erg.text
        assert not katalog.daten_fehler(katalog.katalog()[MODUL], daten)

    def seite(ab: int, weiter, items=()):
        return _liste({**_LISTE, "skipCount": ab, "items": list(items),
                       "more": {"nextSkipCount": weiter}})

    # Nach der dritten Seite gäbe es noch mehr.
    server = _Server(seite(0, 250, _LISTE["items"][:2]), seite(250, 500, _LISTE["items"][2:4]),
                     seite(500, 750))
    erg = _lauf(monkeypatch, server)
    assert [a[1]["skipCount"] for a in server.aufrufe] == [0, 250, 500]
    assert "k2" not in _ungewiss(erg.block.daten["zeilen"])
    assert {k for k, e in _NEU.items() if e >= 2} <= _ungewiss(erg.block.daten["zeilen"])
    # Ein Zeiger, der nicht vorwärts führt, oder ``more`` in einer fremden Form: Es gäbe mehr —
    # keine Schleife, und nie „vollständig“.
    for mehr in ({"nextSkipCount": 0}, {"nextSkipCount": "250"}, {"nextSkipCount": None},
                 {"nextSkipCount": True}, {}, True, 250, [250], "ja"):
        server = _Server(_liste({**_LISTE, "items": [], "more": mehr}))
        erg = _lauf(monkeypatch, server)
        assert len(server.aufrufe) == 1 and erg.block.daten["unvollstaendig"] is True, mehr
        assert len(_ungewiss(erg.block.daten["zeilen"])) == 9, mehr


def test_nach_einem_ausfall_ist_kein_neu_verbindlich(monkeypatch):
    """Zweites Review SW-4, Befund 1: ``incomplete``/``restricted`` gelten für den ganzen Lauf des
    Servers. Wo es war, sagt die Antwort nicht verlässlich — auch nicht, wenn eine Sammlung eine
    Marke trägt (es kann einen zweiten Ausfall geben, an einer Sammlung einer anderen Seite oder
    an der gelesenen Sammlung selbst)."""
    _server_kennt_die_liste()
    for marke, feld in (("incomplete", "childrenUnread"), ("restricted", "childrenRefused")):
        for liste in ({**_LISTE, marke: True},
                      {**_mit(_LISTE, "g-l", **{feld: True}), marke: True}):
            erg = _lauf(monkeypatch, _Server(_liste(liste)))
            assert _ungewiss(erg.block.daten["zeilen"]) == set(_NEU), marke
            assert erg.block.daten["unvollstaendig"] is True and "nicht gefunden" in erg.text
        # … und nicht, wenn erst die zweite Seite ihn meldet.
        seite1 = {**_LISTE, "items": _LISTE["items"][:3], "more": {"nextSkipCount": 250}}
        seite2 = {**_LISTE, "skipCount": 250, "items": _LISTE["items"][3:], marke: True}
        erg = _lauf(monkeypatch, _Server(_liste(seite1), _liste(seite2)))
        assert _ungewiss(erg.block.daten["zeilen"]) == set(_NEU), marke


def test_eine_antwort_ohne_items_ist_keine_baumliste(monkeypatch):
    """Zweites Review SW-4, Befund 2: Sonst hieße eine fremde Antwort „keine Untersammlungen“
    und jeder Punkt verbindlich „neu“."""
    _server_kennt_die_liste()
    for fremd in ({"foo": 1}, {"items": "x"}, {"error": {"code": "internal"}}):
        server = _Server(McpAntwort("…", strukturiert=fremd), _ALT)
        erg = _lauf(monkeypatch, server)
        assert server.werkzeuge == [NAME, BROWSE], fremd
        assert [z["id"] for z in erg.block.daten["zeilen"]] == ["k1", "k1-1", "k2", "k2-1"]
    # Auf einer Folgeseite: abgebrochen, das Gelesene bleibt.
    seite1 = _liste({**_LISTE, "items": _LISTE["items"][:2], "more": {"nextSkipCount": 250}})
    erg = _lauf(monkeypatch, _Server(seite1, McpAntwort("…", strukturiert={"foo": 1})))
    assert erg.block.daten["unvollstaendig"] is True


def test_die_liste_wird_nur_so_tief_gelesen_wie_der_entwurf_reicht(monkeypatch):
    """Tiefer zu lesen kostete je Sammlung eine Abfrage (und stieß früher an die Grenze des
    Servers), ohne dass ein Punkt dazu passte — mindestens aber zwei Ebenen, wie bisher."""
    _server_kennt_die_liste()
    for entwurf, tiefe in (({"knoten": [{"id": "a", "titel": "Geometrische Optik"}]}, 2),
                           ({"knoten": [{"id": "a", "titel": "Geometrische Optik", "kinder": [
                               {"id": "b", "titel": "Linsen", "kinder": [
                                   {"id": "c", "titel": "Sammellinsen"}]}]}]}, 3),
                           (_ENTWURF, 4)):
        server = _Server(_liste(_LISTE))
        monkeypatch.setattr(client, "call_mcp_tool_antwort", server)
        erg = asyncio.run(asynchron(MODUL, {"sammlung": OPTIK}, Umgebung(teile=_teile(entwurf))))
        assert [a[1]["depth"] for a in server.aufrufe] == [tiefe]
        assert max(z["ebene"] for z in erg.block.daten["zeilen"]) <= tiefe


def test_faellt_die_liste_aus_liest_der_dienst_zwei_ebenen(monkeypatch):
    """Review SW-4, Befund 3: Ein Ausfall der neuen Liste darf den Abgleich nicht kosten, der
    vorher in 4 bis 5 s gelang."""
    _server_kennt_die_liste()
    for ausfall in (McpAntwort("MCP error: keine Antwort", "timeout"),
                    McpAntwort("MCP error [unknown_tool]: weg", "tool", "unknown_tool"),
                    McpAntwort("Sammlungsbaum … (ohne strukturierten Teil)")):
        server = _Server(ausfall, _ALT)
        erg = _lauf(monkeypatch, server)
        assert server.werkzeuge == [NAME, BROWSE]
        assert [z["id"] for z in erg.block.daten["zeilen"]] == ["k1", "k1-1", "k2", "k2-1"]
    # Gibt es die Sammlung nicht, sagt das der alte Weg.
    erg = _lauf(monkeypatch, _Server(McpAntwort("MCP error [not_found]: weg", "tool", "not_found")))
    assert erg.block is None and erg.outcome.error == "sammlung"
    erg = _lauf(monkeypatch, _Server(McpAntwort("MCP error: keine Antwort", "timeout")))
    assert erg.outcome.status == "timeout" and erg.outcome.error == "timeout"


def test_dauert_die_liste_zu_lange_liest_der_dienst_zwei_ebenen(monkeypatch):
    """Die eigene Frist der Liste: gemessen dauerte ein Fachportal einmal 38 s statt 11."""
    _server_kennt_die_liste()
    monkeypatch.setattr(dienst, "_LISTE_BRAUCHT_S", 0.05)
    aufrufe: list[str] = []

    async def server(tool, args, **kw):
        aufrufe.append(tool)
        if tool == NAME:
            await asyncio.sleep(5)
        return _ALT

    erg = _lauf(monkeypatch, server)
    assert aufrufe == [NAME, BROWSE]
    assert [z["id"] for z in erg.block.daten["zeilen"]] == ["k1", "k1-1", "k2", "k2-1"]
    assert "unvollstaendig" not in erg.block.daten


def test_faellt_eine_folgeseite_aus_bleibt_das_gelesene(monkeypatch):
    _server_kennt_die_liste()
    seite1 = _liste({**_LISTE, "items": _LISTE["items"][:4], "more": {"nextSkipCount": 250}})
    server = _Server(seite1, McpAntwort("MCP error: keine Antwort", "timeout"))
    erg = _lauf(monkeypatch, server)
    assert server.werkzeuge == [NAME, NAME] and erg.block is not None
    daten = erg.block.daten
    # Gelesen sind Ebene 1 und ein Teil der Ebene 2: ab dort „nicht gefunden“, darüber nicht.
    assert daten["unvollstaendig"] is True
    neu = {z["id"]: z.get("ungewiss", False) for z in daten["zeilen"] if z["art"] == "neu"}
    assert neu.pop("k2") is False and neu and all(neu.values())


def test_reicht_die_zeit_nicht_fuer_die_naechste_seite_endet_das_lesen(monkeypatch):
    _server_kennt_die_liste()
    antworten = iter([True, False])              # vor Seite 1 ja, vor Seite 2 nein
    monkeypatch.setattr(dienst, "_zeit_reicht", lambda umgebung, dazu=0.0: next(antworten))
    seite1 = _liste({**_LISTE, "items": _LISTE["items"][:2], "more": {"nextSkipCount": 250}})
    server = _Server(seite1)
    erg = _lauf(monkeypatch, server)
    assert server.werkzeuge == [NAME]
    daten = erg.block.daten
    assert daten["unvollstaendig"] is True
    # Nur Ebene 1 ist gelesen, und die nicht sicher ganz: jedes „neu“ ist „nicht gefunden“.
    neu = [z for z in daten["zeilen"] if z["art"] == "neu"]
    assert neu and all(z.get("ungewiss") for z in neu)


def test_nach_der_gesamtzeit_beginnt_keine_weitere_seite(monkeypatch):
    """Auch ohne Frist des Laufs (Muster-Weg, Ablauf): Zwei Seiten zu je unter 30 s dürfen
    zusammen länger dauern, eine dritte beginnt dann nicht mehr."""
    _server_kennt_die_liste()
    uhr = iter([0.0, 10.0, 40.0])                # Beginn, vor Seite 2, vor Seite 3
    monkeypatch.setattr(dienst, "_jetzt", lambda: next(uhr))

    def seite(ab: int, items):
        return _liste({**_LISTE, "skipCount": ab, "items": items,
                       "more": {"nextSkipCount": ab + 250}})

    server = _Server(seite(0, _LISTE["items"][:2]), seite(250, _LISTE["items"][2:4]),
                     seite(500, _LISTE["items"][4:]))
    erg = _lauf(monkeypatch, server)
    assert [a[1]["skipCount"] for a in server.aufrufe] == [0, 250]
    assert erg.block.daten["unvollstaendig"] is True


def test_adressen_und_titel_der_gelesenen_sammlung(monkeypatch):
    _server_kennt_die_liste()
    monkeypatch.setattr("boerdi.ui_module.themenbaum._wurzel_url",
                        lambda kennung: f"https://wlo.example/{kennung}")
    andere = "11111111-1111-1111-1111-111111111111"
    geo = "22222222-2222-2222-2222-222222222222"
    liste = {"root": {"nodeId": andere, "title": "  Optik \n (Portal) " + "x" * 200},
             "items": [_eintrag(geo, ["Geometrische Optik"], andere),
                       _eintrag("x?id=1#frag", ["Quantenoptik"], andere)]}
    erg = _lauf(monkeypatch, _Server(_liste(liste)), {"sammlung": OPTIK, "titel": "Physik"})
    sammlung = erg.block.daten["sammlung"]
    assert sammlung["nodeId"] == andere and sammlung["url"] == f"https://wlo.example/{andere}"
    assert sammlung["titel"].startswith("Optik (Portal) x") and len(sammlung["titel"]) == 120
    wlo = {z["id"]: z["wlo"] for z in erg.block.daten["zeilen"] if "wlo" in z}
    assert wlo["k1"]["url"] == f"https://wlo.example/{geo}"
    # Nur eine Kennung in UUID-Form wird zur Adresse.
    assert wlo["k2"]["nodeId"] == "x?id=1#frag" and "url" not in wlo["k2"]
    # Ohne Titel vom Server — oder mit der Kennung als Ersatz — gilt der aus dem Argument, wenn
    # es dieselbe Sammlung ist.
    for wurzel in ({"nodeId": OPTIK}, {"nodeId": OPTIK, "title": OPTIK}):
        erg = _lauf(monkeypatch, _Server(_liste({**_LISTE, "root": wurzel})),
                    {"sammlung": OPTIK, "titel": "Physik"})
        assert erg.block.daten["sammlung"]["titel"] == "Physik", wurzel


# ── Abdeckung (SE-9: gezählt wird für Ebene 1 und 2) ─────────────────────────────────────────

def test_die_abdeckung_zaehlt_tiefe_zeilen_nicht_und_sagt_es(monkeypatch):
    _server_kennt_die_liste()
    daten = _lauf(monkeypatch, _Server(_liste(_LISTE))).block.daten
    zeilen = daten["zeilen"]
    # Eine tiefe Zeile mit der Kennung eines Punkts (kaputter Entwurf) bekäme sonst dessen Treffer.
    next(z for z in zeilen if z["id"] == "k1-1-2")["id"] = "k2"
    z = SimpleNamespace(treffer={"k1": {"total": 40, "top": []}, "k2": {"total": 0, "top": []},
                                 "k1-1": {"total": 9, "top": []}},
                        fehlen={"k2-1": "keine_antwort"})
    summe = dienst._abdeckung_eintragen(z, zeilen)
    tief = [zl for zl in zeilen if zl["ebene"] > abdeckung.TIEFE]
    assert len(tief) == 5 and all(zl["abdeckung_fehlt"] == "ebene" for zl in tief)
    assert not any("abdeckung" in zl for zl in tief)
    quanten = next(zl for zl in zeilen if zl["id"] == "k2" and zl["ebene"] == 1)
    assert quanten["abdeckung"] == {"total": 0, "luecke": True}
    # „Ungezählt“ ist nur, was hätte gezählt werden sollen.
    assert summe["gezaehlt"] == 3 and summe["ungezaehlt"] == 1 and summe["luecken"] == 1
    assert summe["nur_bis_ebene"] == abdeckung.TIEFE
    daten["abdeckung"] = summe
    assert not katalog.daten_fehler(katalog.katalog()[MODUL], daten)
    assert "3 von 4 Punkten gezählt" in dienst.quittung(daten)
    assert "Gezählt wird nur für Ebene 1 bis 2." in dienst.quittung(daten)
    # Reicht der Abgleich nicht tiefer als die Zählung, steht der Satz nicht da.
    flach = [zl for zl in zeilen if zl["ebene"] <= abdeckung.TIEFE]
    assert "nur_bis_ebene" not in dienst._abdeckung_eintragen(z, flach)


def test_die_liste_zusammen_mit_der_abdeckung(monkeypatch):
    """Der ganze Weg durch den Dienst: Baumliste und Zählung nebeneinander."""
    _server_kennt_die_liste()
    aufrufe: list[str] = []

    async def server(tool, args, **kw):
        aufrufe.append(tool)
        if tool == NAME:
            return _liste(_LISTE)
        return McpAntwort("ok", strukturiert={"results": [
            {"id": q["id"], "total": 0 if q["id"] == "k2" else 50, "top": []}
            for q in args["queries"]], "missing": []})

    monkeypatch.setattr(client, "call_mcp_tool_antwort", server)
    erg = asyncio.run(asynchron(MODUL, {"sammlung": OPTIK, "abdeckung": True}, Umgebung(
        teile=_teile(_ENTWURF), verfuegbar=frozenset({BROWSE, abdeckung.WERKZEUG}))))
    assert sorted(aufrufe) == sorted([NAME, abdeckung.WERKZEUG])
    daten = erg.block.daten
    assert not katalog.daten_fehler(katalog.katalog()[MODUL], daten)
    assert daten["abdeckung"] == {"gezaehlt": 4, "luecken": 1, "ungezaehlt": 0, "nur_bis_ebene": 2,
                                  "luecke_bis": 2, "filter_unaufgeloest": False}
    assert {z["id"] for z in daten["zeilen"] if "abdeckung" in z} == {"k1", "k1-1", "k2", "k2-1"}
    assert "4 von 4 Punkten gezählt" in erg.text and "nur für Ebene 1 bis 2" in erg.text
    assert "- Quantenoptik (0 Treffer in WLO)" in erg.block.text


def test_die_textfassung_trennt_neu_und_nicht_gefunden():
    """Zweites Review SW-4, Befund 3: Ein Widget ohne das Modul zeigte nicht gelesene Punkte
    sonst als neu."""
    daten = {"sammlung": {"titel": "Physik"}, "unvollstaendig": True, "gekuerzt": True,
             "zahlen": {"vorhanden": 0, "aehnlich": 0, "neu": 2, "nur_in_wlo": 0},
             "zeilen": [{"titel": "Optik", "ebene": 1, "art": "neu"},
                        {"titel": "Spiegel", "ebene": 2, "art": "neu", "ungewiss": True}]}
    text = dienst.textfassung(daten)
    assert "Neu:\n- Optik\n\nNicht gefunden (nicht sicher neu):\n- Spiegel" in text
    assert "Die Sammlung wurde nicht vollständig gelesen." in text
    alt = dienst.textfassung({**daten, "unvollstaendig": False})
    assert "Die Sammlung ist größer als gezeigt." in alt
    ohne = dienst.textfassung({**daten, "zeilen": daten["zeilen"][:1]})
    assert "Nicht gefunden" not in ohne and "vollständig" not in ohne


def test_die_textfassung_nennt_den_punkt_einer_luecke_auch_mit_tiefen_zeilen_dazwischen():
    daten = {"sammlung": {"titel": "Physik"},
             "zahlen": {"vorhanden": 0, "aehnlich": 0, "neu": 5, "nur_in_wlo": 0},
             "zeilen": [{"titel": "Optik [1]", "ebene": 1, "art": "neu"},
                        {"titel": "Linsen", "ebene": 2, "art": "neu"},
                        {"titel": "Sammellinsen", "ebene": 3, "art": "neu"},
                        {"titel": "Brennweite", "ebene": 4, "art": "neu"},
                        {"titel": "Spiegel", "ebene": 2, "art": "neu",
                         "abdeckung": {"total": 1, "luecke": True}}],
             "abdeckung": {"gezaehlt": 1}}
    assert "- Optik &#91;1&#93; › Spiegel (1 Treffer in WLO)" in dienst.textfassung(daten)
