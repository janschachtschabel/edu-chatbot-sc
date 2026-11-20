"""Plan 2026-11-19, E1c (viertes Review A, ersetzt die Anker E1a/E1b): Ebene 2 auf dem Weg „ganz“.

Hat der Aufrufer den ganzen Text moderiert (``ganz_moderiert=True``, Text ≤ ``GANZTEXT_ZEICHEN``),
bekommt JEDER Aufruf für Unterpunkte den ganzen Text statt eines Auszugs — das Modell findet den
Abschnitt seines Punkts selbst (Nutzervorgabe E1). Für das Prompt-Caching beginnen die Nachrichten
aller Punkte byte-gleich (Systemteil, dann das Dokument), erst danach steht die Aufgabe des Punkts;
ein Vorwärm-Aufruf nur mit diesem Anfang füllt den Cache, danach laufen alle Punkte parallel
(gemessen: der Cache des Anbieters trifft nur am Ende des Systemteils oder am Ende eines früheren
Prompts — ein erster Punkt allein endet hinter seiner Aufgabe und half nicht). Der Weg
„gliederung“ bleibt, wie er war.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any

from boerdi.domain.dokument_gliederung import gliederung
from boerdi.services import strukturentwurf_dienst as dienst
from boerdi.services import strukturentwurf_dokument as sd
from boerdi.services import strukturentwurf_lauf as lauf_teil
from tests.test_strukturentwurf_dienst import _k

_MD = ("# Rahmenlehrplan Automobilkaufleute\n"
       "Lernfeld 1: Kunden beraten 1. Ausbildungsjahr\n" + "Beratung im Autohaus. " * 30 + "\n"
       "Lernfeld 2: Teile beschaffen 1. Ausbildungsjahr\n" + "Lager und Bestellung. " * 30 + "\n"
       "Lernfeld 3: Fahrzeuge verkaufen 2. Ausbildungsjahr\n" + "Verkaufsgespräch. " * 30 + "\n")


def _dokument(md: str = _MD):
    abschnitte, _ = gliederung(md)
    return SimpleNamespace(markdown=md, abschnitte=abschnitte, name="Kfz.pdf")


class Mitschrift:
    """LLM-Attrappe: merkt sich je Aufruf die Nachrichten und Beginn/Ende (Reihenfolge)."""

    def __init__(self, pause: float = 0.0, abschnitte: list[str] | None = None, *,
                 tief: bool = False, vorwaermen: str = "") -> None:
        self.aufrufe: list[list[dict[str, Any]]] = []
        self.ereignisse: list[tuple[str, str]] = []
        self.pause, self.abschnitte = pause, abschnitte
        #: ``tief``: Ebene-2-Punkte sehen 2 Unterpunkte vor (Ebene 3); ``vorwaermen``: ``wirft``
        #: oder ``haengt`` (fünftes Review A, MINOR 2)
        self.tief, self.vorwaermen = tief, vorwaermen

    async def __call__(self, nachrichten, max_tokens, frist_s, platz_frist_s):
        auftrag = json.loads(nachrichten[-1]["content"].split("\n", 1)[1])
        ziel = (auftrag["knoten"]["titel"] if "knoten" in auftrag
                else "vorwaermen" if nachrichten[-1]["content"].startswith("Dokument der Person")
                else "oben")
        self.aufrufe.append(nachrichten)
        self.ereignisse.append(("start", ziel))
        if ziel == "vorwaermen" and self.vorwaermen == "wirft":
            raise RuntimeError("Vorwärmen gescheitert")
        if ziel == "vorwaermen" and self.vorwaermen == "haengt":
            await asyncio.sleep(30)
        await asyncio.sleep(self.pause)
        self.ereignisse.append(("ende", ziel))
        if ziel == "vorwaermen":
            return {}
        if ziel == "oben":
            mehr = {"abschnitte": self.abschnitte} if self.abschnitte else {}
            return {"titel": "Kfz", "knoten": [_k(f"LF{n}", 4, **mehr) for n in (1, 2, 3)]}
        plan = 2 if self.tief and not auftrag.get("pfad") else 0     # nur Ebene 2 plant Ebene 3
        return {"knoten": [_k(f"{ziel} {b}", plan) for b in "ABC"]}


async def _erzeugen(llm, dokument=None, **mehr):
    ende = asyncio.get_running_loop().time() + 60
    return await dienst.erzeugen(dienst.Auftrag(thema="Kfz", tiefe=2), llm=llm, frist_ende=ende,
                                 dokument=dokument or _dokument(), **mehr)


def _ebene_zwei(llm: Mitschrift) -> list[list[dict[str, Any]]]:
    return [n for n in llm.aufrufe if '"knoten": {' in n[-1]["content"]]


async def test_jeder_punkt_bekommt_den_ganzen_text_und_keinen_auszug():
    llm = Mitschrift()
    erzeugt = await _erzeugen(llm, ganz_moderiert=True)
    aufrufe = _ebene_zwei(llm)
    assert len(aufrufe) == 3
    for nachrichten in aufrufe:
        alles = "".join(m["content"] for m in nachrichten)
        assert "Verkaufsgespräch" in alles and "Beratung im Autohaus" in alles   # der ganze Text
        auftrag = json.loads(nachrichten[-1]["content"].split("\n", 1)[1])
        assert "auszug" not in auftrag
    assert all(len(k["kinder"]) == 3 for k in erzeugt.daten["knoten"])


async def test_der_anfang_der_nachrichten_ist_fuer_alle_punkte_byte_gleich():
    llm = Mitschrift()
    await _erzeugen(llm, ganz_moderiert=True)
    eins, zwei, drei = _ebene_zwei(llm)
    assert eins[:-1] == zwei[:-1] == drei[:-1]                   # alles vor der Aufgabe gleich
    assert eins[-1] != zwei[-1]                                   # die Aufgabe je Punkt
    # das Dokument davor, als Daten
    assert json.loads(eins[-2]["content"].split("\n", 1)[1]) == {"dokument": _MD}


async def test_ein_vorwaerm_aufruf_mit_dem_anfang_laeuft_vor_den_punkten():
    llm = Mitschrift(pause=0.02)
    await _erzeugen(llm, ganz_moderiert=True)
    ebene_zwei = [e for e in llm.ereignisse if e[1] != "oben"]
    assert ebene_zwei[:2] == [("start", "vorwaermen"), ("ende", "vorwaermen")]
    # danach alle Punkte zugleich
    assert [a for a, _ in ebene_zwei[2:5]] == ["start", "start", "start"]
    [vorwaermen] = [n for n in llm.aufrufe
                    if n[-1]["content"].startswith("Dokument der Person")]
    assert vorwaermen == _ebene_zwei(llm)[0][:2]                # genau der gemeinsame Anfang


async def test_ohne_weg_ganz_kein_vorwaermen():
    llm = Mitschrift(abschnitte=[gliederung(_MD)[0][0].id])
    await _erzeugen(llm)
    assert all(e[1] != "vorwaermen" for e in llm.ereignisse)


async def test_ebene_eins_verlangt_keinen_anker_mehr():
    llm = Mitschrift()
    await _erzeugen(llm, ganz_moderiert=True)
    assert "anker" not in llm.aufrufe[0][0]["content"]


async def test_der_weg_gliederung_bleibt_mit_auszuegen():
    llm = Mitschrift(abschnitte=[gliederung(_MD)[0][0].id])
    await _erzeugen(llm)                                          # ohne Zusage der Moderation
    for nachrichten in _ebene_zwei(llm):
        assert len(nachrichten) == 2                              # System und Auftrag wie bisher
        assert "auszug" in json.loads(nachrichten[-1]["content"].split("\n", 1)[1])


def test_auf_dem_weg_ganz_hat_jeder_punkt_text_fuer_unterpunkte():
    """``plan_ohne_angabe``: auf dem Weg „ganz“ hat jeder obere Punkt Text, auch ohne
    Abschnitte."""
    plaene = {"k1": 0, "k2": 3}
    sd.nacharbeit([({"id": "k1", "titel": "A"}, {}), ({"id": "k2", "titel": "B"}, {})],
                  plaene, _dokument(), ganz=True)
    assert plaene == {"k1": 8, "k2": 3}


# ── Fünftes Review A ────────────────────────────────────────────────────────────────────────────

async def test_bei_tiefe_drei_bekommt_nur_ebene_zwei_das_dokument():
    """MAJOR 1: der ganze Text und die Anhebung der Zahl gelten nur für die oberen Punkte —
    Ebene 3 läuft wie bisher (ohne Dokument, höchstens die Planzahl); ein Vorwärmen je Lauf."""
    llm = Mitschrift(tief=True)
    ende = asyncio.get_running_loop().time() + 60
    await dienst.erzeugen(dienst.Auftrag(thema="Kfz", tiefe=3), llm=llm, frist_ende=ende,
                          dokument=_dokument(), ganz_moderiert=True)
    ebene3 = [n for n in llm.aufrufe if '"knoten": {' in n[-1]["content"]
              and json.loads(n[-1]["content"].split("\n", 1)[1]).get("pfad")]
    assert ebene3, "Ebene 3 lief"
    for nachrichten in ebene3:
        assert len(nachrichten) == 2 and "Verkaufsgespräch" not in nachrichten[0]["content"]
        assert json.loads(nachrichten[-1]["content"].split("\n", 1)[1])["anzahl"] <= 2
    assert sum(1 for e in llm.ereignisse if e == ("start", "vorwaermen")) == 1


async def test_vorwaermen_wirft_die_punkte_bekommen_trotzdem_unterpunkte():
    erzeugt = await _erzeugen(Mitschrift(vorwaermen="wirft"), ganz_moderiert=True)
    assert all(len(k.get("kinder") or []) == 3 for k in erzeugt.daten["knoten"])


async def test_vorwaermen_haengt_die_punkte_bekommen_trotzdem_unterpunkte(monkeypatch):
    """MINOR 2: eigene kurze Frist für das Vorwärmen — ein Hängen kostet Ebene 2 nicht."""
    import time

    monkeypatch.setattr(lauf_teil, "VORWAERMEN_FRIST_S", 0.2)
    t0 = time.monotonic()
    erzeugt = await _erzeugen(Mitschrift(vorwaermen="haengt"), ganz_moderiert=True)
    assert time.monotonic() - t0 < 5
    assert all(len(k.get("kinder") or []) == 3 for k in erzeugt.daten["knoten"])


async def test_mit_knapper_frist_kein_vorwaermen(monkeypatch):
    """MINOR 2: nur mit mindestens 2 × ``MINDEST_REST_S`` Rest — sonst gleich die Punkte."""
    monkeypatch.setattr(lauf_teil, "MINDEST_REST_S", 1.0)
    llm = Mitschrift()
    ende = asyncio.get_running_loop().time() + 1.8
    await dienst.erzeugen(dienst.Auftrag(thema="Kfz", tiefe=2), llm=llm, frist_ende=ende,
                          dokument=_dokument(), ganz_moderiert=True)
    assert all(e[1] != "vorwaermen" for e in llm.ereignisse)


async def test_mehrere_dokumente_auf_dem_weg_ganz():
    from boerdi.services.dokumente import stand

    def _stand(name, md):
        abschnitte, _ = gliederung(md)
        return stand.DokumentStand(upload_id=name, name=name, format="md", befund={},
                                   abschnitte=abschnitte, markdown=md)

    vereint = stand.vereint([_stand("A.pdf", _MD), _stand("B.pdf", "# Anhang\n" + "Zusatz. " * 40)])
    llm = Mitschrift()
    await _erzeugen(llm, dokument=vereint, ganz_moderiert=True)
    for nachrichten in _ebene_zwei(llm):
        dok = json.loads(nachrichten[-2]["content"].split("\n", 1)[1])["dokument"]
        assert dok == vereint.markdown and "Zusatz." in dok and "Verkaufsgespräch" in dok


async def test_knapper_rest_und_haengendes_vorwaermen_kostet_ebene_zwei_nicht(monkeypatch):
    """Kontroll-Durchgang, MINOR 1: die Frist des Vorwärmens hängt am Rest — es bleibt das Budget
    für Ebene 2; reicht der Rest dafür nicht, entfällt das Vorwärmen."""
    monkeypatch.setattr(lauf_teil, "MINDEST_REST_S", 1.0)
    monkeypatch.setattr(lauf_teil, "VORWAERMEN_FRIST_S", 3.0)
    monkeypatch.setattr(lauf_teil, "EBENE2_BUDGET_S", 2.0, raising=False)
    llm = Mitschrift(vorwaermen="haengt")
    ende = asyncio.get_running_loop().time() + 2.6           # knapp über 2 × MINDEST_REST_S
    erzeugt = await dienst.erzeugen(dienst.Auftrag(thema="Kfz", tiefe=2), llm=llm,
                                    frist_ende=ende, dokument=_dokument(), ganz_moderiert=True)
    assert erzeugt.daten is not None
    assert all(len(k.get("kinder") or []) == 3 for k in erzeugt.daten["knoten"])

