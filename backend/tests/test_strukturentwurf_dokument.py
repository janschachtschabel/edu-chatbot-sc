"""Paket U3-2b: ein Strukturentwurf aus dem Dokument der Person (``aus_dokument``).

Ebene 1 sieht die Gliederung des Dokuments (mit Kennungen ``[aN]``, ≤ 8000 Zeichen) und seinen
Anfang (≤ 1500); jeder Punkt nennt die Abschnitte, aus denen er stammt. Ebene 2 bekommt den Text
genau dieser Abschnitte samt Unterabschnitten (≤ 6000 je Aufruf). Das Modell sieht nie das ganze
Dokument; was es an Kennungen erfindet, fällt weg.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from boerdi.domain.dokument_gliederung import gliederung, mit_unterabschnitten
from boerdi.services import strukturentwurf_dienst as dienst
from tests.test_strukturentwurf_dienst import Attrappe, _k

_MD = ("# Lehrplan Physik\nVorwort zum Plan.\n"
       "## 1 Mechanik\nKräfte wirken.\n### 1.1 Kraft\nNewton.\n### 1.2 Energie\nJoule.\n"
       "## 2 Optik\nLicht.\n### 2.1 Linsen\nBrennweite.\n"
       "## 3 Akustik\nSchall.\n")


def _dokument(md: str = _MD):
    abschnitte, _ = gliederung(md)
    return SimpleNamespace(markdown=md, abschnitte=abschnitte)


async def _erzeugen(llm, dokument=None, **auftrag):
    ende = asyncio.get_running_loop().time() + 60
    return await dienst.erzeugen(dienst.Auftrag(**{"thema": "Lehrplan Physik", **auftrag}),
                                 llm=llm, frist_ende=ende, dokument=dokument or _dokument())


def test_unterabschnitte_gehoeren_zum_abschnitt():
    abschnitte, _ = gliederung(_MD)
    ids = {a.titel: a.id for a in abschnitte}
    assert mit_unterabschnitten(abschnitte, [ids["1 Mechanik"]]) == [
        ids["1 Mechanik"], ids["1.1 Kraft"], ids["1.2 Energie"]]
    assert mit_unterabschnitten(abschnitte, [ids["3 Akustik"], "a999"]) == [ids["3 Akustik"]]


async def test_die_obere_ebene_folgt_dem_dokument_und_nennt_die_fundstelle():
    abschnitte, _ = gliederung(_MD)
    ids = {a.titel: a.id for a in abschnitte}
    llm = Attrappe([_k("Mechanik", abschnitte=[ids["1 Mechanik"]]),
                    _k("Optik", abschnitte=[ids["2 Optik"], "a999"]),
                    _k("Ohne Herkunft", abschnitte=["x"])])
    erzeugt = await _erzeugen(llm, tiefe=1)
    d = erzeugt.daten
    assert d["quelle"] == "dokument" and d["thema"] == "Lehrplan Physik"
    mechanik, optik, ohne = d["knoten"]
    assert mechanik["abschnitte"] == [ids["1 Mechanik"]] and mechanik["fundstelle"] == "1 Mechanik"
    assert optik["abschnitte"] == [ids["2 Optik"]]           # erfundene Kennung fällt weg
    assert "abschnitte" not in ohne and "fundstelle" not in ohne
    [aufruf] = llm.aufrufe
    dok = aufruf["auftrag"]["dokument"]
    assert f"- 1 Mechanik [{ids['1 Mechanik']}]" in dok["gliederung"]
    assert dok["anfang"].startswith("# Lehrplan Physik")


async def test_ebene_zwei_liest_den_text_der_abschnitte():
    abschnitte, _ = gliederung(_MD)
    ids = {a.titel: a.id for a in abschnitte}
    llm = Attrappe([_k("Mechanik", 2, abschnitte=[ids["1 Mechanik"]]), _k("Akustik", 0)],
                   {"Mechanik": [_k("Kraft"), _k("Energie")]})
    erzeugt = await _erzeugen(llm, tiefe=2)
    assert [k["titel"] for k in erzeugt.daten["knoten"][0]["kinder"]] == ["Kraft", "Energie"]
    kinder_aufruf = next(a for a in llm.aufrufe if "knoten" in a["auftrag"])
    auszug = kinder_aufruf["auftrag"]["auszug"]
    assert "Newton." in auszug and "Joule." in auszug and "Licht." not in auszug


async def test_deckel_fuer_gliederung_anfang_und_auszug():
    lang = "# Titel\n" + "".join(f"## Kapitel {i} mit langem Namen\n{'Text ' * 400}\n"
                                 for i in range(1, 400))
    abschnitte, _ = gliederung(lang)
    llm = Attrappe([_k("Kapitel", 2, abschnitte=[a.id for a in abschnitte[1:13]])],
                   {"Kapitel": [_k("Teil")]})
    await _erzeugen(llm, dokument=SimpleNamespace(markdown=lang, abschnitte=abschnitte), tiefe=2)
    oben, kinder = llm.aufrufe
    assert len(oben["auftrag"]["dokument"]["gliederung"]) <= dienst.DOKUMENT_GLIEDERUNG
    assert len(oben["auftrag"]["dokument"]["anfang"]) <= dienst.DOKUMENT_ANFANG
    assert len(kinder["auftrag"]["auszug"]) <= dienst.DOKUMENT_AUSZUG


async def test_ohne_dokument_bleibt_alles_wie_vorher():
    llm = Attrappe([_k("Licht", abschnitte=["a1"])])
    ende = asyncio.get_running_loop().time() + 60
    erzeugt = await dienst.erzeugen(dienst.Auftrag(thema="Optik", tiefe=1), llm=llm,
                                    frist_ende=ende)
    assert erzeugt.daten["quelle"] == "ki" and "abschnitte" not in erzeugt.daten["knoten"][0]
    assert "dokument" not in llm.aufrufe[0]["auftrag"]


async def test_der_ganze_weg_ergibt_einen_gueltigen_block_mit_fundstellen(monkeypatch):
    """Vom Modul-Aufruf bis zum Block: ``quelle: dokument``, ``fundstelle`` und ``abschnitte``
    bestehen die Prüfung gegen ``eingabe`` und die Deckel."""
    from boerdi.ui_module import aufruf
    from boerdi.ui_module.namen import STRUKTURENTWURF

    abschnitte, _ = gliederung(_MD)
    ids = {a.titel: a.id for a in abschnitte}
    llm = Attrappe([_k("Mechanik", 2, abschnitte=[ids["1 Mechanik"]]),
                    _k("Optik", 0, abschnitte=[ids["2 Optik"]])],
                   {"Mechanik": [_k("Kraft"), _k("Energie")]})
    monkeypatch.setattr(dienst, "llm_json", lambda usage_acc: llm)
    dokument = _dokument()

    async def lader():
        return dokument

    erg = await aufruf.asynchron(STRUKTURENTWURF, {"thema": "Lehrplan Physik",
                                                   "aus_dokument": True},
                                 aufruf.Umgebung(dokument=lader))
    assert erg.block is not None, erg.text
    d = erg.block.daten
    assert d["quelle"] == "dokument" and d["knoten"][0]["fundstelle"] == "1 Mechanik"
    assert erg.block.text.startswith("**Entwurf (aus Dokument):")


# ── Querschnitts-Review 2026-11-06: Moderation der Abschnittstexte vor Ebene 2 ───────────────

async def _ebene_zwei(moderieren, monkeypatch=None, modus="open"):
    from boerdi.settings import get_settings

    if monkeypatch is not None:
        monkeypatch.setenv("MODERATION_FAILURE_MODE", modus)
        get_settings.cache_clear()
    abschnitte, _ = gliederung(_MD)
    ids = {a.titel: a.id for a in abschnitte}
    llm = Attrappe([_k("Mechanik", 2, abschnitte=[ids["1 Mechanik"]]), _k("Akustik", 0)],
                   {"Mechanik": [_k("Kraft"), _k("Energie")]})
    ende = asyncio.get_running_loop().time() + 60
    await dienst.erzeugen(dienst.Auftrag(thema="Lehrplan Physik", tiefe=2), llm=llm,
                          frist_ende=ende, dokument=_dokument(), moderieren=moderieren)
    if monkeypatch is not None:
        get_settings.cache_clear()
    # Ohne Auszug trägt der Auftrag das Feld gar nicht.
    return next(a for a in llm.aufrufe if "knoten" in a["auftrag"])["auftrag"].get("auszug", "")


async def test_ein_beanstandeter_auszug_geht_nicht_ans_modell():
    """Die Moderation beim Hochladen sieht nur Übersicht und Anfang — ein Abschnitt weiter hinten
    erreichte das Modell sonst ungeprüft."""
    geprueft: list[str] = []

    async def moderieren(text):
        geprueft.append(text)
        return {"flagged": "Newton." in text}

    assert await _ebene_zwei(moderieren) == ""
    assert geprueft and "Newton." in geprueft[0]


async def test_ein_unbedenklicher_auszug_geht_hin():
    async def moderieren(text):
        return {"flagged": False}

    assert "Newton." in await _ebene_zwei(moderieren)


async def test_ohne_urteil_entscheidet_der_ausfallmodus(monkeypatch):
    async def stumm(text):
        return {}

    assert await _ebene_zwei(stumm, monkeypatch, "closed") == ""
    assert "Newton." in await _ebene_zwei(stumm, monkeypatch, "open")


async def test_derselbe_auszug_wird_einmal_geprueft_auch_gleichzeitig():
    """Review Q4, Befund 2: zwei Punkte mit denselben Abschnitten fragen zugleich — eine Prüfung."""
    from boerdi.services.strukturentwurf_auszug import Auszuege

    abschnitte, _ = gliederung(_MD)
    ids = [a.id for a in abschnitte if a.titel == "1 Mechanik"]
    gerufen: list[str] = []

    async def moderieren(text):
        gerufen.append(text)
        await asyncio.sleep(0.01)
        return {"flagged": False}

    a = Auszuege(_dokument(), 6000, moderieren)
    eins, zwei = await asyncio.gather(a.fuer({"abschnitte": ids}), a.fuer({"abschnitte": ids}))
    assert eins == zwei and "Newton." in eins and len(gerufen) == 1


async def test_ein_entwurf_belegt_hoechstens_einen_moderationsplatz():
    """Review Q4, Befund 1: die Moderation teilt ihre Plätze mit den Chat-Zügen aller Personen."""
    from boerdi.services.strukturentwurf_auszug import Auszuege

    abschnitte, _ = gliederung(_MD)
    zugleich, hoechstens = 0, 0

    async def moderieren(text):
        nonlocal zugleich, hoechstens
        zugleich += 1
        hoechstens = max(hoechstens, zugleich)
        await asyncio.sleep(0.01)
        zugleich -= 1
        return {"flagged": False}

    a = Auszuege(_dokument(), 6000, moderieren)
    await asyncio.gather(*(a.fuer({"abschnitte": [x.id]}) for x in abschnitte))
    assert hoechstens == 1


async def test_ohne_moderation_eine_warnung_je_entwurf(monkeypatch, caplog):
    """Review Q4, Befund 3: ohne Zugang zur Moderation (``open``) nicht je Punkt eine Zeile."""
    from boerdi.services.strukturentwurf_auszug import Auszuege
    from boerdi.settings import get_settings

    monkeypatch.setenv("MODERATION_FAILURE_MODE", "open")
    get_settings.cache_clear()
    abschnitte, _ = gliederung(_MD)

    async def stumm(text):
        return {}

    a = Auszuege(_dokument(), 6000, stumm)
    with caplog.at_level("WARNING"):
        for x in abschnitte:
            await a.fuer({"abschnitte": [x.id]})
    get_settings.cache_clear()
    assert len([r for r in caplog.records if "ohne Moderation" in r.getMessage()]) == 1


async def test_eine_langsame_moderation_haelt_die_frist_des_entwurfs(monkeypatch):
    """Nachprüfung Q4, Befund 1 und 3: das Warten auf die Moderation endet vor der Frist — der Punkt
    bleibt ``ausstehend``, ohne Modellaufruf, und Ebene 1 kommt an (sonst bräche der Lauf ab)."""
    abschnitte, _ = gliederung(_MD)
    ids = {a.titel: a.id for a in abschnitte}
    llm = Attrappe([_k("Mechanik", 2, abschnitte=[ids["1 Mechanik"]]), _k("Akustik", 0)],
                   {"Mechanik": [_k("Kraft"), _k("Energie")]})

    async def langsam(text):
        await asyncio.sleep(1.5)              # länger als die ganze Restzeit
        return {"flagged": False}

    monkeypatch.setattr(dienst, "MINDEST_REST_S", 0.1)
    uhr = asyncio.get_running_loop()
    ende = uhr.time() + 0.5
    erzeugt = await dienst.erzeugen(dienst.Auftrag(thema="Lehrplan Physik", tiefe=2), llm=llm,
                                    frist_ende=ende, dokument=_dokument(), moderieren=langsam)
    assert uhr.time() < ende
    [mechanik] = [k for k in erzeugt.daten["knoten"] if k["titel"] == "Mechanik"]
    assert mechanik.get("ausstehend") is True and not mechanik.get("kinder")
    assert not [a for a in llm.aufrufe if "knoten" in a["auftrag"]]
    await asyncio.sleep(1.5)                  # die geteilte Prüfung läuft zu Ende
