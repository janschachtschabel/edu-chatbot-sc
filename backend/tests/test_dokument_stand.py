"""Paket U3-2b: das Dokument der Sitzung für den Zug — einmal laden, Frist verlängern, freigeben.

Plan 2026-11-16, TG-3d/TG-3e: mehrere Strukturdokumente (Teil ``strukturdokument`` oder alle
lesbaren der Sitzung) werden ein Stand; der Leser holt den Text je Quelle."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import OperationalError

from boerdi.domain.dokument_gliederung import Abschnitt
from boerdi.services.dokumente import stand
from boerdi.services.dokumente import strukturdokument as leser
from boerdi.services.dokumente import strukturdokument_teil as sd
from boerdi.ui_module import dienst_upload

_KNOTEN = "11111111-2222-3333-4444-555555555555"


@pytest.fixture(autouse=True)
def _erlaubt(monkeypatch):
    monkeypatch.setattr(dienst_upload, "dokument_erlaubt", lambda: True)


class _S:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.commits -= 100


def _zeile(kennung="u-1", name="Lehrplan.pdf"):
    return SimpleNamespace(
        id=kennung, name=name, format="pdf", befund={"abschnitte": 2},
        gliederung=[{"id": "a1", "ebene": 1, "titel": "Mechanik", "start": 0, "ende": 10},
                    {"id": "a2", "ebene": 1, "titel": "Optik", "start": 10, "ende": 20}],
        markdown="# Mechanik\n# Optik\n")


async def _ohne(*_a, **_k):
    return None


def test_der_lader_liest_einmal_beruehrt_und_gibt_den_stand(monkeypatch):
    gelesen, beruehrt = [], []

    async def alle_lesbaren(s, session_id, aufrufer, *_rolle):  # Paket U: Rolle
        gelesen.append((session_id, aufrufer))
        return [_zeile()]

    async def beruehren(s, upload_id, *, ttl_h):
        beruehrt.append((upload_id, ttl_h))

    monkeypatch.setattr(stand.ablage, "zuschreiben", _ohne)
    monkeypatch.setattr(stand.ablage, "alle_lesbaren", alle_lesbaren)
    monkeypatch.setattr(stand.ablage, "beruehren", beruehren)
    monkeypatch.setattr(stand, "has_personal_auth", lambda: True)
    monkeypatch.setattr(stand, "aufrufer_kennung", lambda: "person-a")
    s = _S()
    laden = stand.lader(s, "sitzung-0123456789")

    async def zweimal():
        return await laden(), await laden()

    eins, zwei = asyncio.run(zweimal())
    assert eins is zwei and eins.upload_id == "u-1" and eins.name == "Lehrplan.pdf"
    assert eins.abschnitte == [Abschnitt("a1", 1, "Mechanik", 0, 10),
                               Abschnitt("a2", 1, "Optik", 10, 20)]
    # TG-3e: mit einem Dokument bleibt alles wie vorher
    assert eins.dokumente == 1 and eins.anfang is None and not eins.ungeprueft
    assert gelesen == [("sitzung-0123456789", "person-a")]
    assert beruehrt == [("u-1", 24)] and s.commits == 1


def test_ohne_anmeldung_ohne_aufrufer_und_ohne_dokument_none(monkeypatch):
    gelesen = []

    async def alle_lesbaren(s, session_id, aufrufer, *_rolle):  # Paket U: Rolle
        gelesen.append(aufrufer)
        return []

    monkeypatch.setattr(stand.ablage, "alle_lesbaren", alle_lesbaren)
    monkeypatch.setattr(stand, "has_personal_auth", lambda: False)
    assert asyncio.run(stand.lader(_S(), "sitzung-0123456789")()) is None
    assert gelesen == [None]


def test_eine_kaputte_gliederung_zaehlt_als_kein_dokument(monkeypatch):
    async def alle_lesbaren(s, session_id, aufrufer, *_rolle):  # Paket U: Rolle
        z = _zeile()
        z.gliederung = [{"id": "a1"}]
        return [z]

    monkeypatch.setattr(stand.ablage, "alle_lesbaren", alle_lesbaren)
    monkeypatch.setattr(stand, "has_personal_auth", lambda: False)
    assert asyncio.run(stand.lader(_S(), "sitzung-0123456789")()) is None


def test_abgeschaltet_gibt_es_kein_dokument_ohne_abfrage(monkeypatch):
    """Review U3-2 Befund 7: schaltet das Studio ab, bleibt ein gespeichertes Dokument ungenutzt."""
    async def nie(*_a):
        raise AssertionError("keine Abfrage, wenn es nicht erlaubt ist")

    monkeypatch.setattr(dienst_upload, "dokument_erlaubt", lambda: False)
    monkeypatch.setattr(stand.ablage, "alle_lesbaren", nie)
    assert asyncio.run(stand.lader(_S(), "sitzung-0123456789")()) is None


def test_ein_datenbankfehler_ergibt_kein_dokument_statt_einer_ausnahme(monkeypatch):
    async def streikt(*_a):
        raise OperationalError("select", {}, Exception("weg"))

    monkeypatch.setattr(stand.ablage, "alle_lesbaren", streikt)
    monkeypatch.setattr(stand, "has_personal_auth", lambda: False)
    s = _S()
    assert asyncio.run(stand.lader(s, "sitzung-0123456789")()) is None
    assert s.commits == -100                  # zurückgerollt


def test_tb_e1_angemeldet_uebernimmt_die_anonymen_dokumente(monkeypatch):
    """Plan 2026-11-10, TB-E1: die angemeldete Person übernimmt die anonymen Dokumente derselben
    Sitzung (``ablage.zuschreiben``) — vor dem Lesen — und schreibt das fest."""
    gefragt = []

    async def alle_lesbaren(s, session_id, aufrufer, *_rolle):  # Paket U: Rolle
        gefragt.append(("alle_lesbaren", aufrufer))
        return [_zeile()]

    async def zuschreiben(s, session_id, aufrufer):
        gefragt.append(("zuschreiben", aufrufer))
        return _zeile()

    monkeypatch.setattr(stand.ablage, "alle_lesbaren", alle_lesbaren)
    monkeypatch.setattr(stand.ablage, "zuschreiben", zuschreiben)
    monkeypatch.setattr(stand.ablage, "beruehren", _ohne)
    monkeypatch.setattr(stand, "has_personal_auth", lambda: True)
    monkeypatch.setattr(stand, "aufrufer_kennung", lambda: "person-a")
    s = _S()
    erg = asyncio.run(stand.laden(s, "sitzung-0123456789"))
    assert erg is not None and erg.upload_id == "u-1"
    assert gefragt == [("zuschreiben", "person-a"), ("alle_lesbaren", "person-a")]
    assert s.commits == 1


def test_tb_e1_anonym_wird_nichts_zugeschrieben(monkeypatch):
    async def alle_lesbaren(s, session_id, aufrufer, *_rolle):  # Paket U: Rolle
        return []

    async def zuschreiben(s, session_id, aufrufer):  # pragma: no cover — darf nicht laufen
        raise AssertionError("anonym darf nichts übernehmen")

    monkeypatch.setattr(stand.ablage, "alle_lesbaren", alle_lesbaren)
    monkeypatch.setattr(stand.ablage, "zuschreiben", zuschreiben)
    monkeypatch.setattr(stand, "has_personal_auth", lambda: False)
    assert asyncio.run(stand.laden(_S(), "sitzung-0123456789")) is None


def test_tb_e1_review_2_zwei_zuege_derselben_person_finden_beide_das_dokument(monkeypatch):
    """Review TB-E1, Befund 2: hat ein paralleler Zug die Dokumente schon übernommen (nichts mehr
    ohne Besitzerin), liest der zweite trotzdem unter ihrer Kennung — statt ``kein_dokument``."""
    from boerdi.services.dokumente import ablage

    async def alle_lesbaren(s, session_id, aufrufer, *_rolle):  # Paket U: Rolle
        return [_zeile()] if aufrufer == "person-a" else []

    monkeypatch.setattr(ablage, "alle_lesbaren", alle_lesbaren)
    monkeypatch.setattr(ablage, "zuschreiben", _ohne)       # der andere Zug war schneller
    erg = asyncio.run(ablage.fuer_aufrufer(_S(), "sitzung-0123456789", "person-a"))
    assert erg is not None and erg.id == "u-1"


def test_tb_e1_review_anonym_liest_fuer_aufrufer_nur_das_anonyme(monkeypatch):
    from boerdi.services.dokumente import ablage

    async def alle_lesbaren(s, session_id, aufrufer, *_rolle):  # Paket U: Rolle
        assert aufrufer is None
        return []

    async def zuschreiben(s, session_id, aufrufer):  # pragma: no cover — darf nicht laufen
        raise AssertionError("anonym wird nichts übernommen")

    monkeypatch.setattr(ablage, "alle_lesbaren", alle_lesbaren)
    monkeypatch.setattr(ablage, "zuschreiben", zuschreiben)
    assert asyncio.run(ablage.fuer_aufrufer(_S(), "sitzung-0123456789", None)) is None


# ── TG-3e: mehrere Dokumente ─────────────────────────────────────────────────────────────────────

def test_tg3e_mehrere_dokumente_der_sitzung_werden_ein_stand(monkeypatch):
    async def alle_lesbaren(s, session_id, aufrufer, *_rolle):  # Paket U: Rolle
        return [_zeile("u-1", "Lehrplan A.pdf"), _zeile("u-2", "Lehrplan B.pdf")]

    monkeypatch.setattr(stand.ablage, "alle_lesbaren", alle_lesbaren)
    monkeypatch.setattr(stand.ablage, "beruehren", _ohne)
    monkeypatch.setattr(stand, "has_personal_auth", lambda: False)
    erg = asyncio.run(stand.laden(_S(), "sitzung-0123456789"))
    assert erg is not None and erg.dokumente == 2
    assert [a.id for a in erg.abschnitte] == ["d1", "d1-a1", "d1-a2", "d2", "d2-a1", "d2-a2"]
    assert [a.ebene for a in erg.abschnitte] == [1, 2, 2, 1, 2, 2]
    oben = {a.id: a for a in erg.abschnitte}
    assert oben["d2"].titel == "Lehrplan B.pdf"
    # die Stellen verschieben sich mit: der Text eines Abschnitts ist sein Text im Dokument
    original = _zeile().markdown
    assert erg.markdown[oben["d2-a2"].start:oben["d2-a2"].ende] == original[10:20]
    assert erg.markdown[oben["d1-a1"].start:oben["d1-a1"].ende] == original[0:10]
    assert erg.anfang is not None and len(erg.anfang) <= stand.ANFANG_ZEICHEN
    assert "Lehrplan A.pdf" in erg.anfang and "Lehrplan B.pdf" in erg.anfang


def _sitzung(monkeypatch, *zeilen):
    """M1: der Leser liest Sitzungsdokumente über ``alle_fuer_aufrufer`` (mit Übernahme)."""
    async def alle_fuer_aufrufer(s, session_id, aufrufer, *_rolle):  # Paket U: Rolle
        return list(zeilen)

    monkeypatch.setattr(leser.ablage, "alle_fuer_aufrufer", alle_fuer_aufrufer)
    monkeypatch.setattr(leser.ablage, "beruehren", _ohne)


def test_tg3d_der_teil_strukturdokument_bestimmt_die_dokumente(monkeypatch):
    """Mit Vorgang zählt der Teil (Quelle chatbot über die Sitzung, Quelle wlo über den Leser) —
    ein Dokument der Sitzung, das nicht darin steht, nicht."""
    teil = sd.wert([sd.chatbot("u-2", "B.pdf"), sd.wlo(_KNOTEN, "Lehrplan WLO.pdf")])

    async def teile(name):
        return teil if name == sd.TEIL else None

    async def volltext(node_id):
        assert node_id == _KNOTEN
        return "# Kapitel 1\nText\n# Kapitel 2\nText\n# Kapitel 3\nText", ""

    _sitzung(monkeypatch, _zeile("u-1", "A.pdf"), _zeile("u-2", "B.pdf"))
    monkeypatch.setattr(leser, "volltext", volltext)
    monkeypatch.setattr(leser, "has_personal_auth", lambda: False)
    erg = asyncio.run(stand.laden(_S(), "sitzung-0123456789", teile))
    assert erg is not None and erg.dokumente == 2 and erg.ungeprueft
    assert [a.id for a in erg.abschnitte if a.ebene == 1] == ["d1", "d2"]
    assert [a.titel for a in erg.abschnitte if a.ebene == 1] == ["B.pdf", "Lehrplan WLO.pdf"]
    assert [a.titel for a in erg.abschnitte if a.id.startswith("d2-")] == [
        "Kapitel 1", "Kapitel 2", "Kapitel 3"]


def test_tg3d_ein_dokument_aus_wlo_braucht_den_schalter_des_chat_lesens_nicht(monkeypatch):
    teil = sd.wert([sd.chatbot("u-2", "B.pdf"), sd.wlo(_KNOTEN, "Lehrplan WLO.pdf")])

    async def teile(name):
        return teil if name == sd.TEIL else None

    async def nie(*_a):
        raise AssertionError("ein Sitzungsdokument nur mit dem Schalter")

    async def volltext(node_id):
        return "# A\nx\n# B\ny\n# C\nz", ""

    monkeypatch.setattr(dienst_upload, "dokument_erlaubt", lambda: False)
    monkeypatch.setattr(leser.ablage, "alle_fuer_aufrufer", nie)
    monkeypatch.setattr(leser, "volltext", volltext)
    erg = asyncio.run(stand.laden(_S(), "sitzung-0123456789", teile))
    assert erg is not None and erg.dokumente == 1 and erg.ungeprueft
    assert erg.name == "Lehrplan WLO.pdf" and erg.upload_id == _KNOTEN


def _mcp(monkeypatch, antwort: dict, gerufen: list | None = None):
    from boerdi.services.mcp import client

    async def call_mcp_tool(name, args, *, use_cache=True):
        if gerufen is not None:
            gerufen.append((name, args, use_cache))
        return json.dumps(antwort)

    monkeypatch.setattr(client, "call_mcp_tool", call_mcp_tool)
    monkeypatch.setattr(leser, "has_personal_auth", lambda: True)


def test_tg3d_der_volltext_kommt_nur_lesend_ueber_das_mcp(monkeypatch):
    """Nie selbst schreiben: der Leser ruft nur ``get_wlo_content_text`` (Cache nicht gelesen)."""
    gerufen: list = []
    _mcp(monkeypatch, {"nodeId": "n-1", "title": "T", "text": "# A\nB", "source": "repository",
                       "charCount": 5, "truncated": False}, gerufen)
    assert asyncio.run(leser.volltext("n-1")) == ("# A\nB", "")
    assert gerufen == [("get_wlo_content_text", {"nodeId": "n-1", "maxChars": 200_000}, False)]


def test_tg3d_ohne_volltext_kein_text_mit_grund(monkeypatch):
    _mcp(monkeypatch, {"nodeId": "n-1", "title": "T", "text": "", "source": "none",
                       "reason": "not_extracted"})
    assert asyncio.run(leser.volltext("n-1")) == (None, "not_extracted")
    _mcp(monkeypatch, {"nodeId": "n-1", "text": "", "reason": "irgendein Servertext"})
    assert asyncio.run(leser.volltext("n-1")) == (None, "ohne_text")   # nur feste Codes


def test_nit_ohne_anmeldung_wird_kein_volltext_gelesen(monkeypatch):
    gerufen: list = []
    _mcp(monkeypatch, {"text": "x"}, gerufen)
    monkeypatch.setattr(leser, "has_personal_auth", lambda: False)
    assert asyncio.run(leser.volltext("n-1")) == (None, "ohne_anmeldung") and gerufen == []


def test_tg3e_im_vorgang_ergaenzt_strukturdokumente_aus_der_ablage():
    ablage = {"inhalte": [
        {"index": 0, "name": "lp.pdf", "rolle": "struktur", "stand": "stored", "node_id": _KNOTEN},
        {"index": 1, "name": "x.pdf", "rolle": "inhalt", "stand": "stored",
         "node_id": "aaaaaaaa-2222-3333-4444-555555555555"},
        {"index": 2, "name": "y.pdf", "rolle": "struktur", "stand": "failed"}]}

    async def teile(name):
        return {sd.TEIL: sd.wert([sd.chatbot("u-1", "a.pdf")]), "ablage": ablage}.get(name)

    eintraege = asyncio.run(leser.im_vorgang(teile))
    assert eintraege == [sd.chatbot("u-1", "a.pdf"), sd.wlo(_KNOTEN, "lp.pdf")]
