"""Plan 2026-11-16, Review TG-3d–f (samt R3): Behebung. Entscheide im Plan unter „Review TG-3d–f“.

- MINOR 1: Namen einer Auswahl laufen durch die Krisen- und Drohungsmuster — als Hinweis ohne
  Sperre (Upload bleibt, Hilfsnummern an der Antwort, Grund ohne Namen im Protokoll).
- MINOR 2: der Leser schreibt fest, bevor er das MCP fragt; WLO-Volltexte parallel mit Frist.
- MINOR 3: ohne Volltext fällt nichts still weg.
- MINOR 4: der aktuelle Stapel vor ``frueher``.
- MINOR 6: ``quality_logs`` ohne Namen.
- MINOR 7: ``draft`` an kuratierende Werkzeuge ohne ``inhalte``.
- MINOR 8: node_ids eines Entwurfs nur aus der gebundenen Ablage.
Die Postgres-Fälle (M1, MINOR 5, gleichzeitiges Speichern) stehen in
``test_review_tg3def_pg.py``.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from boerdi.api.schemas import ChatRequest, ChatResponse, ClassificationResult, SafetyDecision
from boerdi.domain.dokument_gliederung import gliederung
from boerdi.graph import build
from boerdi.graph import state as state_mod
from boerdi.graph.nodes import assess as assess_mod
from boerdi.graph.nodes import preflight as pf_mod
from boerdi.services.dokumente import stand
from boerdi.services.dokumente import strukturdokument as leser
from boerdi.services.dokumente import strukturdokument_teil as sd
from boerdi.services.safety.service import NAMEN_DROHUNG, NAMEN_KRISE, namen_pruefung
from boerdi.ui_module.namen import UPLOAD

_KNOTEN = "33333333-3333-3333-3333-333333333333"
_KNOTEN_2 = "44444444-4444-4444-4444-444444444444"


def _upload(ordner: str = "Ethik", datei: str = "a.pdf") -> dict:
    return {"block_id": "b0000001", "modul": UPLOAD, "frage": "Ordner erfassen", "labels": [],
            "daten": {"aktion": "erfasst",
                      "struktur": {"name": ordner, "dateien": 1, "alle_dateien": 1, "kinder": [],
                                   "dateiliste": [{"i": 0, "name": datei, "endung": "pdf",
                                                   "groesse": 1, "rolle": "inhalt"}]},
                      "zahlen": {"ordner": 1, "dateien": 1, "inhalte": 1, "ignoriert": 0,
                                 "strukturdokumente": 0, "bytes": 1},
                      "strukturdokument": None, "warnungen": []}}


def _ctx(message: str, geprueft: dict | None) -> state_mod.TurnContext:
    ctx = state_mod.TurnContext(req=ChatRequest(session_id="bb-1", message=message))
    ctx.session_state = {}
    ctx.client_ip = "1.2.3.4"
    ctx.ui_antwort = geprueft
    return ctx


# ── MINOR 1: Hinweis statt Sperre ────────────────────────────────────────────────────────────────

def test_m1_namen_pruefung_findet_krise_und_drohung():
    assert namen_pruefung("Ethik\nSuizid-Prävention.pdf") == NAMEN_KRISE
    assert namen_pruefung("ich will mich umbringen") == NAMEN_KRISE
    assert namen_pruefung("Physik\nHebel.pdf") is None
    assert namen_pruefung("") is None


def _assess(monkeypatch, message: str, geprueft: dict):
    async def safety(text, signals, usage_acc=None, **_k):
        return SafetyDecision(risk_level="low")

    async def classify(*_a, **_k):
        return ClassificationResult()

    async def keine(_sid):
        return []

    monkeypatch.setattr(assess_mod, "assess_safety", safety)
    monkeypatch.setattr(assess_mod, "classify_input", classify)
    return asyncio.run(assess_mod.assess(_ctx(message, geprueft), keine))


def test_m1_suizid_praevention_als_datei_upload_bleibt_hinweis_kommt(monkeypatch):
    out = _assess(monkeypatch, "Ordner „Ethik“ erfasst: 1 Datei.",
                  _upload(datei="Suizid-Prävention.pdf"))
    assert out.safety.risk_level == "low"                  # keine Sperre: persist speichert
    assert NAMEN_KRISE in out.safety.reasons and out.krisenhilfe is True


def test_m1_ein_krisensatz_als_ordnername_upload_bleibt_hinweis_kommt(monkeypatch):
    out = _assess(monkeypatch, "Ordner erfasst.", _upload(ordner="ich will mich umbringen"))
    assert out.safety.risk_level == "low" and out.krisenhilfe is True


def test_m1_ein_krisensatz_in_der_nachricht_sperrt_wie_bisher(monkeypatch):
    out = _assess(monkeypatch, "ich will mich umbringen", _upload())
    assert out.safety.risk_level == "high" and out.safety.enforced_pattern == "M01"
    assert out.krisenhilfe is False                        # M01 antwortet selbst


def test_m1_die_antwort_traegt_die_hilfsnummern_angehaengt():
    antwort = ChatResponse(session_id="bb-1", content="Danke, ich sehe deinen Ordner.")
    state = {"krisenhilfe": True, "response": antwort, "early_response": None,
             "req": ChatRequest(session_id="bb-1", message="x")}
    build._krisenhilfe(state)
    assert antwort.content.startswith("Danke, ich sehe deinen Ordner.")
    assert "0800 111 0 111" in antwort.content
    build._krisenhilfe(state)                              # nicht doppelt
    assert antwort.content.count("0800 111 0 111") == 1
    ohne = ChatResponse(session_id="bb-1", content="Hallo")
    build._krisenhilfe({"krisenhilfe": False, "response": ohne})
    assert ohne.content == "Hallo"


def test_m1_im_protokoll_steht_der_grund_ohne_namen(monkeypatch):
    """Ein Ablauf beantwortet die Auswahl in ``preflight`` — dort steht der Grund im Protokoll,
    ohne Datei- oder Ordnernamen, auch nicht aus der Blase."""
    from tests.test_preflight_node import _lauf_spione, _patch_db, _patch_handlers

    _patch_handlers(monkeypatch)
    log, _save = _patch_db(monkeypatch)
    _lauf_spione(monkeypatch)

    async def ok(*_a, **_k):
        from boerdi.services.rate_limits import RateVerdict

        return RateVerdict(allowed=True)

    async def safety(text, signals, usage_acc=None, **_k):
        return SafetyDecision(risk_level="low")

    monkeypatch.setattr(pf_mod, "check_rate_limit", ok)
    monkeypatch.setattr(pf_mod, "assess_safety", safety)
    ctx = _ctx("Ordner „Geheim-Ethik“ erfasst: 1 Datei.",
               _upload(ordner="Geheim-Ethik", datei="Suizid-Prävention.pdf"))
    out = asyncio.run(pf_mod.preflight(ctx, object()))
    assert out.early_response.content == "ABLAUF-WEITER" and out.krisenhilfe is True
    [aufruf] = log.calls
    protokoll, entscheid = aufruf["args"][2], aufruf["kwargs"]["decision"]
    assert NAMEN_KRISE in entscheid.reasons
    assert "Suizid" not in protokoll and "Geheim-Ethik" not in protokoll


def test_m1_drohung_in_namen_nur_als_grund(monkeypatch):
    """Eine Drohung als Ordnername: Grund im Protokoll, keine Sperre, keine Hilfsnummern."""
    assert namen_pruefung("ich werde euch alle erschiessen") == NAMEN_DROHUNG
    out = _assess(monkeypatch, "Ordner erfasst.", _upload(ordner="ich werde euch alle erschiessen"))
    assert out.safety.risk_level == "low" and NAMEN_DROHUNG in out.safety.reasons
    assert out.krisenhilfe is False


# ── MINOR 6: quality_logs ohne Namen ─────────────────────────────────────────────────────────────

def test_m6_qualitaetsprotokoll_ohne_namen(monkeypatch):
    from boerdi.obs import quality_events
    from boerdi.services import turn_quality

    gesehen: list[str] = []

    async def log_quality_event(session, sid, message, *_a, **_k):
        gesehen.append(message)

    monkeypatch.setattr(turn_quality, "qualitaetsprotokoll_an", lambda: True)
    monkeypatch.setattr(quality_events, "log_quality_event", log_quality_event)
    req = ChatRequest(session_id="bb-1", message="Ordner „Zeugnis_Müller“ erfasst: 1 Datei.")
    asyncio.run(turn_quality.log_turn_quality(None, req, {}, ui_antwort=_upload(
        ordner="Zeugnis_Müller")))
    asyncio.run(turn_quality.log_turn_quality(None, ChatRequest(session_id="bb-1",
                                                                message="„Zitat“ bleibt"), {}))
    assert gesehen == ["Ordner „…“ erfasst: 1 Datei.", "„Zitat“ bleibt"]


# ── MINOR 2/3: Lesen der Strukturdokumente ───────────────────────────────────────────────────────

class _S:
    def __init__(self, ereignisse: list[str]) -> None:
        self.ereignisse = ereignisse

    async def commit(self) -> None:
        self.ereignisse.append("commit")

    async def rollback(self) -> None:
        self.ereignisse.append("rollback")


def _zeile(kennung: str, name: str):
    md = "# A\nx\n# B\ny\n# C\nz"
    abschnitte, _ = gliederung(md)
    return SimpleNamespace(id=kennung, name=name, format="pdf", befund={}, markdown=md,
                           gliederung=[a.__dict__ for a in abschnitte])


def test_m2_festgeschrieben_vor_dem_mcp_parallel_hoechstens_drei(monkeypatch):
    ereignisse: list[str] = []
    gleichzeitig = {"jetzt": 0, "max": 0}

    async def alle_fuer_aufrufer(s, sid, aufrufer, *_rolle):  # Paket U: Rolle
        return [_zeile("u-1", "a.pdf")]

    async def beruehren(s, kennung, *, ttl_h):
        ereignisse.append("beruehren")

    async def volltext(node_id):
        ereignisse.append("mcp")
        gleichzeitig["jetzt"] += 1
        gleichzeitig["max"] = max(gleichzeitig["max"], gleichzeitig["jetzt"])
        await asyncio.sleep(0.01)
        gleichzeitig["jetzt"] -= 1
        return "# X\na\n# Y\nb\n# Z\nc", ""

    monkeypatch.setattr(leser.ablage, "alle_fuer_aufrufer", alle_fuer_aufrufer)
    monkeypatch.setattr(leser.ablage, "beruehren", beruehren)
    monkeypatch.setattr(leser, "volltext", volltext)
    knoten = [f"{n}{_KNOTEN[1:]}" for n in "56789"]
    eintraege = [sd.chatbot("u-1", "a.pdf"), *(sd.wlo(k, f"w{k[0]}.pdf") for k in knoten)]
    lesung = asyncio.run(leser.staende(eintraege, session=_S(ereignisse), session_id="s"))
    assert ereignisse.index("commit") < ereignisse.index("mcp")
    assert gleichzeitig["max"] <= leser.PARALLEL
    assert [d.name for d in lesung.staende] == ["a.pdf", *(f"w{k[0]}.pdf" for k in knoten)]


def test_m2_die_gesamtfrist_haelt_langsame_lesungen_an(monkeypatch):
    async def volltext(node_id):
        await asyncio.sleep(5)
        return "nie", ""

    monkeypatch.setattr(leser, "volltext", volltext)

    async def lauf():
        ende = asyncio.get_running_loop().time() + 0.05
        return await leser.staende([sd.wlo(_KNOTEN, "w.pdf")], session=_S([]), session_id="s",
                                   frist_ende=ende)

    lesung = asyncio.run(lauf())
    assert lesung.staende == [] and lesung.fehlend == [("w.pdf", "frist")]


def _gemischt(monkeypatch, *, mit_chatbot: bool):
    teil = sd.wert([*([sd.chatbot("u-1", "a.pdf")] if mit_chatbot else []),
                    sd.wlo(_KNOTEN, "Lehrplan „neu“.pdf")])

    async def teile(name):
        return teil if name == sd.TEIL else None

    async def alle_fuer_aufrufer(s, sid, aufrufer, *_rolle):  # Paket U: Rolle
        return [_zeile("u-1", "a.pdf")]

    async def beruehren(*_a, **_k):
        return None

    async def volltext(node_id):
        return None, "not_extracted"

    from boerdi.ui_module import dienst_upload

    monkeypatch.setattr(dienst_upload, "dokument_erlaubt", lambda: True)
    monkeypatch.setattr(leser.ablage, "alle_fuer_aufrufer", alle_fuer_aufrufer)
    monkeypatch.setattr(leser.ablage, "beruehren", beruehren)
    monkeypatch.setattr(leser, "volltext", volltext)
    return asyncio.run(stand.laden(_S([]), "s", teile))


def test_m3_gemischt_bleibt_das_lesbare_und_nennt_das_fehlende(monkeypatch):
    erg = _gemischt(monkeypatch, mit_chatbot=True)
    assert isinstance(erg, stand.DokumentStand) and erg.name == "a.pdf"
    assert erg.fehlend == (("Lehrplan „neu“.pdf", "not_extracted"),)


def test_m3_nur_wlo_ohne_volltext_ist_ein_eigener_fall(monkeypatch):
    erg = _gemischt(monkeypatch, mit_chatbot=False)
    assert isinstance(erg, stand.OhneVolltext)
    assert erg.fehlend == (("Lehrplan „neu“.pdf", "not_extracted"),)


def test_m3_der_dienst_sagt_es_der_ki(monkeypatch):
    from boerdi.ui_module import dienst as modul_dienst
    from boerdi.ui_module import katalog
    from boerdi.ui_module.aufruf import Umgebung

    manifest = katalog.katalog()["ui_strukturentwurf"]

    async def ohne():
        return stand.OhneVolltext((("Lehrplan „neu“.pdf", "not_extracted"),))

    erg = asyncio.run(modul_dienst.aufruf(manifest, {"thema": "Physik", "aus_dokument": True},
                                          Umgebung(dokument=ohne)))
    # Plan 2026-11-20 §8, E1: ``not_extracted`` ist endgültig — eigener Code, die Auswege im Satz
    assert erg.outcome.error == "volltext_endgueltig"
    assert "„Lehrplan neu.pdf“" in erg.text and "keinen Text gewinnen" in erg.text
    fehlend = (("B.pdf", "frist"), ("C.pdf", "access_denied"))
    assert modul_dienst._ohne_volltext(fehlend) == (
        "Dokument „B.pdf“: Volltext gerade nicht lesbar, später erneut. "
        "Dokument „C.pdf“: kein Volltext lesbar.")


# ── MINOR 4 ──────────────────────────────────────────────────────────────────────────────────────

def test_m4_der_aktuelle_stapel_vor_frueher():
    frueher = [{"titel": f"alt{n}.pdf", "rolle": "struktur",
                "node_id": f"{n:08d}-0000-0000-0000-000000000000"}
                for n in range(sd.HOECHSTENS + 2)]
    ablage = {"frueher": frueher, "inhalte": [
        {"index": 0, "name": "neu.pdf", "rolle": "struktur", "stand": "stored",
         "node_id": _KNOTEN}]}
    eintraege = sd.aus_ablage(ablage)
    assert len(eintraege) == sd.HOECHSTENS
    assert eintraege[0] == sd.wlo(_KNOTEN, "neu.pdf")
    # die jüngsten früheren zuerst (Paket U1: Grenze 35)
    assert eintraege[1]["name"] == f"alt{sd.HOECHSTENS + 1}.pdf"


# ── MINOR 7 ──────────────────────────────────────────────────────────────────────────────────────

def test_m7_draft_an_kuratierende_werkzeuge_ohne_inhalte():
    from boerdi.domain.write_confirm import CURATION_TOOLS
    from boerdi.services import teil_verweise

    draft = {"titel": "T", "quelle": "ordner", "knoten": [
        {"id": "k1", "titel": "A", "inhalte": [{"i": 0, "name": "Zeugnis.pdf"}],
         "kinder": [{"id": "k1-1", "titel": "B", "inhalte": [{"i": 1, "name": "x.pdf"}]}]}]}

    async def teile(name):
        return draft if name == "draft" else None

    schreibend = sorted(CURATION_TOOLS)[0]
    args, fehlt = asyncio.run(teil_verweise.einsetzen({"e": {"x": {"$teil": "draft"}}}, teile,
                                                      schreibend))
    assert fehlt == [] and "Zeugnis" not in str(args)
    assert args["e"]["x"]["knoten"][0]["kinder"][0]["titel"] == "B"
    args, _ = asyncio.run(teil_verweise.einsetzen({"e": {"x": {"$teil": "draft"}}}, teile,
                                                  "ui_strukturentwurf"))
    assert "Zeugnis" in str(args)                          # ein Modul mit ``liest: draft``


# ── MINOR 8 ──────────────────────────────────────────────────────────────────────────────────────

def test_m8_node_ids_nur_aus_der_gebundenen_ablage():
    from boerdi.ui_module.strukturentwurf import mit_knoten_ids

    daten = {"titel": "T", "quelle": "ordner", "knoten": [
        {"id": "k1", "titel": "A", "inhalte": [{"i": 0, "name": "a.pdf", "node_id": _KNOTEN_2},
                                               {"i": 1, "name": "b.pdf"}]}]}
    neu = mit_knoten_ids(daten, {1: _KNOTEN})
    assert neu["knoten"][0]["inhalte"] == [{"i": 0, "name": "a.pdf"},
                                           {"i": 1, "name": "b.pdf", "node_id": _KNOTEN}]
    assert daten["knoten"][0]["inhalte"][0]["node_id"] == _KNOTEN_2   # Kopie


def test_m8_beim_speichern_verwirft_der_server_die_node_id_des_clients(monkeypatch):
    from boerdi.services import arbeitsstand

    teile_im_vorgang = {
        "struktur": {"block_id": "b1"},
        "ablage": {"block_id": "b1", "inhalte": [
            {"index": 0, "i": 1, "stand": "stored", "node_id": _KNOTEN}]}}

    async def teil_wert(s, v, name):
        return teile_im_vorgang.get(name)

    monkeypatch.setattr(arbeitsstand.vorgaenge, "teil_wert", teil_wert)
    # Nachprüfung, MINOR 2: der Entwurf nennt seine Auswahl
    entwurf = {"titel": "T", "quelle": "ordner", "quelle_block": "b1", "knoten": [
        {"id": "k1", "titel": "A", "inhalte": [{"i": 0, "name": "a.pdf", "node_id": _KNOTEN_2},
                                               {"i": 1, "name": "b.pdf"}]}]}
    neu = asyncio.run(arbeitsstand._entwurf_mit_knoten(None, None, entwurf))
    assert neu["knoten"][0]["inhalte"] == [{"i": 0, "name": "a.pdf"},
                                           {"i": 1, "name": "b.pdf", "node_id": _KNOTEN}]
    teile_im_vorgang["ablage"]["block_id"] = "b2"          # nicht gebunden: keine node_id
    neu = asyncio.run(arbeitsstand._entwurf_mit_knoten(None, None, entwurf))
    assert all("node_id" not in i for i in neu["knoten"][0]["inhalte"])
