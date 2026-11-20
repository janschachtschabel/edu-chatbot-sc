"""Plan 2026-11-16, TG-3d/TG-3e: Strukturdokumente — der Teil ``strukturdokument`` (Verweise, zwei
Quellen), mehrere Dokumente in der Antwort von ``ui_upload``, der Generator aus mehreren Dokumenten
(ein Abschnitt oberster Ebene je Dokument, Kennungen ``d1-a3``, Fundstelle „Dokument › Abschnitt“),
der Dienst ``bereitgestellt`` und die Prüfung eines Volltexts aus WLO vor Ebene 1.

Mit einem Dokument bleibt alles wie vorher — das prüfen die Bestandstests
(``test_strukturentwurf_dokument``, ``test_golden_ui_strukturentwurf``)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from boerdi.api.schemas_ui import UiAntwort, UiBlock
from boerdi.domain.dokument_gliederung import gliederung, uebersicht, zusammenfuehren
from boerdi.services import arbeitsstand_teile
from boerdi.services import strukturentwurf_dienst as dienst
from boerdi.services.ablauf import typen, werkzeuge
from boerdi.services.dokumente import stand
from boerdi.services.dokumente import strukturdokument_teil as sd
from boerdi.ui_module import antwort, upload_rahmen
from boerdi.ui_module import upload_antwort as upload
from boerdi.ui_module.namen import UPLOAD
from tests.test_strukturentwurf_dienst import Attrappe, _k

_A = "11111111-1111-4111-8111-111111111111"
_B = "22222222-2222-4222-8222-222222222222"
_KNOTEN = "33333333-3333-3333-3333-333333333333"


# ── Teil ``strukturdokument`` (rein) ─────────────────────────────────────────────────────────────

def test_eintraege_nur_gueltige_formen_ohne_doppel():
    wert = {"dokumente": [sd.chatbot(_A, "a.pdf"), sd.chatbot(_A, "doppelt.pdf"),
                          sd.wlo(_KNOTEN, "w.pdf"), {"quelle": "wlo", "ref": "kein-knoten"},
                          {"quelle": "chatbot", "ref": "nicht-dokument"}, "kaputt"]}
    assert sd.eintraege(wert) == [sd.chatbot(_A, "a.pdf"), sd.wlo(_KNOTEN, "w.pdf")]
    assert sd.eintraege("kaputt") == [] and sd.eintraege(None) == []
    assert sd.upload_id(sd.chatbot(_A, "a")) == _A and sd.upload_id(sd.wlo(_KNOTEN, "w")) is None


def test_nach_dem_lesen_bleiben_die_knoten_aus_wlo():
    alt = sd.wert([sd.chatbot(_A, "a.pdf"), sd.wlo(_KNOTEN, "w.pdf")])
    neu = sd.mit_chatbot(alt, [sd.chatbot(_B, "b.pdf")])
    assert neu == {"dokumente": [sd.chatbot(_B, "b.pdf"), sd.wlo(_KNOTEN, "w.pdf")]}


def test_nach_der_ablage_kommen_die_knoten_mit_rolle_struktur_dazu():
    ablage = {"inhalte": [
        {"index": 0, "name": "lp.pdf", "rolle": "struktur", "stand": "stored", "node_id": _KNOTEN},
        {"index": 1, "name": "x.pdf", "rolle": "inhalt", "stand": "stored",
         "node_id": "44444444-4444-4444-4444-444444444444"}]}
    alt = sd.wert([sd.chatbot(_A, "a.pdf")])
    assert sd.mit_ablage(alt, ablage) == {"dokumente": [sd.chatbot(_A, "a.pdf"),
                                                        sd.wlo(_KNOTEN, "lp.pdf")]}
    # unverändert → nichts schreiben (keine neue Fassung je abgelegter Datei)
    assert sd.mit_ablage(sd.mit_ablage(alt, ablage), ablage) is None
    assert sd.mit_ablage(alt, {"inhalte": []}) is None
    assert sd.zusammenfassung(sd.eintraege(sd.mit_ablage(alt, ablage))) == (
        "2 Strukturdokumente: „a.pdf“, „lp.pdf“")


def test_strukturdokument_ist_bereitstellung_mit_bekanntem_typ():
    assert sd.TEIL in arbeitsstand_teile.BEREITSTELLUNG
    assert typen.MODUL_TEILE[sd.TEIL] == sd.TYP == typen.STRUKTURDOKUMENTE


# ── Antwort von ``ui_upload`` mit mehreren gelesenen Dokumenten ──────────────────────────────────

def _dok(kennung: str, name: str, abschnitte: int = 4, vorschau=("Kapitel 1",)) -> dict:
    return {"upload_id": kennung, "name": name, "format": "pdf", "vorschau": list(vorschau),
            "befund": {"seiten": 3, "woerter": 100, "abschnitte": abschnitte,
                       "gliederung_art": "ueberschriften", "warnungen": []}}


def _datei(i: int, name: str, rolle: str = "inhalt") -> dict:
    return {"i": i, "name": name, "endung": "pdf", "groesse": 10, "rolle": rolle}


def _daten(*dokumente: dict) -> dict:
    daten = {
        "aktion": "dokument",
        "struktur": {"name": "Physik", "dateien": 2, "alle_dateien": 2, "kinder": [],
                     "dateiliste": [_datei(0, "Lehrplan A.pdf", "struktur"),
                                    _datei(1, "Lehrplan B.pdf", "struktur")]},
        "zahlen": {"ordner": 1, "dateien": 2, "inhalte": 0, "ignoriert": 0,
                   "strukturdokumente": 2, "bytes": 20},
        "strukturdokument": {"name": "Lehrplan A.pdf", "groesse": 10, "endung": "pdf"},
        "warnungen": [],
        "dokument": dokumente[0],
    }
    if len(dokumente) > 1:
        daten["dokumente"] = list(dokumente)
    return daten


def _pruefe(daten: dict) -> dict | None:
    block = UiBlock(block_id="b0000001", modul=UPLOAD, version=1, art="abfragen",
                    daten={"zweck": "bereitstellen"}, text="t", status="offen")
    entities: dict = {}
    antwort.merke_frage(entities, block)
    return antwort.antwort_pruefen(entities[antwort.OFFENE_FRAGE],
                                   UiAntwort(block_id="b0000001", daten=daten))


def test_zwei_gelesene_dokumente_sind_eine_gueltige_antwort():
    geprueft = _pruefe(_daten(_dok(_A, "Lehrplan A.pdf"), _dok(_B, "Lehrplan B.pdf")))
    assert geprueft is not None
    teile = {t[0]: t for t in arbeitsstand_teile.teile_aus_antwort(geprueft)}
    # ``document`` bleibt das erste (Rückwärts-Teil), ``strukturdokument`` verweist auf beide
    assert teile["document"][2]["upload_id"] == _A
    assert teile["strukturdokument"][2] == {"dokumente": [
        sd.chatbot(_A, "Lehrplan A.pdf"), sd.chatbot(_B, "Lehrplan B.pdf")]}
    assert teile["strukturdokument"][3] == (
        "2 Strukturdokumente: „Lehrplan A.pdf“, „Lehrplan B.pdf“")


def test_eine_antwort_mit_einem_dokument_bleibt_wie_vorher():
    daten = _daten(_dok(_A, "Lehrplan A.pdf"))
    assert "dokumente" not in daten and _pruefe(daten) is not None
    assert upload.gelesene(daten) == [daten["dokument"]]


def test_unstimmige_dokumente_werden_abgewiesen():
    a, b = _dok(_A, "Lehrplan A.pdf"), _dok(_B, "Lehrplan B.pdf")
    falsch_vorne = _daten(a, b)
    falsch_vorne["dokument"] = b
    assert _pruefe(falsch_vorne) is None
    doppelt = _daten(a, b)
    doppelt["dokumente"] = [a, dict(a)]
    assert _pruefe(doppelt) is None
    mehr_als_markiert = _daten(a, b)
    mehr_als_markiert["zahlen"] = {**mehr_als_markiert["zahlen"], "strukturdokumente": 1}
    mehr_als_markiert["struktur"]["dateiliste"][1]["rolle"] = "inhalt"
    assert _pruefe(mehr_als_markiert) is None
    ohne_aktion = _daten(a, b)
    ohne_aktion["aktion"] = "erfasst"
    del ohne_aktion["dokument"]
    assert _pruefe(ohne_aktion) is None


def test_die_ki_sieht_beide_befunde_aber_keinen_text():
    geprueft = _pruefe(_daten(_dok(_A, "Lehrplan A.pdf", 4, ["Mechanik"]),
                              _dok(_B, "Lehrplan B.pdf", 7, ["Optik"])))
    start, zeilen = upload_rahmen.zeilen(geprueft)
    text = "\n".join(zeilen)
    assert start == upload_rahmen.DOKUMENT_FRAME_START
    assert "2 gelesene Strukturdokumente" in text
    assert "Dokument 1: Lehrplan A.pdf (pdf), 4 Abschnitte" in text
    assert "Dokument 2: Lehrplan B.pdf (pdf), 7 Abschnitte" in text
    assert "- Lehrplan B.pdf: Optik" in text
    # die Sicherheitsprüfung liest Namen und Überschriften beider
    pruef = upload.sicherheit(geprueft["daten"])
    assert "Lehrplan B.pdf" in pruef and "Optik" in pruef


# ── Gliederung aus mehreren Dokumenten ───────────────────────────────────────────────────────────

_MD_A = "# Mechanik\nKräfte.\n# Optik\nLicht.\n# Akustik\nSchall.\n"
_MD_B = "# Mechanik\nHebel.\n# Wärme\nTemperatur.\n# Elektrik\nStrom.\n"


def _stand(kennung: str, name: str, md: str) -> stand.DokumentStand:
    abschnitte, _ = gliederung(md)
    return stand.DokumentStand(upload_id=kennung, name=name, format="pdf", befund={},
                               abschnitte=abschnitte, markdown=md)


def test_zusammenfuehren_gibt_je_dokument_einen_abschnitt_oberster_ebene():
    a, b = _stand(_A, "Plan A", _MD_A), _stand(_B, "Plan B", _MD_B)
    abschnitte, md = zusammenfuehren([(a.name, a.abschnitte, a.markdown),
                                      (b.name, b.abschnitte, b.markdown)])
    ids = [x.id for x in abschnitte]
    assert ids == ["d1", "d1-a1", "d1-a2", "d1-a3", "d2", "d2-a1", "d2-a2", "d2-a3"]
    nach_id = {x.id: x for x in abschnitte}
    assert md[nach_id["d2-a2"].start:nach_id["d2-a2"].ende] == "# Wärme\nTemperatur.\n"
    text, _ = uebersicht(abschnitte, 8000, bis_ebene=4)
    assert "- Plan B [d2]\n  - Mechanik [d2-a1]\n  - Wärme [d2-a2]" in text


def test_der_generator_nimmt_mehrere_dokumente_mit_praefix_und_fundstelle():
    vereint = stand.vereint([_stand(_A, "Plan A", _MD_A), _stand(_B, "Plan B", _MD_B)])
    llm = Attrappe([_k("Mechanik", 2, abschnitte=["d1-a1", "d2-a1"]),
                    _k("Wärme", 0, abschnitte=["d2-a2", "a2"])],
                   {"Mechanik": [_k("Kräfte"), _k("Hebel")]})

    async def lauf():
        ende = asyncio.get_running_loop().time() + 60
        return await dienst.erzeugen(dienst.Auftrag(thema="Physik", tiefe=2), llm=llm,
                                     frist_ende=ende, dokument=vereint)

    erzeugt = asyncio.run(lauf())
    mechanik, waerme = erzeugt.daten["knoten"]
    assert mechanik["abschnitte"] == ["d1-a1", "d2-a1"]
    assert mechanik["fundstelle"] == "Plan A › Mechanik"
    assert waerme["abschnitte"] == ["d2-a2"]          # „a2“ ohne Präfix gibt es nicht
    oben = llm.aufrufe[0]
    assert "NACH MEHREREN DOKUMENTEN" in oben["aufgabe"]
    assert "- Plan A [d1]" in oben["auftrag"]["dokument"]["gliederung"]
    # Zweites Review A, MINOR 5: ohne Zusage der Moderation (``ganz_moderiert``) der Anfang
    assert oben["auftrag"]["dokument"]["anfang"].startswith("# Plan A")
    # Ebene 2 liest den Text beider Fundstellen — gedeckelt wie bei einem Dokument
    kinder = next(a for a in llm.aufrufe if "knoten" in a["auftrag"])
    assert "Kräfte." in kinder["auftrag"]["auszug"] and "Hebel." in kinder["auftrag"]["auszug"]
    assert len(kinder["auftrag"]["auszug"]) <= dienst.DOKUMENT_AUSZUG


def test_deckel_gelten_insgesamt():
    lang = "".join(f"# Kapitel {i} mit einem recht langen Namen\n{'Text ' * 50}\n"
                   for i in range(1, 300))
    vereint = stand.vereint([_stand(_A, "Plan A", lang), _stand(_B, "Plan B", lang),
                             _stand("u-3", "Plan C", lang)])
    llm = Attrappe([_k("Kapitel", 0, abschnitte=["d1-a1"])])

    async def lauf():
        ende = asyncio.get_running_loop().time() + 60
        return await dienst.erzeugen(dienst.Auftrag(thema="Physik", tiefe=1), llm=llm,
                                     frist_ende=ende, dokument=vereint)

    asyncio.run(lauf())
    dok = llm.aufrufe[0]["auftrag"]["dokument"]
    assert len(dok["gliederung"]) <= dienst.DOKUMENT_GLIEDERUNG
    assert len(dok["anfang"]) <= dienst.DOKUMENT_ANFANG


# ── Ein Volltext aus WLO geht erst nach der Moderation an Ebene 1 ────────────────────────────────

def test_ein_ungepruefter_volltext_wird_vor_ebene_eins_moderiert(monkeypatch):
    from boerdi.ui_module import dienst as modul_dienst
    from boerdi.ui_module import katalog
    from boerdi.ui_module.aufruf import Umgebung

    geprueft: list[str] = []

    async def pruefen(text):
        geprueft.append(text)
        return "abgewiesen"

    wlo = _stand(_KNOTEN, "Lehrplan WLO", _MD_A)
    wlo = stand.DokumentStand(**{**wlo.__dict__, "ungeprueft": True})

    async def lader():
        return wlo

    monkeypatch.setattr(modul_dienst, "_ebene_eins_pruefen", pruefen)
    manifest = katalog.katalog()["ui_strukturentwurf"]
    erg = asyncio.run(modul_dienst.aufruf(manifest, {"thema": "Physik", "aus_dokument": True},
                                          Umgebung(dokument=lader)))
    assert erg.block is None and erg.outcome.error == "abgewiesen"
    assert geprueft and "Mechanik [a1]" in geprueft[0]


# ── Dienst ``bereitgestellt`` ────────────────────────────────────────────────────────────────────

def test_bereitgestellt_meldet_strukturdokumente_mit_lesbarkeit():
    teil = sd.wert([sd.chatbot(_A, "A.pdf"), sd.chatbot(_B, "B.pdf"), sd.wlo(_KNOTEN, "W.pdf")])
    document = {"ref": f"dokument:{_A}", "name": "A.pdf", "format": "pdf", "befund": {}}

    async def teile(name):
        return {sd.TEIL: teil, "document": document}.get(name)

    async def kennungen():
        return [_A]                   # B ist abgelaufen

    kontext = werkzeuge.DienstKontext(teile=teile, dokument_ids=kennungen)
    wert = asyncio.run(werkzeuge.DIENSTE["bereitgestellt"]({}, kontext))
    assert wert["strukturdokumente"] == [{"name": "A.pdf", "lesbar": True},
                                         {"name": "B.pdf", "lesbar": False},
                                         {"name": "W.pdf", "lesbar": True}]
    assert wert["lesbare_strukturdokumente"] == 2
    assert wert["dokument"] == {"name": "A.pdf", "lesbar": True}
    assert werkzeuge.ZUSAMMENFASSUNG["bereitgestellt"](wert) == (
        "Dokument „A.pdf“, 2 Strukturdokumente")


def test_mit_mehreren_ist_das_dokument_des_teils_lesbar_auch_wenn_es_nicht_das_juengste_ist():
    """TG-3e: ``document`` ist das erste gelesene, das jüngste ist ein anderes — lesbar bleibt
    es trotzdem (vorher zählte nur das jüngste)."""
    document = {"ref": f"dokument:{_A}", "name": "A.pdf", "format": "pdf", "befund": {}}

    async def teile(name):
        return {"document": document}.get(name)

    async def kennungen():
        return [_A, _B]

    async def juengstes():
        return _B

    kontext = werkzeuge.DienstKontext(teile=teile, dokument_id=juengstes,
                                      dokument_ids=kennungen)
    wert = asyncio.run(werkzeuge.DIENSTE["bereitgestellt"]({}, kontext))
    assert wert["dokument"]["lesbar"] is True


def test_der_dienst_kontext_reicht_alle_kennungen_durch():
    from boerdi.services.ablauf import treiber

    async def kennungen():
        return [_A]

    async def teile(_name):
        return None

    k = treiber.dienst_kontext(treiber.Umgebung(teile=teile, dokument_ids=kennungen))
    assert k.dokument_ids is kennungen


def test_das_dokument_der_antwort_gilt_auch_wenn_es_nicht_das_juengste_ist(monkeypatch):
    """TG-3e: ``arbeitsstand._dokument_bestaetigt`` prüft gegen alle lesbaren Dokumente."""
    from boerdi.services import arbeitsstand
    from boerdi.services.dokumente import ablage

    zeilen = [SimpleNamespace(id=_A, name="A.pdf", format="pdf", befund={"abschnitte": 3}),
              SimpleNamespace(id=_B, name="B.pdf", format="pdf", befund={"abschnitte": 5})]

    async def alle_fuer_aufrufer(s, session_id, aufrufer, *_rolle):  # Paket U: Rolle
        return zeilen

    monkeypatch.setattr(ablage, "alle_fuer_aufrufer", alle_fuer_aufrufer)
    monkeypatch.setattr(arbeitsstand, "has_personal_auth", lambda: False)
    wert, kurz = asyncio.run(arbeitsstand._dokument_bestaetigt(None, "s", {"upload_id": _A}))
    assert wert["ref"] == f"dokument:{_A}" and kurz == "A.pdf, 3 Abschnitte"
    neu, kurz = asyncio.run(arbeitsstand._strukturdokumente_bestaetigt(
        None, "s", sd.wert([sd.chatbot(_B, "gefälscht"), sd.chatbot("weg", "x")]),
        sd.wert([sd.wlo(_KNOTEN, "W.pdf")])))
    assert neu == {"dokumente": [sd.chatbot(_B, "B.pdf"), sd.wlo(_KNOTEN, "W.pdf")]}


# ── Nach der Ablage schreibt ``vorgang_teil`` den Teil ``strukturdokument`` mit ─────────────────

def test_nach_der_ablage_folgt_der_teil_strukturdokument(monkeypatch):
    from boerdi.services import arbeitsstand
    from boerdi.services.ablage import vorgang_teil

    geschrieben: list = []
    vorhanden = {sd.TEIL: sd.wert([sd.chatbot(_A, "a.pdf")])}

    def teil_lader(s, session_id, entities):
        async def teil(name):
            return vorhanden.get(name)
        return teil

    async def teile_speichern(s, session_id, entities, teile, *, neu=None, nur_dieser=False):
        geschrieben.append([(t[0], t[2]) for t in teile])
        return True

    monkeypatch.setattr(arbeitsstand, "teil_lader", teil_lader)
    monkeypatch.setattr(arbeitsstand, "teile_speichern", teile_speichern)
    ablage = {"format": vorgang_teil.TYP, "inhalte": [
        {"index": 0, "name": "lp.pdf", "rolle": "struktur", "stand": "offen"}]}
    asyncio.run(vorgang_teil.speichern(None, "s", {}, ablage))
    assert [n for n, _ in geschrieben[-1]] == ["ablage"]        # noch nichts abgelegt
    ablage["inhalte"][0].update(stand="stored", node_id=_KNOTEN)
    asyncio.run(vorgang_teil.speichern(None, "s", {}, ablage))
    assert geschrieben[-1][1] == (sd.TEIL, {"dokumente": [sd.chatbot(_A, "a.pdf"),
                                                          sd.wlo(_KNOTEN, "lp.pdf")]})


def test_beim_erfassen_nennt_der_rahmen_alle_markierten():
    daten = _daten(_dok(_A, "Lehrplan A.pdf"))
    daten["aktion"] = "erfasst"
    del daten["dokument"]
    geprueft = _pruefe(daten)
    assert geprueft is not None
    _start, zeilen = upload_rahmen.zeilen(geprueft)
    assert "Strukturdokumente: Lehrplan A.pdf, Lehrplan B.pdf" in zeilen
