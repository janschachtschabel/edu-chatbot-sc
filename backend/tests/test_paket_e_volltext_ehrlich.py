"""Plan 2026-11-20 §8, Paket E: der Volltext aus WLO ehrlich.

- **E1:** ``not_extracted`` ist endgültig (Messung §7: das Repositorium erzeugt den Text synchron
  beim ersten Lesen und wiederholt eine gescheiterte Extraktion nie). Kein „nochmal“ — der Dienst
  meldet ``volltext_endgueltig`` mit den Auswegen „Hier im Chat lesen lassen“ und „Ohne Dokument
  weiter“; im Ablauf führt „Weiter im Ablauf“ zu einem Schritt mit genau diesen Knöpfen.
- **E2:** nur ``text_unreadable``/``abruf_fehler`` sind vorübergehend — der Leser versucht im selben
  Zug selbst noch zweimal (nach ~5 s und ~10 s), solange die Frist reicht.
"""

from __future__ import annotations

import asyncio
import pathlib

import yaml

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.services.dokumente import stand
from boerdi.services.dokumente import strukturdokument as leser
from boerdi.services.dokumente import strukturdokument_teil as sd
from boerdi.ui_module import dienst as modul_dienst
from boerdi.ui_module import katalog
from boerdi.ui_module.aufruf import Umgebung
from boerdi.ui_module.dienst_fehler import FEHLER
from tests.test_paket_u4_orte import lage  # noqa: F401 — Fixture (Studio, Anmeldung, Träger)

_KNOTEN = "11111111-1111-4111-8111-111111111111"
_SEED = pathlib.Path(__file__).parents[1] / "seeds" / "06-ablaeufe" / "themenbaum.yaml"


class _S:
    async def commit(self):
        return None


def _entwurf(fehlend):
    async def ohne():
        return stand.OhneVolltext(fehlend)

    return asyncio.run(modul_dienst.aufruf(katalog.katalog()["ui_strukturentwurf"],
                                           {"thema": "Physik", "aus_dokument": True},
                                           Umgebung(dokument=ohne)))


# ── E1: ``not_extracted`` ist endgültig ──────────────────────────────────────────────────────────

def test_e1_not_extracted_ist_nicht_voruebergehend():
    assert leser.NICHT_EXTRAHIERT not in leser.SPAETER
    assert {"text_unreadable", "abruf_fehler", "frist"} <= leser.SPAETER


def test_e1_der_dienst_meldet_volltext_endgueltig_mit_den_auswegen():
    erg = _entwurf((("Lehrplan.pdf", "not_extracted"),))
    assert erg.block is None and erg.outcome.error == "volltext_endgueltig"
    assert "„Lehrplan.pdf“" in erg.text and "keinen Text gewinnen" in erg.text
    assert "Hier im Chat lesen lassen" in erg.text and "Ohne Dokument weiter" in erg.text
    assert "Weiter im Ablauf" in erg.text
    # kein Warten, kein „nochmal“ — ein neuer Versuch hilft nie
    assert "nochmal" not in erg.text and "gerade erzeugt" not in erg.text


def test_e1_endgueltig_geht_vor_dem_lesefehler():
    assert modul_dienst._volltext_satz((("a", "not_extracted"),)) == "volltext_endgueltig"
    assert modul_dienst._volltext_satz((("a", "frist"), ("b", "not_extracted"))) == (
        "volltext_endgueltig")
    assert modul_dienst._volltext_satz((("a", "text_unreadable"),)) == "volltext_fehlt"
    assert _entwurf((("a.pdf", "text_unreadable"),)).outcome.error == "volltext_fehlt"


def test_e1_gemischt_nennt_den_ausweg_statt_zu_warten():
    satz = modul_dienst._ohne_volltext((("Scan.pdf", "not_extracted"),))
    assert "keinen Text gewinnen" in satz and "hier im Chat lesen lassen" in satz
    assert "entsteht" not in satz and "später" not in satz


def test_e1_der_alte_wartesatz_ist_weg():
    assert "volltext_fehlt_datei" not in FEHLER


# ── E1: der Ablauf bietet die Auswege als Knöpfe ─────────────────────────────────────────────────

def _themenbaum() -> AblaufArea:
    return AblaufArea.model_validate(yaml.safe_load(_SEED.read_text(encoding="utf-8")))


