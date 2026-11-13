"""Paket U4 (Plan 2026-11-08): der Strukturentwurf gegen eine WLO-Sammlung.

- Rein (``domain/strukturabgleich``): normalisieren, gleich → ``vorhanden``, Jaccard ≥ 0,5 →
  ``aehnlich``, sonst ``neu``; jede Sammlung höchstens einmal; Ebene 2 unter der zugeordneten
  Sammlung; der Rest ``nur_in_wlo``; Inhaltszahlen.
- Dienst ``strukturabgleich``: Entwurf aus dem Vorgang (sonst der gemerkte), Sammlung über
  ``browse_collection_tree`` ohne Cache; die KI bekommt nur Zahlen.
- Modul im Katalog: nachgeladen, mit Dienst, liest ``draft``.
"""

from __future__ import annotations

import asyncio

import pytest

from boerdi.domain import strukturabgleich as sa
from boerdi.services.mcp import client
from boerdi.services.mcp.client import McpAntwort
from boerdi.ui_module import katalog
from boerdi.ui_module.aufruf import Umgebung, asynchron

MODUL = "ui_strukturabgleich"
SAMMLUNG = "5e40e372-735c-4b17-bbf7-e827a5702b57"

_ENTWURF = {"titel": "Optik", "quelle": "ki", "knoten": [
    {"id": "k1", "titel": "Licht und Schatten", "kinder": [
        {"id": "k1-1", "titel": "Schattenbildung"}, {"id": "k1-2", "titel": "Farben"}]},
    {"id": "k2", "titel": "Linsen", "kinder": [{"id": "k2-1", "titel": "Brennweite"}]},
    {"id": "k3", "titel": "Spiegel und Reflexion"},
]}
_BAUM = {"parent": SAMMLUNG,         # Review U4, Befund 1: die Kennung als Text (MCP)
         "results": [
             {"nodeId": "a1", "title": "Licht & Schatten", "fileCount": 42, "children": [
                 {"nodeId": "a11", "title": "Schatten und Halbschatten", "contentsCount": 7},
                 {"nodeId": "a12", "title": "Farbenlehre"}]},
             {"nodeId": "a2", "title": "Reflexion am Spiegel", "fileCount": 5},
             {"nodeId": "a3", "title": "Mechanik", "fileCount": 120, "url": "javascript:x"},
             {"title": "ohne nodeId"}],
         "truncated": False}


def test_normalisiert_und_aehnlichkeit():
    assert sa.normalisiert("Über die Licht- und Schattenbildung!") == (
        "ueber", "licht", "schattenbildung")
    # Review U4, Befund 5: Umlaute gefaltet, „für“ ist ein Füllwort
    assert sa.normalisiert("Mathematik für Anfänger") == sa.normalisiert(
        "Mathematik fuer Anfaenger") == ("mathematik", "anfaenger")
    assert sa.normalisiert("Ørsted") == ("orsted",)
    assert sa.normalisiert(None) == ()
    assert sa.aehnlichkeit(("a", "b"), ("b", "c")) == pytest.approx(1 / 3)
    assert sa.aehnlichkeit((), ("a",)) == 0.0


def test_der_abgleich():
    erg = sa.abgleichen(_ENTWURF, sa.wlo_aus(_BAUM))
    art = {z["id"]: z["art"] for z in erg["zeilen"]}
    assert art == {"k1": "vorhanden", "k1-1": "neu", "k1-2": "neu", "k2": "neu",
                   "k2-1": "neu", "k3": "aehnlich"}
    k1 = next(z for z in erg["zeilen"] if z["id"] == "k1")
    assert k1["wlo"] == {"nodeId": "a1", "titel": "Licht & Schatten", "anzahl": 42}
    nur = {w["nodeId"] for w in erg["nur_in_wlo"]}
    assert nur == {"a11", "a12", "a3"}
    mechanik = next(w for w in erg["nur_in_wlo"] if w["nodeId"] == "a3")
    assert "url" not in mechanik and mechanik["anzahl"] == 120
    assert erg["zahlen"] == {"vorhanden": 1, "aehnlich": 1, "neu": 4, "nur_in_wlo": 3}
    # Kinder einer zugeordneten Sammlung stehen mit ihrer Elternsammlung da
    farben = next(w for w in erg["nur_in_wlo"] if w["nodeId"] == "a12")
    assert farben["eltern_titel"] == "Licht & Schatten" and farben["ebene"] == 2