def test_e1_nach_dem_dokument_entwurf_feste_knoepfe_statt_nochmal_schleife():
    ablauf = _themenbaum()
    schritte = {s.id: s for s in ablauf.schritte}
    ziel = schritte["entwurf_dokument"].bei_fehler
    assert ziel == "ohne_dokumenttext"
    ausweg = schritte[ziel]
    wahl = {o.label["de"]: o for o in ausweg.optionen or []}
    # Review Paket E, MAJOR 1: ein eigenes Feld nur mit „Hier im Chat“ (``test_r1_…``)
    assert wahl["Dokument hier im Chat lesen lassen"].ziel == "dokument_chat"
    assert "document" in (wahl["Dokument hier im Chat lesen lassen"].verwirft or [])
    assert wahl["Ohne Dokument weiter"].ziel == "grundlage"
    assert {"grundlage", "document"} <= set(wahl["Ohne Dokument weiter"].verwirft or [])
    # kein Freitext: jede Wahl leerte sonst dessen Teil (hier ``grundlage``, Review AS-3, Befund 3)
    assert ausweg.freitext is None


# ── E2: vorübergehende Gründe im selben Zug selbst wiederholen ───────────────────────────────────

def _volltext_folge(monkeypatch, antworten: list[tuple[str | None, str]]) -> list[float]:
    """``volltext`` liefert nacheinander ``antworten``; Pausen werden gemerkt, nicht gewartet."""
    folge = list(antworten)
    pausen: list[float] = []
    aufrufe: list[str] = []

    async def volltext(node_id):
        aufrufe.append(node_id)
        return folge.pop(0)

    async def schlafen(s):
        pausen.append(s)

    monkeypatch.setattr(leser, "volltext", volltext)
    monkeypatch.setattr(leser, "_schlafen", schlafen)
    return pausen


def _lesen(frist_s: float = 30.0):
    async def lauf():
        ende = asyncio.get_running_loop().time() + frist_s
        return await leser.staende([sd.wlo(_KNOTEN, "w.pdf")], session=_S(), session_id="s",
                                   frist_ende=ende)

    return asyncio.run(lauf())


_TEXT = "# A\n" + " ".join(["Lernfeld"] * 40)


def test_e2_ein_lesefehler_wird_nach_5_s_wiederholt_und_gelingt(monkeypatch):
    pausen = _volltext_folge(monkeypatch, [(None, "text_unreadable"), (_TEXT, "")])
    lesung = _lesen()
    assert pausen == [5.0]
    assert [d.name for d in lesung.staende] == ["w.pdf"] and lesung.fehlend == []


def test_e2_hoechstens_zwei_wiederholungen_nach_5_und_10_s(monkeypatch):
    pausen = _volltext_folge(monkeypatch, [(None, "abruf_fehler")] * 3)
    lesung = _lesen()
    assert pausen == [5.0, 10.0]
    assert lesung.fehlend == [("w.pdf", "abruf_fehler")]


def test_e2_endgueltige_gruende_werden_nie_wiederholt(monkeypatch):
    for grund in ("not_extracted", "access_denied", "ohne_anmeldung", "node_not_found"):
        pausen = _volltext_folge(monkeypatch, [(None, grund)])
        assert _lesen().fehlend == [("w.pdf", grund)]
        assert pausen == []


def test_e2_keine_wiederholung_ueber_die_frist_hinaus(monkeypatch):
    """Reicht die Frist nicht für Pause und Versuch, bleibt der letzte Grund (nicht ``frist``)."""
    pausen = _volltext_folge(monkeypatch, [(None, "text_unreadable")])
    assert _lesen(frist_s=4.0).fehlend == [("w.pdf", "text_unreadable")]
    assert pausen == []


# ══ Review Paket E (20.11.) ══════════════════════════════════════════════════════════════════════

# ── MAJOR 1: „hier im Chat lesen lassen“ bietet nur „Hier im Chat“ ──────────────────────────────

def test_r1_der_chat_ausweg_hat_ein_eigenes_feld_nur_mit_ort_chat(lage):  # noqa: F811
    ablauf = _themenbaum()
    schritte = {s.id: s for s in ablauf.schritte}
    wahl = {o.id: o for o in schritte["ohne_dokumenttext"].optionen or []}
    feld = schritte[wahl["chat"].ziel]
    assert feld.id == "dokument_chat" and feld.modul == "ui_upload"
    assert feld.daten == {"zweck": "bereitstellen", "einzeldatei_als_struktur": True,
                          "orte": ["chat"]}
    assert feld.weiter == "dokument_gelesen"
    # angemeldet mit Flow-Träger wäre sonst „In WLO ablegen“ vorgewählt — die Schleife
    erg = asyncio.run(modul_dienst.aufruf(katalog.katalog()["ui_upload"], dict(feld.daten),
                                          Umgebung(aus_ablauf=True)))
    orte = erg.block.daten["orte"]
    assert orte["vorauswahl"] == "chat" and orte["wlo"] == {"geht": False, "grund": "ablauf"}


def test_r10_ohne_dokument_verwirft_auch_die_teile_der_anderen_wege():
    schritt = {s.id: s for s in _themenbaum().schritte}["ohne_dokumenttext"]
    wahl = {o.id: o for o in schritt.optionen or []}
    assert {"ordnerweg", "soll_ist"} <= set(wahl["ohne"].verwirft or [])


def test_r4_kein_diesmal_und_nochmal_steht_zuletzt():
    schritt = {s.id: s for s in _themenbaum().schritte}["ohne_dokumenttext"]
    assert "diesmal" not in schritt.text["de"]
    assert [o.id for o in schritt.optionen][-1] == "nochmal"
    assert "ausgelastet" in schritt.optionen[-1].label["de"]


# ── MINOR 2: ``ablage`` nur, wenn der Teil ``strukturdokument`` fehlt ───────────────────────────

def test_r2_ein_vorhandener_teil_holt_keine_toten_knoten_aus_der_ablage():
    ablage = {"inhalte": [{"rolle": "struktur", "stand": "stored", "node_id": _KNOTEN,
                           "titel": "Alt.pdf"}]}
    chat = sd.chatbot("22222222-2222-4222-8222-222222222222", "Neu.pdf")

    def lader(teile):
        async def teil(name):
            return teile.get(name)
        return teil

    mit_teil = asyncio.run(leser.im_vorgang(lader({sd.TEIL: sd.wert([chat]), "ablage": ablage})))
    assert [e["name"] for e in mit_teil] == ["Neu.pdf"]
    # ein Vorgang vor TG-3d (kein Teil): die Ablage bleibt der Rückgriff
    ohne_teil = asyncio.run(leser.im_vorgang(lader({"ablage": ablage})))
    assert [e["ref"] for e in ohne_teil] == [_KNOTEN]


# ── MINOR 3: gemischt — der Endgültig-Satz nennt nur die Dokumente ohne Text ────────────────────

def test_r3_gemischt_nennt_endgueltig_nur_die_namen_ohne_text():
    erg = _entwurf((("Scan.pdf", "not_extracted"), ("Weg.pdf", "access_denied")))
    assert erg.outcome.error == "volltext_endgueltig"
    erster = erg.text.split(". ")[0]
    assert "„Scan.pdf“" in erster and "Weg.pdf" not in erster
    assert "Dokument „Weg.pdf“: kein Volltext lesbar." in erg.text


# ── MINOR 5: Fehler des MCP-Aufrufs nach ihrer Art ──────────────────────────────────────────────

def _mcp_art(monkeypatch, art: str):
    from boerdi.services.mcp import client

    async def antwort(name, args, *, use_cache=True):
        return client.McpAntwort(text="Fehler beim Aufruf von get_wlo_content_text: x", art=art)

    monkeypatch.setattr(client, "call_mcp_tool_antwort", antwort)
    monkeypatch.setattr(leser, "has_personal_auth", lambda: True)


def test_r5_keine_antwort_ist_ein_abruffehler_und_wird_wiederholt(monkeypatch):
    for art in ("timeout", "transport", "busy"):
        _mcp_art(monkeypatch, art)
        assert asyncio.run(leser.volltext("n-1")) == (None, "abruf_fehler")
    assert "abruf_fehler" in leser.SPAETER


def test_r5_abgewiesene_anmeldung_heisst_ohne_anmeldung(monkeypatch):
    _mcp_art(monkeypatch, "auth")
    assert asyncio.run(leser.volltext("n-1")) == (None, "ohne_anmeldung")