def test_ebene_2_nur_unter_der_zugeordneten_sammlung_und_jede_sammlung_einmal():
    entwurf = {"knoten": [
        {"id": "a", "titel": "Licht", "kinder": [{"id": "a1", "titel": "Farben"}]},
        {"id": "b", "titel": "Licht"},
        {"id": "c", "titel": "Neu", "kinder": [{"id": "c1", "titel": "Farben"}]}]}
    baum = {"results": [{"nodeId": "L", "title": "Licht", "children": [
        {"nodeId": "F", "title": "Farben"}]}, {"nodeId": "M", "title": "Mechanik", "children": [
            {"nodeId": "F2", "title": "Farben"}]}]}
    art = {z["id"]: (z["art"], z.get("wlo", {}).get("nodeId"))
           for z in sa.abgleichen(entwurf, sa.wlo_aus(baum))["zeilen"]}
    assert art["a"] == ("vorhanden", "L") and art["a1"] == ("vorhanden", "F")
    assert art["b"] == ("neu", None)                            # „Licht“ ist schon vergeben
    # ohne zugeordneten Elternpunkt: gegen alle Sammlungen der Ebene 2
    assert art["c1"] == ("vorhanden", "F2")


def test_kaputte_eingaben_werfen_nicht():
    assert sa.abgleichen(None, [])["zeilen"] == []
    assert sa.abgleichen({"knoten": ["x", {"titel": ""}]}, sa.wlo_aus({"results": "x"})) == {
        "zeilen": [], "nur_in_wlo": [], "zahlen": {"vorhanden": 0, "aehnlich": 0, "neu": 0,
                                                    "nur_in_wlo": 0}, "gekuerzt": False}
    assert sa.wlo_aus({"results": [{"nodeId": "a", "title": "A", "children": "x",
                                    "fileCount": True}]}) == [
        {"nodeId": "a", "titel": "A", "ebene": 1, "eltern": None, "eltern_titel": None,
         "anzahl": None, "mehr": False}]


# ── Dienst ───────────────────────────────────────────────────────────────────────────────────

class _Server:
    def __init__(self, antwort):
        self.aufrufe: list = []
        self.antwort = antwort

    async def __call__(self, tool, args, **kw):
        self.aufrufe.append((tool, args, kw))
        return self.antwort


def _teile(wert):
    async def lader(name):
        return wert if name == "draft" else None
    return lader


def test_das_modul_steht_im_katalog():
    m = katalog.katalog()[MODUL]
    assert m["laden"] == "bei_bedarf" and m["dienst"]["name"] == "strukturabgleich"
    assert m["vorgang"] == {"liest": ["draft"]} and m["art"] == "anzeigen"
    assert set(m["dienst"]["parameter"]["properties"]) == {"sammlung", "titel", "abdeckung"}
    assert m["dienst"]["braucht"] == ["browse_collection_tree"]


def test_der_dienst_gleicht_ab_und_sagt_der_ki_nur_zahlen(monkeypatch):
    server = _Server(McpAntwort("{}", strukturiert=_BAUM))
    monkeypatch.setattr(client, "call_mcp_tool_antwort", server)
    erg = asyncio.run(asynchron(MODUL, {"sammlung": SAMMLUNG}, Umgebung(teile=_teile(_ENTWURF))))
    [(tool, args, kw)] = server.aufrufe
    assert tool == "browse_collection_tree" and kw == {"use_cache": False}
    assert args == {"nodeId": SAMMLUNG, "depth": 2, "includeContentCounts": True,
                    "maxResults": sa.WLO_OBEN, "outputFormat": "json"}
    assert erg.block is not None and erg.outcome.status == "success"
    daten = erg.block.daten
    assert daten["sammlung"]["nodeId"] == SAMMLUNG and daten["sammlung"]["titel"] == ""
    assert daten["zahlen"]["vorhanden"] == 1 and daten["gekuerzt"] is False
    # Titel nur im Modul, nicht im Text an die KI
    assert "Licht" not in erg.text and "1 Punkte vorhanden" in erg.text
    assert "Linsen" in erg.block.text                       # neue Punkte in der Textfassung


def test_ohne_entwurf_oder_ohne_sammlung(monkeypatch):
    monkeypatch.setattr(client, "call_mcp_tool_antwort", _Server(McpAntwort("{}",
                                                                            strukturiert=_BAUM)))
    erg = asyncio.run(asynchron(MODUL, {"sammlung": SAMMLUNG}, Umgebung(teile=_teile(None))))
    assert erg.block is None and erg.outcome.error == "kein_entwurf"
    # der gemerkte Entwurf als Rückfall
    erg = asyncio.run(asynchron(MODUL, {"sammlung": SAMMLUNG},
                                Umgebung(teile=_teile(None), vorlage=_ENTWURF)))
    assert erg.block is not None
    monkeypatch.setattr(client, "call_mcp_tool_antwort",
                        _Server(McpAntwort("MCP error [not_found]: weg", "tool", "not_found")))
    erg = asyncio.run(asynchron(MODUL, {"sammlung": SAMMLUNG}, Umgebung(teile=_teile(_ENTWURF))))
    assert erg.block is None and erg.outcome.error == "sammlung"


def test_der_dienst_prueft_die_argumente(monkeypatch):
    monkeypatch.setattr(client, "call_mcp_tool_antwort", _Server(McpAntwort("{}")))
    for args in ({}, {"sammlung": "keine-uuid"}, {"sammlung": SAMMLUNG, "fremd": 1}):
        erg = asyncio.run(asynchron(MODUL, args, Umgebung(teile=_teile(_ENTWURF))))
        assert erg.block is None and erg.outcome.error == "argumente", args


def test_text_statt_struktur_und_gekuerzt(monkeypatch):
    import json

    gross = {"parent": {"title": "P"}, "truncated": True,
             "results": [{"nodeId": f"n{i}", "title": f"T{i}", "children": [
                 {"nodeId": f"n{i}-{j}", "title": f"U{i}-{j}"} for j in range(10)]}
                 for i in range(15)]}
    monkeypatch.setattr(client, "call_mcp_tool_antwort", _Server(McpAntwort(json.dumps(gross))))
    erg = asyncio.run(asynchron(MODUL, {"sammlung": SAMMLUNG}, Umgebung(teile=_teile(_ENTWURF))))
    assert erg.block is not None and erg.block.daten["gekuerzt"] is True
    assert len(erg.block.daten["nur_in_wlo"]) == 100


# ── Review U4 ─────────────────────────────────────────────────────────────────────────────────

def test_review_ein_ungebundener_punkt_schnappt_keine_kinder_weg():
    entwurf = {"knoten": [{"id": "a", "titel": "Akustik", "kinder": [{"id": "a1",
        "titel": "Linsen"}]},
                          {"id": "o", "titel": "Optik", "kinder": [{"id": "o1",
                              "titel": "Linsen"}]}]}
    baum = {"results": [{"nodeId": "O", "title": "Optik", "children": [
        {"nodeId": "L", "title": "Linsen"}]}]}
    art = {z["id"]: (z["art"], z.get("wlo", {}).get("nodeId"))
           for z in sa.abgleichen(entwurf, sa.wlo_aus(baum))["zeilen"]}
    assert art["o1"] == ("vorhanden", "L") and art["a1"] == ("neu", None)


def test_review_gekuerzt_heisst_nicht_gefunden():
    baum = {"truncated": True, "results": [
        {"nodeId": "L", "title": "Licht", "hasMoreChildren": True, "children": [
            {"nodeId": "F", "title": "Farben"}]},
        {"nodeId": "M", "title": "Mechanik"}]}
    entwurf = {"knoten": [{"id": "l", "titel": "Licht", "kinder": [{"id": "l1",
        "titel": "Linsen"}]},
                          {"id": "m", "titel": "Mechanik", "kinder": [{"id": "m1",
                              "titel": "Kraft"}]},
                          {"id": "w", "titel": "Waerme"}]}
    erg = sa.abgleichen(entwurf, sa.wlo_aus(baum), gekuerzt=True)
    ungewiss = {z["id"]: z.get("ungewiss", False) for z in erg["zeilen"] if z["art"] == "neu"}
    assert ungewiss == {"l1": True, "m1": False, "w": True} and erg["gekuerzt"] is True