# ── MINOR 6: die Frist der Lesung trägt ein langsames erstes Lesen und eine Wiederholung ────────

def test_r6_nach_einem_ersten_lesen_bis_zur_frist_des_mcp_passt_eine_wiederholung():
    """Der MCP wartet auf das Repositorium bis ``WLO_TEXT_TIMEOUT_MS`` (Vorgabe 25 s)."""
    assert leser.GESAMT_FRIST_S >= 25.0 + leser.WIEDERHOLEN_S[0] + 15.0


# ── MINOR 7: „auch Text in Scans“ nur, wenn hier im Chat mit Texterkennung geht ─────────────────

def test_r7_der_scan_hinweis_nur_mit_texterkennung(monkeypatch):
    from boerdi.ui_module import dienst_fehler

    monkeypatch.setattr(dienst_fehler, "_chat_mit_texterkennung", lambda: True)
    assert "Scans" in _entwurf((("a.pdf", "not_extracted"),)).text
    monkeypatch.setattr(dienst_fehler, "_chat_mit_texterkennung", lambda: False)
    ohne = _entwurf((("a.pdf", "not_extracted"),)).text
    assert "Scans" not in ohne and "Hier im Chat lesen lassen" in ohne


def test_r7_der_seed_verspricht_die_texterkennung_nicht():
    schritt = {s.id: s for s in _themenbaum().schritte}["ohne_dokumenttext"]
    assert "oft auch aus Scans" in schritt.text["de"] and "erkannt" not in schritt.text["de"]


# ── MINOR 8: auf dem Dokument-Weg verspricht der Satz an die KI keine Metadaten ─────────────────

def test_r8_der_dokument_weg_verspricht_keine_metadaten(lage, monkeypatch):  # noqa: F811
    from boerdi.ui_module import dienst_upload

    monkeypatch.setattr(dienst_upload, "schalter", lambda: {"ablage_in_wlo": True,
                                                            "dokument_im_chat": True})
    datei_weg = asyncio.run(modul_dienst.aufruf(katalog.katalog()["ui_upload"],
                                                {"zweck": "bereitstellen"}, Umgebung())).text
    assert "Volltexte" in datei_weg                       # der Datei-Weg bleibt, wie er war
    args = {"zweck": "bereitstellen", "einzeldatei_als_struktur": True}
    satz = asyncio.run(modul_dienst.aufruf(katalog.katalog()["ui_upload"], args,
                                           Umgebung(aus_ablauf=True))).text
    assert "Metadaten." not in satz and "auf Wunsch Metadaten" not in satz
    assert "liest der Chat danach den Text" in satz


# ── NIT 12: die Pause hält keinen Platz; Frist im zweiten Versuch ───────────────────────────────

def test_r12_in_der_pause_haelt_der_knoten_keinen_platz(monkeypatch):
    belegt: list[int] = []

    async def volltext(node_id):
        return None, "text_unreadable"

    async def schlafen(s):
        belegt.append(platz_frei())

    platz_frei = None
    echt = asyncio.Semaphore

    def semaphor(n):
        nonlocal platz_frei
        sem = echt(n)
        platz_frei = lambda: sem._value  # noqa: E731 — gemessen: freie Plätze
        return sem

    monkeypatch.setattr(leser, "volltext", volltext)
    monkeypatch.setattr(leser, "_schlafen", schlafen)
    monkeypatch.setattr(leser.asyncio, "Semaphore", semaphor)
    _lesen()
    assert belegt == [leser.PARALLEL, leser.PARALLEL]


def test_r12_frist_im_zweiten_versuch_der_letzte_grund_bleibt(monkeypatch):
    aufrufe = {"n": 0}

    async def volltext(node_id):
        aufrufe["n"] += 1
        if aufrufe["n"] == 1:
            return None, "abruf_fehler"
        await asyncio.sleep(5)
        return _TEXT, ""

    async def schlafen(s):
        return None

    monkeypatch.setattr(leser, "volltext", volltext)
    monkeypatch.setattr(leser, "_schlafen", schlafen)
    monkeypatch.setattr(leser, "WIEDERHOLEN_S", (0.01,))
    assert _lesen(frist_s=0.2).fehlend == [("w.pdf", "abruf_fehler")]