def test_review_der_dienst_nennt_die_kuerzung_und_nimmt_den_gelesenen_parent(monkeypatch):
    baum = {**_BAUM, "parent": "11111111-1111-1111-1111-111111111111", "truncated": True}
    monkeypatch.setattr(client, "call_mcp_tool_antwort", _Server(McpAntwort("{}",
                                                                            strukturiert=baum)))
    erg = asyncio.run(asynchron(MODUL, {"sammlung": SAMMLUNG, "titel": "Physik"},
                                Umgebung(teile=_teile(_ENTWURF))))
    assert erg.block.daten["sammlung"] == {
        "nodeId": "11111111-1111-1111-1111-111111111111", "titel": "",
        **({"url": erg.block.daten["sammlung"]["url"]} if "url" in erg.block.daten["sammlung"]
           else {})}
    assert "größer als gezeigt" in erg.text and erg.block.daten["gekuerzt"] is True


def test_review_titel_aus_dem_argument_und_entschaerft(monkeypatch):
    monkeypatch.setattr(client, "call_mcp_tool_antwort", _Server(McpAntwort("{}",
                                                                            strukturiert=_BAUM)))
    entwurf = {"knoten": [{"id": "x", "titel": "[Klick](https://boese.de) **fett**"}]}
    erg = asyncio.run(asynchron(MODUL, {"sammlung": SAMMLUNG, "titel": "Physik"},
                                Umgebung(teile=_teile(entwurf))))
    assert erg.block.daten["sammlung"]["titel"] == "Physik"
    assert "](https://boese.de)" not in erg.block.text and "&#91;Klick&#93;" in erg.block.text


def test_review_zeitueberschreitung_und_vorrang_des_gemerkten(monkeypatch):
    monkeypatch.setattr(client, "call_mcp_tool_antwort",
                        _Server(McpAntwort("MCP error: keine Antwort", "timeout")))
    erg = asyncio.run(asynchron(MODUL, {"sammlung": SAMMLUNG}, Umgebung(teile=_teile(_ENTWURF))))
    assert erg.outcome.status == "timeout" and erg.outcome.error == "timeout"
    monkeypatch.setattr(client, "call_mcp_tool_antwort", _Server(McpAntwort("{}",
                                                                            strukturiert=_BAUM)))
    neu = {"titel": "Neu", "knoten": [{"id": "n", "titel": "Nur gemerkt"}]}
    erg = asyncio.run(asynchron(MODUL, {"sammlung": SAMMLUNG},
                                Umgebung(teile=_teile(_ENTWURF), vorlage=neu)))
    assert [z["id"] for z in erg.block.daten["zeilen"]] == ["n"]


def test_review_ohne_browse_wird_das_modul_nicht_angeboten():
    from boerdi.ui_module.werkzeuge import modul_werkzeuge

    def namen(verfuegbar):
        return {w["function"]["name"] for w in modul_werkzeuge([MODUL], verfuegbar, fuer="agent")}

    # Review U5, Befund 5: die Zählung ist kein Muss — der Abgleich bleibt ohne sie angeboten
    assert namen({"browse_collection_tree"}) == {MODUL}
    assert namen(set()) == set() and namen(None) == set()


# ── Paket U5: Abdeckung ───────────────────────────────────────────────────────────────────────

class _ZweiServer:
    """browse_collection_tree und count_wlo_content_matches."""

    def __init__(self, zaehlung):
        self.aufrufe: list = []
        self.zaehlung = zaehlung

    async def __call__(self, tool, args, **kw):
        self.aufrufe.append(tool)
        if tool == "browse_collection_tree":
            return McpAntwort("{}", strukturiert=_BAUM)
        return self.zaehlung(args) if callable(self.zaehlung) else self.zaehlung


_MIT_ZAEHLUNG = frozenset({"browse_collection_tree", "count_wlo_content_matches"})


def test_u5_abdeckung_je_punkt_und_luecken(monkeypatch):
    def zaehlung(args):
        werte = {"k1": 80, "k1-1": 1, "k2": 0}
        return McpAntwort("ok", strukturiert={"results": [
            {"id": q["id"], "total": werte[q["id"]],
             "top": [{"nodeId": "t", "title": "Treffer", "url": "https://x.de/t"}]}
            for q in args["queries"] if q["id"] in werte], "missing": [
            {"part": q["id"], "code": "timeout"} for q in args["queries"] if q["id"] not in werte]})

    server = _ZweiServer(zaehlung)
    monkeypatch.setattr(client, "call_mcp_tool_antwort", server)
    erg = asyncio.run(asynchron(MODUL, {"sammlung": SAMMLUNG, "abdeckung": True},
                                Umgebung(teile=_teile(_ENTWURF), verfuegbar=_MIT_ZAEHLUNG)))
    assert sorted(server.aufrufe) == ["browse_collection_tree", "count_wlo_content_matches"]
    zeilen = {z["id"]: z for z in erg.block.daten["zeilen"]}
    assert zeilen["k1"]["abdeckung"]["luecke"] is False
    assert zeilen["k1-1"]["abdeckung"] == {"total": 1, "luecke": True, "top": [
        {"nodeId": "t", "titel": "Treffer", "url": "https://x.de/t"}]}
    assert zeilen["k3"]["abdeckung_fehlt"] == "timeout"
    assert erg.block.daten["abdeckung"] == {"gezaehlt": 3, "luecken": 2, "ungezaehlt": 3,
                                            "luecke_bis": 2, "filter_unaufgeloest": False}
    assert "2 davon Lücken" in erg.text and "Lücken (kaum Material" in erg.block.text


def test_u5_ohne_abdeckung_wird_nicht_gezaehlt(monkeypatch):
    server = _ZweiServer(McpAntwort("ok"))
    monkeypatch.setattr(client, "call_mcp_tool_antwort", server)
    erg = asyncio.run(asynchron(MODUL, {"sammlung": SAMMLUNG}, Umgebung(teile=_teile(_ENTWURF))))
    assert server.aufrufe == ["browse_collection_tree"] and "abdeckung" not in erg.block.daten


def test_u5_filter_unbekannt_und_zaehlung_ohne_antwort(monkeypatch):
    def unbekannt(args):
        return McpAntwort("ok", strukturiert={"results": [], "missing": [
            {"part": q["id"], "code": "unresolved_filter"} for q in args["queries"]]})

    monkeypatch.setattr(client, "call_mcp_tool_antwort", _ZweiServer(unbekannt))
    erg = asyncio.run(asynchron(MODUL, {"sammlung": SAMMLUNG, "abdeckung": True},
                                Umgebung(teile=_teile({**_ENTWURF, "fach": "Quidditch"}),
                                         verfuegbar=_MIT_ZAEHLUNG)))
    assert erg.block.daten["abdeckung"]["filter_unaufgeloest"] is True
    assert "kennt WLO nicht" in erg.text
    monkeypatch.setattr(client, "call_mcp_tool_antwort",
                        _ZweiServer(McpAntwort("MCP error: keine Antwort", "timeout")))
    erg = asyncio.run(asynchron(MODUL, {"sammlung": SAMMLUNG, "abdeckung": True},
                                Umgebung(teile=_teile(_ENTWURF), verfuegbar=_MIT_ZAEHLUNG)))
    assert erg.block is not None                          # der Abgleich steht trotzdem
    # Review U5, Befund 1: nichts gezählt heißt nicht „keine Lücken“
    assert erg.block.daten["abdeckung"]["gezaehlt"] == 0
    assert "kam nicht zustande" in erg.text and "Lücken (höchstens" not in erg.text
    assert "ließen sich nicht zählen" in erg.block.text
    assert all(z["abdeckung_fehlt"] == "keine_antwort" for z in erg.block.daten["zeilen"])


# ── Review U5 ─────────────────────────────────────────────────────────────────────────────────

def _zaehle(werte):
    def zaehlung(args):
        return McpAntwort("ok", strukturiert={"results": [
            {"id": q["id"], "total": werte.get(q["id"], 50), "top": []}
            for q in args["queries"]], "missing": []})
    return zaehlung


def test_review_u5_ohne_angebotene_zaehlung_kein_aufruf(monkeypatch):
    server = _ZweiServer(_zaehle({}))
    monkeypatch.setattr(client, "call_mcp_tool_antwort", server)
    erg = asyncio.run(asynchron(MODUL, {"sammlung": SAMMLUNG, "abdeckung": True},
                                Umgebung(teile=_teile(_ENTWURF),
                                         verfuegbar=frozenset({"browse_collection_tree"}))))
    assert server.aufrufe == ["browse_collection_tree"]
    assert erg.block.daten["abdeckung"]["gesperrt"] is True
    assert {z["abdeckung_fehlt"] for z in erg.block.daten["zeilen"]} == {"gesperrt"}
    assert "in diesem Zug nicht angeboten" in erg.text


def test_review_u5_vorhanden_mit_inhalten_ist_keine_luecke(monkeypatch):
    monkeypatch.setattr(client, "call_mcp_tool_antwort", _ZweiServer(_zaehle({"k1": 0})))
    erg = asyncio.run(asynchron(MODUL, {"sammlung": SAMMLUNG, "abdeckung": True},
                                Umgebung(teile=_teile(_ENTWURF), verfuegbar=_MIT_ZAEHLUNG)))
    k1 = next(z for z in erg.block.daten["zeilen"] if z["id"] == "k1")
    assert k1["wlo"]["anzahl"] == 42 and k1["abdeckung"] == {"total": 0, "luecke": False}


def test_review_u5_doppelte_kennung_zaehlt_nur_die_erste_zeile(monkeypatch):
    monkeypatch.setattr(client, "call_mcp_tool_antwort", _ZweiServer(_zaehle({"d": 1})))
    doppelt = {"knoten": [{"id": "d", "titel": "Alpha"}, {"id": "d", "titel": "Beta"}]}
    erg = asyncio.run(asynchron(MODUL, {"sammlung": SAMMLUNG, "abdeckung": True},
                                Umgebung(teile=_teile(doppelt), verfuegbar=_MIT_ZAEHLUNG)))
    alpha, beta = erg.block.daten["zeilen"]
    assert alpha["abdeckung"]["total"] == 1 and beta["abdeckung_fehlt"] == "nicht_gezaehlt"
    assert erg.block.daten["abdeckung"]["gezaehlt"] == 1


def test_review_u5_die_frist_laesst_den_abgleich_stehen(monkeypatch):
    class _Langsam(_ZweiServer):
        async def __call__(self, tool, args, **kw):
            if tool == "count_wlo_content_matches":
                await asyncio.sleep(5)
            return await super().__call__(tool, args, **kw)

    monkeypatch.setattr(client, "call_mcp_tool_antwort", _Langsam(_zaehle({})))

    async def lauf():
        ende = asyncio.get_running_loop().time() + 15.5          # RESERVE_S = 15 → 0,5 s
        return await asynchron(MODUL, {"sammlung": SAMMLUNG, "abdeckung": True},
                               Umgebung(teile=_teile(_ENTWURF), verfuegbar=_MIT_ZAEHLUNG,
                                        frist_ende=ende))

    erg = asyncio.run(lauf())
    assert erg.block is not None
    assert {z["abdeckung_fehlt"] for z in erg.block.daten["zeilen"]} == {"frist"}


def test_review_u5_ebene_1_zuerst_beim_deckel():
    from boerdi.services import abdeckung

    gross = {"knoten": [{"id": f"o{i}", "titel": f"Oben {i}", "kinder": [
        {"id": f"o{i}-{j}", "titel": f"Unten {i}.{j}"} for j in range(5)]} for i in range(20)]}
    punkte = abdeckung.punkte_aus_entwurf(gross)
    assert len(punkte) == abdeckung.HOECHSTENS
    assert {p.id for p in punkte if p.ebene == 1} == {f"o{i}" for i in range(20)}


# ── Gesamt-Review U3/M1/U4/U5 ────────────────────────────────────────────────────────────────

def test_gesamt_keine_verwaiste_zaehlung(monkeypatch):
    abgebrochen: list = []

    class _Haengt(_ZweiServer):
        async def __call__(self, tool, args, **kw):
            if tool == "count_wlo_content_matches":
                try:
                    await asyncio.sleep(30)
                except asyncio.CancelledError:
                    abgebrochen.append(tool)
                    raise
            await asyncio.sleep(0.05)                 # die Zählung läuft schon
            return McpAntwort("MCP error [not_found]: weg", "tool", "not_found")

    monkeypatch.setattr(client, "call_mcp_tool_antwort", _Haengt(None))

    async def lauf():
        erg = await asynchron(MODUL, {"sammlung": SAMMLUNG, "abdeckung": True},
                              Umgebung(teile=_teile(_ENTWURF), verfuegbar=_MIT_ZAEHLUNG))
        await asyncio.sleep(0)
        return erg

    erg = asyncio.run(lauf())
    assert erg.block is None and abgebrochen == ["count_wlo_content_matches"]


def test_gesamt_eine_kaputte_zaehlantwort_kippt_den_abgleich_nicht(monkeypatch):
    kaputt = McpAntwort("ok", strukturiert={
        "results": [{"id": ["x"], "total": 1}, {"id": "k1", "total": 2, "fuzzyFilters": [{}]},
                    "kein objekt"],
        "missing": [{"part": ["k2"], "code": "timeout"}, None]})
    monkeypatch.setattr(client, "call_mcp_tool_antwort", _ZweiServer(kaputt))
    erg = asyncio.run(asynchron(MODUL, {"sammlung": SAMMLUNG, "abdeckung": True},
                                Umgebung(teile=_teile(_ENTWURF), verfuegbar=_MIT_ZAEHLUNG)))
    assert erg.block is not None
    k1 = next(z for z in erg.block.daten["zeilen"] if z["id"] == "k1")
    assert k1["abdeckung"]["total"] == 2 and "geraten" not in k1["abdeckung"]


def test_gesamt_persoenliches_geht_nicht_in_die_suche(monkeypatch):
    from boerdi.services import abdeckung

    gefragt: list = []

    async def mcp(tool, args, **_k):
        gefragt.extend(q["query"] for q in args["queries"])
        return McpAntwort("ok", strukturiert={"results": [
            {"id": q["id"], "total": 9, "top": []} for q in args["queries"]], "missing": []})

    monkeypatch.setattr(client, "call_mcp_tool_antwort", mcp)
    entwurf = {"knoten": [{"id": "a", "titel": "Optik"},
                          {"id": "b", "titel": "Referat max.muster@schule.de"},
                          {"id": "c", "titel": "Eltern anrufen 0171 2345678"},
                          {"id": "d", "titel": "Mein Passwort ist geheim"}]}
    erg = asyncio.run(abdeckung.fuer_entwurf(entwurf))
    assert gefragt == ["Optik"]
    fehlt = {z["id"]: z.get("fehlt") for z in erg["punkte"]}
    assert fehlt == {"a": None, "b": "persoenlich", "c": "persoenlich", "d": "persoenlich"}
    assert not abdeckung.persoenlich("Optik Klasse 8 Linsen 2024")



def test_r3c_die_textfassung_nennt_den_punkt_einer_luecke():
    """Paket R3-c: wie das Modul — ein Unterpunkt einer Lücke steht mit seinem Punkt."""
    from boerdi.ui_module import dienst_strukturabgleich as d

    daten = {"sammlung": {"titel": "Physik"},
             "zahlen": {"vorhanden": 0, "aehnlich": 0, "neu": 2, "nur_in_wlo": 0},
             "zeilen": [{"titel": "Optik", "ebene": 1, "art": "neu",
                         "abdeckung": {"total": 90, "luecke": False}},
                        {"titel": "Linsen", "ebene": 2, "art": "neu",
                         "abdeckung": {"total": 0, "luecke": True}}],
             "abdeckung": {"gezaehlt": 2}}
    assert "- Optik › Linsen (0 Treffer in WLO)" in d.textfassung(daten)
